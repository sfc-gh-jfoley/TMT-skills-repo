# Core Architecture

Two-plane, eight-step architecture for Knowledge Graph-powered data discovery.

## Two Planes

**INDEX PLANE** (async, scheduled) — Crawls metadata, enriches with AI, indexes into Cortex Search Services. Runs on schedule or on-demand. Cost is amortized.

**QUERY PLANE** (sync, per question, <2s) — Searches the KG, assembles minimal schema context, routes to Cortex Analyst for SQL generation, executes. No AI enrichment cost at query time.

## Eight Steps

### Step 0: DISCOVER (one-time, free)

Profile the entire account using ACCOUNT_USAGE + INFORMATION_SCHEMA. Zero AI cost. Outputs:
- Account profile (database count, table count, total storage, active users)
- Proposed domain map (auto-clustered by DB/schema/FK/access patterns)
- Priority ranking (by query volume, user count, freshness, complexity)
- Phased rollout plan (top 2-3 domains first)
- Stale data report (tables with no access in 90+ days)

```sql
-- Core discovery queries (all free)
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES;
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.SCHEMATA;
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES;
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.COLUMNS;
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS;
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY;
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY;
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.OBJECT_DEPENDENCIES;
```

### Step 1: CRAWL (per domain, free SQL)

Harvest metadata for a specific domain. Three-level crawl: databases → schemas → tables.

```sql
-- Database-level
SHOW DATABASES;
SELECT database_name, owner, comment, created, is_transient
FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES
WHERE deleted IS NULL;

-- Schema-level
SELECT catalog_name, schema_name, schema_owner, comment, is_managed_access
FROM <DB>.INFORMATION_SCHEMA.SCHEMATA;

-- Table-level
SELECT table_catalog, table_schema, table_name, table_type, row_count,
       bytes, clustering_key, comment, created, last_altered
FROM <DB>.INFORMATION_SCHEMA.TABLES
WHERE table_schema NOT IN ('INFORMATION_SCHEMA');

-- Column-level (within each table)
SELECT column_name, data_type, is_nullable, column_default, comment,
       ordinal_position
FROM <DB>.INFORMATION_SCHEMA.COLUMNS
WHERE table_schema = '<SCHEMA>' AND table_name = '<TABLE>'
ORDER BY ordinal_position;

-- Constraints (free FK detection)
SELECT constraint_name, constraint_type, table_name,
       PARSE_JSON(constraint_properties) AS props
FROM <DB>.INFORMATION_SCHEMA.TABLE_CONSTRAINTS
WHERE constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE');

-- Sample values (for enum detection, small limit)
SELECT DISTINCT <col> FROM <table> LIMIT 20;
```

**Output:** RAW_CONCEPTS table with one row per database, schema, and table. Contains raw metadata as structured columns (not VARIANT).

### Step 2: ENRICH (per domain, cost-tiered)

AI-enrich raw concepts using the cost pyramid. See `enrich-pipeline.md` for full details.

**Tier 0 — Free heuristics:**
- Column name pattern matching (_ID → key, _DATE → dimension, AMOUNT → metric)
- Comment parsing (dbt docs, Snowflake COMMENT ON)
- FK inference from naming conventions (e.g., ORDER_ID in both ORDERS and ORDER_ITEMS)

**Tier 1 — AI_CLASSIFY ($):**
- Ambiguous column role classification (is STATUS a dimension or filter?)
- Table purpose classification (fact, dimension, bridge, staging, reference)

**Tier 2 — AI_EXTRACT ($$):**
- Domain/purpose extraction for undocumented tables
- Business description generation from column patterns

**Tier 3 — AI_COMPLETE ($$$):**
- VARIANT path interpretation
- Cross-database relationship inference
- Concept synthesis (combining table-level concepts into higher-order business concepts)

**Output:** CONCEPTS table with enriched metadata, descriptions, keywords, and structured YAML payloads.

### Step 3: INDEX (per domain)

Create a Cortex Search Service over the CONCEPTS table.

