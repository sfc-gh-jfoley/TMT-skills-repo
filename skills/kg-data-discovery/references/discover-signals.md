# Discover Signals

Complete inventory of free ACCOUNT_USAGE signals available for KG discovery. Organized by category. All queries are zero AI cost.

## Category 1: Schema Metadata

| View | Signal | Use In KG |
|------|--------|-----------|
| `DATABASES` | name, owner, type, comment, created, transient | Database-level concepts, domain clustering |
| `SCHEMATA` | name, owner, comment, managed_access, retention_time | Schema-level concepts, access patterns |
| `TABLES` | name, type, row_count, bytes, clustering_key, comment, created, last_altered | Table-level concepts, freshness, stale detection |
| `COLUMNS` | name, type, nullable, default, comment, ordinal | Column metadata, type classification |
| `TABLE_CONSTRAINTS` | PK, FK, UNIQUE constraints | Relationship inference (free FKs) |
| `VIEWS` | name, definition, is_secure, is_materialized | View detection (may skip for KG) |

### Key Queries

```sql
-- Tables with comments (well-documented, light enrichment needed)
SELECT table_catalog, table_schema, table_name, comment
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE deleted IS NULL AND comment IS NOT NULL AND comment != '';

-- Tables WITHOUT comments (need AI enrichment)
SELECT table_catalog, table_schema, table_name, row_count
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE deleted IS NULL AND (comment IS NULL OR comment = '')
  AND table_schema != 'INFORMATION_SCHEMA';

-- Column type distribution (helps estimate enrichment complexity)
SELECT data_type, COUNT(*) AS col_count
FROM SNOWFLAKE.ACCOUNT_USAGE.COLUMNS
WHERE deleted IS NULL
GROUP BY 1
ORDER BY 2 DESC;

-- VARIANT columns (need Tier 3 enrichment)
SELECT table_catalog, table_schema, table_name, column_name
FROM SNOWFLAKE.ACCOUNT_USAGE.COLUMNS
WHERE data_type = 'VARIANT' AND deleted IS NULL;
```

## Category 2: Data Shape & Storage

| View | Signal | Use In KG |
|------|--------|-----------|
| `TABLE_STORAGE_METRICS` | active_bytes, time_travel_bytes, failsafe_bytes, retained_for_clone_bytes | Storage cost analysis, stale data detection |
| `TABLES.clustering_key` | Clustering key columns | Physical layout hints, common query patterns |

### Key Queries

```sql
-- Storage distribution
SELECT
  id,
  table_catalog,
  table_schema,
  table_name,
  active_bytes / POWER(1024, 3) AS active_gb,
  time_travel_bytes / POWER(1024, 3) AS tt_gb,
  failsafe_bytes / POWER(1024, 3) AS fs_gb,
  clone_bytes / POWER(1024, 3) AS clone_gb
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
WHERE active_bytes > 0
ORDER BY active_bytes DESC
LIMIT 50;

-- Clustered tables (indicates important/optimized tables)
SELECT table_catalog, table_schema, table_name, clustering_key
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE clustering_key IS NOT NULL AND deleted IS NULL;
```

## Category 3: Usage & Access

| View | Signal | Use In KG |
|------|--------|-----------|
| `ACCESS_HISTORY` | base_objects_accessed, direct_objects_accessed, user_name | Table popularity, user patterns, join patterns |
| `QUERY_HISTORY` | query_text, database_name, user_name, warehouse_name, execution_time | Query patterns, common JOINs, performance |
| `LOGIN_HISTORY` | user_name, client_type, first_authentication_factor | Active users, tool ecosystem |

### Key Queries

