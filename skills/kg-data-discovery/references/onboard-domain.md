# Onboard Domain

Step-by-step workflow for onboarding a new data source into the KG.

## Prerequisites

- Session validated (see `core-session.md`)
- Domain boundaries decided (see `domain-model.md` or run DISCOVER first)
- Warehouse available

## Workflow

### Step 1: Create Domain Infrastructure

```sql
CREATE DATABASE IF NOT EXISTS {DOMAIN}_META;
CREATE SCHEMA IF NOT EXISTS {DOMAIN}_META.META;

-- Create all tables (DDL in core-architecture.md)
-- RAW_CONCEPTS, CONCEPTS, RELATIONSHIPS, OBJECT_STATE, DOMAIN_CONFIG
```

### Step 2: Set Domain Config

```sql
INSERT INTO {DOMAIN}_META.META.DOMAIN_CONFIG VALUES
  ('domain_name', '"{DOMAIN}"'),
  ('source_databases', '["DB_1", "DB_2"]'),
  ('ignore_schemas', '["INFORMATION_SCHEMA", "SCRATCH"]'),
  ('enrichment_max_tier', '2'),
  ('enrichment_daily_budget_credits', '5.0'),
  ('css_warehouse', '"COMPUTE_WH"'),
  ('css_target_lag', '"1 hour"');
```

### Step 3: CRAWL — Three-Level Metadata Harvest

**Database-level concepts:**

```sql
INSERT INTO {DOMAIN}_META.META.RAW_CONCEPTS (
  concept_name, concept_level, domain, source_database,
  comment, created, owner, is_transient, metadata_hash
)
SELECT
  database_name,
  'database',
  '{DOMAIN}',
  database_name,
  comment,
  created,
  database_owner,
  is_transient = 'YES',
  MD5(database_name || COALESCE(comment, '') || COALESCE(database_owner, ''))
FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES
WHERE database_name IN (SELECT PARSE_JSON(config_value)::VARCHAR FROM {DOMAIN}_META.META.DOMAIN_CONFIG WHERE config_key = 'source_databases' -- handle array)
  AND deleted IS NULL;
```

**Schema-level concepts:**

```sql
-- For each source database
INSERT INTO {DOMAIN}_META.META.RAW_CONCEPTS (
  concept_name, concept_level, domain, source_database, source_schema,
  comment, owner, is_managed_access, metadata_hash
)
SELECT
  schema_name,
  'schema',
  '{DOMAIN}',
  catalog_name,
  schema_name,
  comment,
  schema_owner,
  is_managed_access = 'YES',
  MD5(catalog_name || '.' || schema_name || COALESCE(comment, ''))
FROM {DB}.INFORMATION_SCHEMA.SCHEMATA
WHERE schema_name NOT IN ('INFORMATION_SCHEMA')
  AND schema_name NOT IN (SELECT value::VARCHAR FROM TABLE(FLATTEN(input => PARSE_JSON(
    (SELECT config_value FROM {DOMAIN}_META.META.DOMAIN_CONFIG WHERE config_key = 'ignore_schemas')
  ))));
```

**Table-level concepts (with columns):**

```sql
-- For each schema in domain
INSERT INTO {DOMAIN}_META.META.RAW_CONCEPTS (
  concept_name, concept_level, domain, source_database, source_schema, source_table,
  table_type, row_count, bytes, clustering_key, comment, created, last_altered,
  columns_json, constraints_json, sample_values_json, metadata_hash
)
SELECT
  t.table_name,
  'table',
  '{DOMAIN}',
  t.table_catalog,
  t.table_schema,
  t.table_name,
  t.table_type,
  t.row_count,
  t.bytes,
  t.clustering_key,
  t.comment,
  t.created,
  t.last_altered,
  -- Column metadata as VARIANT array
  (SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
    'name', column_name, 'type', data_type,
    'nullable', is_nullable, 'comment', comment,
    'ordinal', ordinal_position
  )) FROM {DB}.INFORMATION_SCHEMA.COLUMNS c
   WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name),
  -- Constraints
  (SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
    'name', constraint_name, 'type', constraint_type
  )) FROM {DB}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
   WHERE tc.table_schema = t.table_schema AND tc.table_name = t.table_name),
  NULL,  -- sample_values populated separately
  MD5(t.table_catalog || '.' || t.table_schema || '.' || t.table_name || t.row_count::VARCHAR || COALESCE(t.last_altered::VARCHAR, ''))
FROM {DB}.INFORMATION_SCHEMA.TABLES t
WHERE t.table_schema = '{SCHEMA}'
  AND t.table_type IN ('BASE TABLE', 'EXTERNAL TABLE');
```