```sql
CREATE OR REPLACE CORTEX SEARCH SERVICE <DOMAIN>_META.META.<DOMAIN>_SEARCH
  ON search_content
  ATTRIBUTES concept_name, concept_level, domain, source_database, source_schema
  WAREHOUSE = <WH>
  TARGET_LAG = '1 hour'
AS (
  SELECT
    concept_name,
    concept_level,
    domain,
    source_database,
    source_schema,
    search_content,
    tables_yaml,
    join_keys_yaml,
    metrics_yaml,
    sample_values,
    is_enum
  FROM <DOMAIN>_META.META.CONCEPTS
  WHERE is_active = TRUE
);
```

### Step 4: SEARCH (per question, ~100ms)

Query hits the domain CSS (or master CSS for cross-domain). Returns top-K concept rows with structured payloads.

```python
from snowflake.core import Root
root = Root(session)
search_service = root.databases["DOMAIN_META"].schemas["META"].cortex_search_services["DOMAIN_SEARCH"]

results = search_service.search(
    query="monthly revenue by product category",
    columns=["concept_name", "concept_level", "tables_yaml", "join_keys_yaml", "metrics_yaml"],
    filter={"@eq": {"concept_level": "table"}},
    limit=10
)
```

### Step 5: ASSEMBLE (~100-200ms)

Deduplicate tables from search results, resolve join paths, build minimal SV-shaped context.

1. Extract unique table FQNs from all returned concept rows
2. For each table pair, check RELATIONSHIPS for known join paths
3. Build minimal column set: only columns referenced in concepts + join keys
4. Format as Cortex Analyst-compatible context (SV YAML or prompt context)

### Step 6: QUERY

Route assembled context to Cortex Analyst for SQL generation. Two approaches:

**Prompt-based (simpler, faster):**
- Inject assembled schema context into system prompt
- Use AI_COMPLETE with claude-3-5-sonnet or similar
- Best for ad-hoc exploration

**Ephemeral SV (more structured):**
- CREATE OR REPLACE SEMANTIC VIEW with assembled tables/columns
- Route question through Cortex Analyst API
- Best for repeated query patterns (graduates to curated SV)

### Step 7: EXECUTE

Run generated SQL, return results. Log concept usage for feedback loop.

```sql
INSERT INTO <DOMAIN>_META.META.QUERY_LOG (
  question, concepts_used, tables_used, sql_generated,
  row_count, execution_time_ms, user_name, timestamp
)
VALUES (:question, :concepts, :tables, :sql, :rows, :ms, CURRENT_USER(), CURRENT_TIMESTAMP());
```

---

## CONCEPTS Table DDL

```sql
CREATE TABLE <DOMAIN>_META.META.RAW_CONCEPTS (
  concept_id VARCHAR DEFAULT UUID_STRING(),
  concept_name VARCHAR NOT NULL,
  concept_level VARCHAR NOT NULL,  -- 'database', 'schema', 'table'
  domain VARCHAR NOT NULL,
  source_database VARCHAR,
  source_schema VARCHAR,
  source_table VARCHAR,
  
  -- Raw metadata (from CRAWL)
  table_type VARCHAR,
  row_count NUMBER,
  bytes NUMBER,
  clustering_key VARCHAR,
  comment VARCHAR,
  created TIMESTAMP_NTZ,
  last_altered TIMESTAMP_NTZ,
  owner VARCHAR,
  is_transient BOOLEAN,
  is_managed_access BOOLEAN,
  
  -- Column metadata (table-level only)
  columns_json VARIANT,        -- [{name, type, nullable, comment, ordinal}]
  constraints_json VARIANT,    -- [{name, type, columns, ref_table, ref_columns}]
  sample_values_json VARIANT,  -- {col_name: [val1, val2, ...]}
  
  -- Crawl metadata
  crawl_timestamp TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  metadata_hash VARCHAR,       -- for drift detection
  
  PRIMARY KEY (concept_id)
);

CREATE TABLE <DOMAIN>_META.META.CONCEPTS (
  concept_id VARCHAR DEFAULT UUID_STRING(),
  concept_name VARCHAR NOT NULL,
  concept_level VARCHAR NOT NULL,
  domain VARCHAR NOT NULL,
  source_database VARCHAR,
  source_schema VARCHAR,
  source_table VARCHAR,
  
  -- Enriched content (from ENRICH)
  description VARCHAR,
  keywords ARRAY,
  search_content VARCHAR,      -- concatenated searchable text for CSS
  
  -- Structured payloads (YAML strings for Cortex Analyst compatibility)
  tables_yaml VARCHAR,         -- table FQNs, PKs, relevant columns with types and roles
  join_keys_yaml VARCHAR,      -- cross-table and cross-database relationships
  metrics_yaml VARCHAR,        -- pre-defined aggregations
  sample_values VARCHAR,       -- representative values for literal matching
  is_enum BOOLEAN DEFAULT FALSE,
  
  -- Enrichment metadata
  enrichment_tier NUMBER,      -- 0=free, 1=classify, 2=extract, 3=complete
  enrichment_quality_score NUMBER(3,2),  -- 0.00-1.00
  enrichment_timestamp TIMESTAMP_NTZ,
  
  -- State
  is_active BOOLEAN DEFAULT TRUE,
  object_state VARCHAR DEFAULT 'KNOWN_CURRENT',
  
  -- Audit
  created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  
  PRIMARY KEY (concept_id)
);
```

