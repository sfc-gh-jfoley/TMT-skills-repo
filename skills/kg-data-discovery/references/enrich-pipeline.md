# Enrichment Pipeline

Cost-tiered AI enrichment: transform RAW_CONCEPTS into searchable, AI-enriched CONCEPTS.

## Enrichment Tiers

### Tier 0: Free Heuristics (Always Run)

Zero AI cost. Pattern-based enrichment from metadata alone.

**Column role classification (name patterns):**

```python
ROLE_PATTERNS = {
    'key': ['_ID', '_KEY', '_FK', '_PK', 'ID$'],
    'dimension': ['_NAME', '_TYPE', '_STATUS', '_CATEGORY', '_CODE', '_COUNTRY', '_REGION', '_CITY'],
    'metric': ['_AMOUNT', '_TOTAL', '_COUNT', '_SUM', '_AVG', '_RATE', '_PRICE', '_COST', '_REVENUE', '_QTY', '_QUANTITY'],
    'timestamp': ['_DATE', '_TIME', '_AT', '_TIMESTAMP', 'CREATED', 'UPDATED', 'MODIFIED', 'DELETED'],
    'flag': ['IS_', 'HAS_', '_FLAG', '_BOOL'],
    'text': ['_DESC', '_DESCRIPTION', '_COMMENT', '_NOTE', '_BODY', '_TEXT', '_MESSAGE'],
}
```

**Table type classification (name/schema patterns):**

```python
TABLE_TYPE_PATTERNS = {
    'fact': ['FACT_', 'FCT_', 'EVENTS', 'TRANSACTIONS', 'ORDERS', 'PAYMENTS'],
    'dimension': ['DIM_', 'DIMENSION_', 'LOOKUP_', 'REF_'],
    'bridge': ['BRIDGE_', 'XREF_', 'MAP_', 'LINK_'],
    'staging': ['STG_', 'STAGING_', 'RAW_', 'SRC_'],
    'mart': ['MART_', 'RPT_', 'REPORT_', 'ANALYTICS_'],
}
```

**Comment parsing:** Extract descriptions from existing Snowflake COMMENT ON or dbt docs.

**FK inference from naming:** If column X_ID exists in table A and table X has column ID, infer FK.

**Sample value enum detection:** If a VARCHAR column has < 25 distinct values sampled, mark `is_enum = TRUE`.

### Tier 1: AI_CLASSIFY ($)

For columns where Tier 0 heuristics are ambiguous.

```sql
SELECT SNOWFLAKE.CORTEX.AI_CLASSIFY(
  'Column STATUS in table ORDERS with values: PENDING, SHIPPED, DELIVERED, CANCELLED, RETURNED',
  ['dimension', 'metric', 'key', 'timestamp', 'flag']
) AS classified_role;
```

**When to use:**
- Column name doesn't match any Tier 0 pattern
- Column has values but unclear role (e.g., STATUS could be dimension or filter)

**Cost:** ~$0.001 per classification

### Tier 2: AI_EXTRACT ($$)

For tables/columns with no documentation.

```sql
SELECT SNOWFLAKE.CORTEX.AI_EXTRACT(
  'Table: FINANCE_DB.CORE.GL_ENTRIES. Columns: ENTRY_ID (NUMBER), ACCOUNT_CODE (VARCHAR), DEBIT (NUMBER), CREDIT (NUMBER), POSTING_DATE (DATE), FISCAL_YEAR (NUMBER), PERIOD (NUMBER), ENTITY (VARCHAR), DEPARTMENT (VARCHAR), PROJECT_CODE (VARCHAR), DESCRIPTION (VARCHAR), CREATED_BY (VARCHAR), CREATED_AT (TIMESTAMP)',
  ['table_purpose', 'business_domain', 'grain_description', 'key_metrics']
);
```

**When to use:**
- Table has no COMMENT
- Column names are cryptic or abbreviated
- Need business-level description for search content

**Cost:** ~$0.01 per extraction

### Tier 3: AI_COMPLETE ($$$)

For complex interpretation tasks.

```sql
SELECT SNOWFLAKE.CORTEX.AI_COMPLETE(
  'claude-3-5-sonnet',
  CONCAT(
    'Analyze this table schema and provide: 1) business purpose, 2) key dimensions, 3) key metrics, 4) likely join keys to other tables.\n\n',
    'Table: ', :table_fqn, '\n',
    'Columns:\n', :columns_json, '\n',
    'Sample data (5 rows):\n', :sample_data, '\n',
    'Other tables in same schema: ', :sibling_tables
  )
);
```

**When to use:**
- VARIANT columns needing path interpretation
- Cross-database relationship inference
- Concept synthesis (combining table-level signals into business concepts)

**Cost:** ~$0.02-0.10 per completion (depending on context size)

## Enrichment Output

Transform RAW_CONCEPTS into CONCEPTS:

```sql
INSERT INTO {DOMAIN}_META.META.CONCEPTS (
  concept_name, concept_level, domain,
  source_database, source_schema, source_table,
  description, keywords, search_content,
  tables_yaml, join_keys_yaml, metrics_yaml,
  sample_values, is_enum,
  enrichment_tier, enrichment_quality_score, enrichment_timestamp
)
SELECT
  rc.concept_name,
  rc.concept_level,
  rc.domain,
  rc.source_database,
  rc.source_schema,
  rc.source_table,
  :enriched_description,
  :enriched_keywords,
  -- Concatenated search content: name + description + keywords + column names + comments
  CONCAT(
    rc.concept_name, ' ',
    COALESCE(:enriched_description, ''), ' ',
    ARRAY_TO_STRING(COALESCE(:enriched_keywords, ARRAY_CONSTRUCT()), ' '), ' ',
    COALESCE(rc.comment, ''), ' ',
    -- Column names for table-level concepts
    COALESCE((SELECT LISTAGG(col.value:name::VARCHAR, ' ')
              FROM TABLE(FLATTEN(input => rc.columns_json)) col), '')
  ),
  :tables_yaml,
  :join_keys_yaml,
  :metrics_yaml,
  :sample_values,
  :is_enum,
  :max_tier_used,
  :quality_score,
  CURRENT_TIMESTAMP()
FROM {DOMAIN}_META.META.RAW_CONCEPTS rc
WHERE rc.concept_id = :concept_id;
```

## tables_yaml Format

For Cortex Analyst compatibility:

```yaml
- name: FINANCE_DB.CORE.GL_ENTRIES
  description: General ledger entries for financial accounting
  columns:
    - name: ENTRY_ID
      data_type: NUMBER
      role: key
      description: Primary key
    - name: ACCOUNT_CODE
      data_type: VARCHAR
      role: dimension
      description: GL account code
      sample_values: ["1000", "2000", "3000", "4000"]
    - name: DEBIT
      data_type: NUMBER
      role: metric
      description: Debit amount
    - name: POSTING_DATE
      data_type: DATE
      role: timestamp
      description: Date the entry was posted
```

## Quality Score Calculation

```python
def calculate_quality_score(concept):
    score = 0.0
    if concept.description and len(concept.description) > 20:
        score += 0.30
    if concept.keywords and len(concept.keywords) >= 3:
        score += 0.15
    if concept.tables_yaml:
        score += 0.20
    if concept.join_keys_yaml:
        score += 0.15
    if concept.metrics_yaml:
        score += 0.10
    if concept.sample_values:
        score += 0.10
    return score
```

## Batch Processing

For large domains (100+ tables), process enrichment in batches:

1. Sort tables by priority (most queried first)
2. Process in batches of 20 tables
3. Track credits consumed per batch
4. Stop if daily budget exceeded
5. Resume next day from where left off