**Sample values (for enum detection):**

For each table, sample low-cardinality columns:

```sql
-- Identify enum candidates (< 50 distinct values, VARCHAR type)
-- Then: SELECT DISTINCT col FROM table LIMIT 25
-- Store in RAW_CONCEPTS.sample_values_json
```

### Step 4: ENRICH — Apply Cost-Tiered AI

See `enrich-pipeline.md` for full details. Summary:

1. **Tier 0 (free):** Column name heuristics, comment parsing, FK inference
2. **Tier 1 ($):** AI_CLASSIFY on ambiguous columns
3. **Tier 2 ($$):** AI_EXTRACT on undocumented tables
4. **Tier 3 ($$$):** AI_COMPLETE on VARIANT columns, cross-DB relationships

Transform RAW_CONCEPTS → CONCEPTS with enriched fields:
- `description`: human-readable purpose
- `keywords`: searchable terms
- `search_content`: concatenated searchable text
- `tables_yaml`: structured table/column metadata for Cortex Analyst
- `join_keys_yaml`: relationship info
- `metrics_yaml`: aggregation definitions

### Step 5: Detect Relationships

Run relationship detection (see `domain-relationships.md`):

1. Declared FKs from constraints
2. Name-based inference (_ID patterns)
3. Co-access patterns from ACCESS_HISTORY
4. Insert into RELATIONSHIPS table

### Step 6: Initialize OBJECT_STATE

```sql
INSERT INTO {DOMAIN}_META.META.OBJECT_STATE (
  object_fqn, object_level, object_state, concept_id,
  first_seen, last_seen, metadata_hash
)
SELECT
  CASE concept_level
    WHEN 'database' THEN source_database
    WHEN 'schema' THEN source_database || '.' || source_schema
    WHEN 'table' THEN source_database || '.' || source_schema || '.' || source_table
  END,
  concept_level,
  'KNOWN_CURRENT',
  concept_id,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  metadata_hash
FROM {DOMAIN}_META.META.CONCEPTS;
```

### Step 7: Create CSS

```sql
CREATE OR REPLACE CORTEX SEARCH SERVICE {DOMAIN}_META.META.{DOMAIN}_SEARCH
  ON search_content
  ATTRIBUTES concept_name, concept_level, domain, source_database, source_schema
  WAREHOUSE = COMPUTE_WH
  TARGET_LAG = '1 hour'
AS (
  SELECT
    concept_name, concept_level, domain, source_database, source_schema,
    search_content, tables_yaml, join_keys_yaml, metrics_yaml,
    sample_values, is_enum
  FROM {DOMAIN}_META.META.CONCEPTS
  WHERE is_active = TRUE
);
```

### Step 8: Validate

Test search quality with 3-5 sample questions:

```python
results = search_service.search(
    query="monthly revenue by product",
    columns=["concept_name", "tables_yaml"],
    limit=5
)
```

Check:
- Do results return relevant tables?
- Are descriptions accurate?
- Are join paths correct?
- Are sample values useful for literal matching?

### Step 9: Update Master KG (if exists)

```sql
CALL MASTER_META.META.REFRESH_MASTER();
```

## Source-Specific Hints

| Source Type | Enrichment Notes |
|-------------|-----------------|
| **dbt marts** | Light enrichment — rich comments exist. Focus on Tier 0. |
| **Shared databases** | May need Tier 2 for cryptic column names. Read-only. |
| **Raw lakes** | VARIANT-heavy. Need Tier 3 for path extraction. |
| **Operational replicas** | Well-normalized. Good FK detection. Tier 0-1 sufficient. |
| **Marketplace datasets** | Unknown quality. Full pipeline Tier 0-2. |
