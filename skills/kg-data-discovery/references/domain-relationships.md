# Domain Relationships

Relationship table design, FK inference, and cross-database join path resolution.

## Relationship Types

| Type | Confidence | Detection Method | Example |
|------|------------|-----------------|---------|
| FK | 1.00 | `TABLE_CONSTRAINTS` (declared FKs) | ORDERS.CUSTOMER_ID → CUSTOMERS.ID |
| INFERRED_FK | 0.70-0.95 | Column name + type matching | EVENTS.USER_ID likely → USERS.USER_ID |
| SHARED_KEY | 0.50-0.80 | Same column name + type in multiple tables | Both tables have ACCOUNT_ID |
| SEMANTIC | 0.30-0.70 | AI-inferred (Tier 3) | PRODUCTS.CATEGORY relates to CATEGORIES.NAME |

## Detection Methods

### Method 1: Declared Foreign Keys (Free, Confidence 1.0)

```sql
SELECT
  fk.table_catalog || '.' || fk.table_schema || '.' || fk.table_name AS source_table,
  kcu.column_name AS source_column,
  fk.table_catalog || '.' || rc.unique_constraint_schema || '.' ||
    ccu.table_name AS target_table,
  ccu.column_name AS target_column,
  'FK' AS relationship_type,
  1.00 AS confidence,
  'CONSTRAINT' AS detection_method
FROM {DB}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS fk
JOIN {DB}.INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
  ON fk.constraint_name = rc.constraint_name
  AND fk.constraint_schema = rc.constraint_schema
JOIN {DB}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
  ON fk.constraint_name = kcu.constraint_name
  AND fk.constraint_schema = kcu.constraint_schema
JOIN {DB}.INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
  ON rc.unique_constraint_name = ccu.constraint_name
WHERE fk.constraint_type = 'FOREIGN KEY';
```

### Method 2: Name-Based Inference (Free, Confidence 0.70-0.95)

```sql
-- Find columns ending in _ID that match PK columns of other tables
WITH pk_columns AS (
  SELECT
    table_catalog || '.' || table_schema || '.' || table_name AS table_fqn,
    column_name,
    table_name
  FROM {DB}.INFORMATION_SCHEMA.COLUMNS
  WHERE ordinal_position = 1  -- simplified: first column often PK
),
fk_candidates AS (
  SELECT
    c.table_catalog || '.' || c.table_schema || '.' || c.table_name AS source_table,
    c.column_name AS source_column,
    pk.table_fqn AS target_table,
    pk.column_name AS target_column
  FROM {DB}.INFORMATION_SCHEMA.COLUMNS c
  JOIN pk_columns pk
    ON (
      c.column_name = pk.table_name || '_ID'     -- e.g., CUSTOMER_ID → CUSTOMER table
      OR c.column_name = pk.column_name           -- e.g., both have ACCOUNT_ID
    )
  WHERE c.table_catalog || '.' || c.table_schema || '.' || c.table_name != pk.table_fqn
    AND c.data_type IN ('NUMBER', 'VARCHAR', 'TEXT')
)
SELECT *, 'INFERRED_FK' AS relationship_type, 0.80 AS confidence
FROM fk_candidates;
```

### Method 3: Co-Access Pattern (Free, Confidence from frequency)

```sql
-- Tables frequently queried together are likely related
WITH table_queries AS (
  SELECT
    query_id,
    base.value:objectName::VARCHAR AS table_fqn
  FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY,
    LATERAL FLATTEN(input => base_objects_accessed) base
  WHERE query_start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
)
SELECT
  a.table_fqn AS table_a,
  b.table_fqn AS table_b,
  COUNT(DISTINCT a.query_id) AS co_queries,
  'SHARED_KEY' AS relationship_type,
  LEAST(co_queries / 100.0, 0.80) AS confidence,
  'CO_ACCESS' AS detection_method
FROM table_queries a
JOIN table_queries b ON a.query_id = b.query_id AND a.table_fqn < b.table_fqn
GROUP BY 1, 2
HAVING co_queries >= 5
ORDER BY co_queries DESC;
```

### Method 4: AI-Inferred (Tier 3, Confidence varies)

Use AI_COMPLETE to analyze column semantics when names don't match but data relationships exist. Only for important cross-domain relationships.

## Populating RELATIONSHIPS

```sql
INSERT INTO {DOMAIN}_META.META.RELATIONSHIPS (
  source_concept_id, target_concept_id, relationship_type,
  source_table, source_column, target_table, target_column,
  confidence, detection_method
)
SELECT
  sc.concept_id,
  tc.concept_id,
  :relationship_type,
  :source_table, :source_column,
  :target_table, :target_column,
  :confidence, :detection_method
FROM {DOMAIN}_META.META.CONCEPTS sc
JOIN {DOMAIN}_META.META.CONCEPTS tc
  ON sc.source_table = :source_table_name
  AND tc.source_table = :target_table_name;
```

## Cross-Database Join Resolution

When assembling context for a query that spans databases:

1. Search returns concept rows from multiple source databases
2. Check RELATIONSHIPS for edges between those databases
3. If no explicit relationship exists, check SHARED_KEY relationships
4. If still no path, flag as "unconnected" and let Cortex Analyst attempt column-name matching

```python
def resolve_join_path(tables, relationships_df):
    paths = []
    for i, t1 in enumerate(tables):
        for t2 in tables[i+1:]:
            rel = relationships_df[
                ((relationships_df.source_table == t1) & (relationships_df.target_table == t2)) |
                ((relationships_df.source_table == t2) & (relationships_df.target_table == t1))
            ]
            if not rel.empty:
                best = rel.sort_values('confidence', ascending=False).iloc[0]
                paths.append({
                    'table_a': t1, 'table_b': t2,
                    'join_on': f"{best.source_column} = {best.target_column}",
                    'confidence': best.confidence
                })
    return paths
```
