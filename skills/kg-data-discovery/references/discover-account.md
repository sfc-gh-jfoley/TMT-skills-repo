# Discover Account

Account-wide profiling workflow for brownfield Snowflake accounts. Run DISCOVER before onboarding any domains in accounts with 50+ tables.

## Purpose

DISCOVER answers: "What do we have, how is it used, and where should we start?" — entirely with free SQL against ACCOUNT_USAGE. Zero AI cost.

## Workflow

### Phase 1: Account Profile

```sql
-- Database inventory
SELECT
  database_name,
  database_owner,
  comment,
  created,
  is_transient,
  type  -- STANDARD, IMPORTED DATABASE (shares), etc.
FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES
WHERE deleted IS NULL
ORDER BY database_name;

-- Table inventory
SELECT
  table_catalog AS database_name,
  table_schema,
  COUNT(*) AS table_count,
  SUM(row_count) AS total_rows,
  SUM(bytes) / POWER(1024, 3) AS total_gb,
  MIN(created) AS earliest_table,
  MAX(last_altered) AS latest_change
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE deleted IS NULL
  AND table_schema != 'INFORMATION_SCHEMA'
GROUP BY 1, 2
ORDER BY total_gb DESC;

-- Account summary
SELECT
  COUNT(DISTINCT table_catalog) AS database_count,
  COUNT(DISTINCT table_catalog || '.' || table_schema) AS schema_count,
  COUNT(*) AS table_count,
  SUM(row_count) AS total_rows,
  SUM(bytes) / POWER(1024, 4) AS total_tb
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE deleted IS NULL
  AND table_schema != 'INFORMATION_SCHEMA';
```

### Phase 2: Usage Signals

```sql
-- Most queried tables (last 30 days)
SELECT
  base.value:objectName::VARCHAR AS table_fqn,
  COUNT(DISTINCT query_id) AS query_count,
  COUNT(DISTINCT user_name) AS distinct_users,
  MAX(query_start_time) AS last_accessed
FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY,
  LATERAL FLATTEN(input => base_objects_accessed) base
WHERE query_start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY query_count DESC
LIMIT 100;

-- Stale tables (no access in 90+ days)
WITH accessed AS (
  SELECT DISTINCT
    base.value:objectName::VARCHAR AS table_fqn
  FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY,
    LATERAL FLATTEN(input => base_objects_accessed) base
  WHERE query_start_time >= DATEADD('day', -90, CURRENT_TIMESTAMP())
)
SELECT
  t.table_catalog || '.' || t.table_schema || '.' || t.table_name AS table_fqn,
  t.row_count,
  t.bytes / POWER(1024, 3) AS gb,
  t.last_altered
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES t
LEFT JOIN accessed a ON a.table_fqn = t.table_catalog || '.' || t.table_schema || '.' || t.table_name
WHERE a.table_fqn IS NULL
  AND t.deleted IS NULL
  AND t.table_schema != 'INFORMATION_SCHEMA'
  AND t.row_count > 0
ORDER BY t.bytes DESC;

-- Active users by database (last 30 days)
SELECT
  database_name,
  COUNT(DISTINCT user_name) AS active_users,
  COUNT(DISTINCT query_id) AS query_count,
  SUM(credits_used_cloud_services) AS cloud_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND database_name IS NOT NULL
GROUP BY 1
ORDER BY query_count DESC;
```

### Phase 3: Domain Clustering

Auto-propose domain boundaries by analyzing:

1. **Database grouping** (default: 1 database = 1 domain)
2. **Shared ownership** — databases owned by the same role likely belong together
3. **Cross-references** — tables referencing each other via FK or naming patterns
4. **Access patterns** — databases queried by the same user groups

```sql
-- FK-based clustering: tables that reference each other
SELECT
  tc.table_catalog || '.' || tc.table_schema AS source_schema,
  rc.unique_constraint_catalog || '.' || rc.unique_constraint_schema AS target_schema
FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
  ON rc.constraint_name = tc.constraint_name
WHERE source_schema != target_schema;

-- Ownership clustering
SELECT
  database_owner,
  ARRAY_AGG(DISTINCT database_name) AS databases
FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES
WHERE deleted IS NULL
GROUP BY 1
HAVING COUNT(*) > 1;
```

### Phase 4: Priority Ranking

Score each potential domain on:

| Signal | Weight | Source |
|--------|--------|--------|
| Query volume (30d) | 30% | QUERY_HISTORY |
| Distinct users (30d) | 25% | ACCESS_HISTORY |
| Data freshness (last_altered) | 20% | TABLES |
| Table count | 15% | TABLES |
| Storage size | 10% | TABLE_STORAGE_METRICS |

```sql
-- Priority score per database
WITH query_stats AS (
  SELECT database_name,
    COUNT(DISTINCT query_id) AS queries_30d,
    COUNT(DISTINCT user_name) AS users_30d
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
  WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
    AND database_name IS NOT NULL
  GROUP BY 1
),
table_stats AS (
  SELECT table_catalog AS database_name,
    COUNT(*) AS table_count,
    SUM(bytes) AS total_bytes,
    MAX(last_altered) AS latest_change
  FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
  WHERE deleted IS NULL AND table_schema != 'INFORMATION_SCHEMA'
  GROUP BY 1
)
SELECT
  t.database_name,
  t.table_count,
  ROUND(t.total_bytes / POWER(1024, 3), 2) AS gb,
  t.latest_change,
  COALESCE(q.queries_30d, 0) AS queries_30d,
  COALESCE(q.users_30d, 0) AS users_30d,
  -- Composite priority score (higher = onboard first)
  ROUND(
    (COALESCE(q.queries_30d, 0) / NULLIF(MAX(q.queries_30d) OVER (), 0)) * 0.30 +
    (COALESCE(q.users_30d, 0) / NULLIF(MAX(q.users_30d) OVER (), 0)) * 0.25 +
    (DATEDIFF('day', t.latest_change, CURRENT_TIMESTAMP()) < 7)::INT * 0.20 +
    (t.table_count / NULLIF(MAX(t.table_count) OVER (), 0)) * 0.15 +
    (t.total_bytes / NULLIF(MAX(t.total_bytes) OVER (), 0)) * 0.10
  , 2) AS priority_score
FROM table_stats t
LEFT JOIN query_stats q ON t.database_name = q.database_name
ORDER BY priority_score DESC;
```

### Phase 5: Rollout Plan

Present the user with:

1. **Domain map** — proposed groupings with rationale
2. **Priority ranking** — ordered by composite score
3. **Phased plan:**
   - Phase 1: Top 2-3 domains (highest usage)
   - Phase 2: Next tier (moderate usage)
   - Phase 3: Remaining (low usage, archival, scratch)
4. **Stale data report** — candidates for archive/cleanup
5. **Estimated enrichment cost** — per domain, based on table count and documentation level

## Output Format

Present as a summary table:

```
| # | Domain          | Databases          | Tables | GB    | Users | Queries | Priority | Est. Cost |
|---|----------------|--------------------|--------|-------|-------|---------|----------|-----------|
| 1 | Sales          | SALES_DB           | 45     | 12.3  | 28    | 15,420  | 0.92     | ~0.5 cr   |
| 2 | Product        | PRODUCT_DB, CATALOG| 78     | 45.1  | 15    | 8,230   | 0.78     | ~1.0 cr   |
| 3 | Marketing      | MARKETING_SHARE    | 32     | 3.2   | 8     | 2,100   | 0.45     | ~0.8 cr   |
| — | Scratch/Temp   | SCRATCH, DEV_*     | 120    | 0.5   | 3     | 450     | 0.08     | skip      |
```