## OBJECT_STATE Table DDL

```sql
CREATE TABLE <DOMAIN>_META.META.OBJECT_STATE (
  object_fqn VARCHAR NOT NULL,           -- DB.SCHEMA or DB.SCHEMA.TABLE
  object_level VARCHAR NOT NULL,         -- 'database', 'schema', 'table'
  object_state VARCHAR NOT NULL,         -- see six-state model
  concept_id VARCHAR,                    -- FK to CONCEPTS (NULL for shadow)
  
  -- Detection metadata
  first_seen TIMESTAMP_NTZ,
  last_seen TIMESTAMP_NTZ,
  last_access TIMESTAMP_NTZ,            -- from ACCESS_HISTORY
  access_count_30d NUMBER DEFAULT 0,
  distinct_users_30d NUMBER DEFAULT 0,
  
  -- Drift detection
  metadata_hash VARCHAR,
  previous_hash VARCHAR,
  drift_detected_at TIMESTAMP_NTZ,
  drift_details VARCHAR,
  
  -- Triage
  triage_action VARCHAR,                -- 'onboard', 'ignore', 'defer', 're-enrich', NULL
  triage_reason VARCHAR,
  triaged_by VARCHAR,
  triaged_at TIMESTAMP_NTZ,
  
  -- Audit
  updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  
  PRIMARY KEY (object_fqn)
);
```

## RELATIONSHIPS Table DDL

```sql
CREATE TABLE <DOMAIN>_META.META.RELATIONSHIPS (
  relationship_id VARCHAR DEFAULT UUID_STRING(),
  source_concept_id VARCHAR NOT NULL,
  target_concept_id VARCHAR NOT NULL,
  relationship_type VARCHAR NOT NULL,    -- 'FK', 'INFERRED_FK', 'SHARED_KEY', 'SEMANTIC'
  
  source_table VARCHAR NOT NULL,
  source_column VARCHAR NOT NULL,
  target_table VARCHAR NOT NULL,
  target_column VARCHAR NOT NULL,
  
  confidence NUMBER(3,2),                -- 0.00-1.00 (1.0 for declared FKs)
  detection_method VARCHAR,              -- 'CONSTRAINT', 'NAME_MATCH', 'AI_INFERRED', 'MANUAL'
  
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  
  PRIMARY KEY (relationship_id)
);
```

## DOMAIN_CONFIG Table DDL

```sql
CREATE TABLE <DOMAIN>_META.META.DOMAIN_CONFIG (
  config_key VARCHAR NOT NULL,
  config_value VARIANT NOT NULL,
  updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (config_key)
);

-- Example configs:
-- domain_name: 'SALESFORCE'
-- source_databases: ['SF_SHARE_1', 'SF_SHARE_2', 'SF_SHARE_3', 'SF_SHARE_4']
-- enrichment_max_tier: 2
-- enrichment_daily_budget_credits: 5.0
-- auto_onboard_schemas: ['PUBLIC', 'CORE']
-- ignore_schemas: ['INFORMATION_SCHEMA', 'SCRATCH']
-- refresh_schedule: '0 6 * * *'
-- watch_enabled: true
-- watch_auto_onboard: false
```