```sql
-- Most accessed tables (30 days)
SELECT
  base.value:objectName::VARCHAR AS table_fqn,
  base.value:objectDomain::VARCHAR AS object_type,
  COUNT(DISTINCT query_id) AS query_count,
  COUNT(DISTINCT user_name) AS distinct_users
FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY,
  LATERAL FLATTEN(input => base_objects_accessed) base
WHERE query_start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1, 2
ORDER BY query_count DESC
LIMIT 50;

-- Common table co-access (tables queried together = likely join candidates)
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
  COUNT(DISTINCT a.query_id) AS co_access_count
FROM table_queries a
JOIN table_queries b ON a.query_id = b.query_id AND a.table_fqn < b.table_fqn
GROUP BY 1, 2
HAVING co_access_count >= 5
ORDER BY co_access_count DESC
LIMIT 50;

-- Query patterns by database
SELECT
  database_name,
  query_type,
  COUNT(*) AS query_count,
  AVG(total_elapsed_time) / 1000 AS avg_seconds,
  COUNT(DISTINCT user_name) AS distinct_users
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
  AND database_name IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, query_count DESC;
```

## Category 4: Governance & Dependencies

| View | Signal | Use In KG |
|------|--------|-----------|
| `OBJECT_DEPENDENCIES` | referencing/referenced objects | View→table deps, cross-schema refs |
| `GRANTS_TO_ROLES` | privilege, grantee, object | Access patterns, role-based domain hints |
| `GRANTS_TO_USERS` | privilege, grantee, object | Per-user access |
| `TAGS` / `TAG_REFERENCES` | tag name, tag value | Existing governance tags = free enrichment |
| `MASKING_POLICIES` | policy assignments | PII/sensitive data indicators |

### Key Queries

```sql
-- Object dependencies (views referencing tables, procs referencing tables)
SELECT
  referencing_database || '.' || referencing_schema || '.' || referencing_object_name AS referencing_fqn,
  referenced_database || '.' || referenced_schema || '.' || referenced_object_name AS referenced_fqn,
  referencing_object_domain,
  referenced_object_domain,
  dependency_type
FROM SNOWFLAKE.ACCOUNT_USAGE.OBJECT_DEPENDENCIES
ORDER BY referencing_fqn;

-- Existing tags (free enrichment!)
SELECT
  tag_database, tag_schema, tag_name, tag_value,
  object_database, object_schema, object_name, column_name,
  domain
FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
WHERE tag_database IS NOT NULL
ORDER BY object_database, object_schema, object_name;

-- Role-based access (domain clustering signal)
SELECT
  grantee_name AS role_name,
  ARRAY_AGG(DISTINCT table_catalog) AS databases_accessed
FROM SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_ROLES
WHERE privilege IN ('SELECT', 'INSERT', 'UPDATE')
  AND table_catalog IS NOT NULL
  AND deleted_on IS NULL
GROUP BY 1
HAVING COUNT(DISTINCT table_catalog) > 1;

-- Masking policy assignments (PII signal)
SELECT
  ref_database_name || '.' || ref_schema_name || '.' || ref_entity_name AS table_fqn,
  ref_column_name,
  policy_name
FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
WHERE policy_kind = 'MASKING_POLICY';
```

## Category 5: Micropartition & Physical Metadata

These signals require per-table queries (not bulk ACCOUNT_USAGE). Use selectively on high-priority tables.

```sql
-- Clustering depth and overlap (partition pruning signal)
SELECT SYSTEM$CLUSTERING_INFORMATION('<TABLE_FQN>', '(<clustering_columns>)');

-- Result includes:
-- cluster_by_keys, total_partition_count, total_constant_partition_count,
-- average_overlaps, average_depth, partition_depth_histogram

-- Useful for: identifying well-clustered tables (high constant partition count)
-- and poorly-clustered tables (high overlap = query performance issues)
```

## Signal Priority for KG

| Priority | Signals | Cost | When |
|----------|---------|------|------|
| **Always** | DATABASES, TABLES, COLUMNS, CONSTRAINTS | Free | Every crawl |
| **Always** | ACCESS_HISTORY, QUERY_HISTORY (30d window) | Free | Every discover/refresh |
| **If available** | TAG_REFERENCES, MASKING_POLICIES | Free | Discover phase |
| **If available** | OBJECT_DEPENDENCIES | Free | Relationship inference |
| **Selective** | TABLE_STORAGE_METRICS | Free | Stale data analysis, cost planning |
| **Selective** | CLUSTERING_INFORMATION | Free (per table) | Physical profiling on key tables |
| **On request** | LOGIN_HISTORY | Free | User ecosystem analysis |
