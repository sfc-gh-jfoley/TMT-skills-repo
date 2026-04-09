# Watch — Shadow Detection & Drift Monitoring

Continuous monitoring that detects new (shadow) objects and schema drift in known objects.

## Six Object States

| State | In KG? | Exists? | Metadata Current? | Action |
|-------|--------|---------|-------------------|--------|
| KNOWN_CURRENT | Yes | Yes | Yes | Healthy |
| KNOWN_DRIFTED | Yes | Yes | No (schema changed) | Re-crawl, delta enrich |
| KNOWN_DELETED | Yes | No | — | Mark inactive |
| ONBOARDED_INCORRECTLY | Yes | Yes | Partial/wrong | Re-enrich, validate |
| SHADOW_ACTIVE | No | Yes | — (has queries) | Alert, triage |
| SHADOW_INACTIVE | No | Yes | — (no queries) | Log, monitor |

## WATCH Procedure

Runs on schedule. Compares current account state against OBJECT_STATE + CONCEPTS.

### Three-Level Detection

**Database-level shadows:**
```sql
-- New databases not in any domain's OBJECT_STATE
SELECT database_name, database_owner, created
FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES d
WHERE d.deleted IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM {DOMAIN}_META.META.OBJECT_STATE os
    WHERE os.object_fqn = d.database_name AND os.object_level = 'database'
  )
  AND database_name NOT IN ('SNOWFLAKE', 'SNOWFLAKE_SAMPLE_DATA');
```

**Schema-level shadows:**
```sql
-- New schemas in tracked databases
SELECT catalog_name || '.' || schema_name AS schema_fqn, schema_owner
FROM {DB}.INFORMATION_SCHEMA.SCHEMATA s
WHERE schema_name NOT IN ('INFORMATION_SCHEMA')
  AND NOT EXISTS (
    SELECT 1 FROM {DOMAIN}_META.META.OBJECT_STATE os
    WHERE os.object_fqn = catalog_name || '.' || schema_name
    AND os.object_level = 'schema'
  );
```

**Table-level shadows:**
```sql
-- New tables in tracked schemas
SELECT
  t.table_catalog || '.' || t.table_schema || '.' || t.table_name AS table_fqn,
  t.row_count,
  t.bytes,
  t.created
FROM {DB}.INFORMATION_SCHEMA.TABLES t
WHERE t.table_schema NOT IN ('INFORMATION_SCHEMA')
  AND NOT EXISTS (
    SELECT 1 FROM {DOMAIN}_META.META.OBJECT_STATE os
    WHERE os.object_fqn = t.table_catalog || '.' || t.table_schema || '.' || t.table_name
    AND os.object_level = 'table'
  );
```

### Drift Detection

```sql
-- Tables where metadata hash diverged
SELECT
  os.object_fqn,
  os.metadata_hash AS known_hash,
  MD5(t.table_catalog || '.' || t.table_schema || '.' || t.table_name || t.row_count::VARCHAR || COALESCE(t.last_altered::VARCHAR, '')) AS current_hash
FROM {DOMAIN}_META.META.OBJECT_STATE os
JOIN {DB}.INFORMATION_SCHEMA.TABLES t
  ON os.object_fqn = t.table_catalog || '.' || t.table_schema || '.' || t.table_name
WHERE os.object_state = 'KNOWN_CURRENT'
  AND os.metadata_hash != MD5(t.table_catalog || '.' || t.table_schema || '.' || t.table_name || t.row_count::VARCHAR || COALESCE(t.last_altered::VARCHAR, ''));
```

### Activity Classification (Shadow Active vs Inactive)

```sql
-- Check ACCESS_HISTORY for shadow objects
WITH shadow_objects AS (
  SELECT object_fqn FROM {DOMAIN}_META.META.OBJECT_STATE WHERE object_state LIKE 'SHADOW%'
)
SELECT
  so.object_fqn,
  COUNT(DISTINCT ah.query_id) AS queries_30d,
  COUNT(DISTINCT ah.user_name) AS users_30d,
  MAX(ah.query_start_time) AS last_access
FROM shadow_objects so
LEFT JOIN SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY ah,
  LATERAL FLATTEN(input => ah.base_objects_accessed) base
ON base.value:objectName::VARCHAR = so.object_fqn
  AND ah.query_start_time >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY 1;

-- SHADOW_ACTIVE: queries_30d > 0
-- SHADOW_INACTIVE: queries_30d = 0
```

## Triage Rules

### Auto-Ignore
- Tables in SCRATCH or TEMP schemas
- Tables with `_TEMP_`, `_TMP_`, `_STAGING_` in name
- Transient tables with zero access in 30 days
- Tables with < 10 rows

### Auto-Alert (Notify)
- New databases appearing
- New schemas in production databases
- Shadow tables with > 100 queries in 30 days
- Shadow tables accessed by > 5 distinct users

### Auto-Flag (Needs Human Review)
- Known objects where column count changed (schema drift)
- Known objects where row count changed > 50% (data drift)
- Concepts with enrichment_quality_score < 0.3

### Auto-Onboard (Optional, for Trusted Domains)
- New tables in schemas listed in `auto_onboard_schemas` config
- Automatically: crawl → Tier 0 enrich → insert CONCEPTS → update CSS
- Requires `watch_auto_onboard = true` in DOMAIN_CONFIG

## WATCH Task

```sql
CREATE OR REPLACE PROCEDURE {DOMAIN}_META.META.RUN_WATCH()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
  -- 1. Detect shadow databases, schemas, tables
  -- 2. Detect drift in known objects
  -- 3. Classify shadows as active/inactive
  -- 4. Apply triage rules (auto-ignore, auto-alert, auto-flag)
  -- 5. Update OBJECT_STATE
  -- 6. If auto-onboard enabled, crawl + enrich new tables in trusted schemas
  -- 7. Return summary: {shadows: N, drifted: N, auto_onboarded: N, flagged: N}
  RETURN 'WATCH complete';
END;
$$;

CREATE OR REPLACE TASK {DOMAIN}_META.META.WATCH_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = 'USING CRON 0 */6 * * * America/New_York'
AS
  CALL {DOMAIN}_META.META.RUN_WATCH();
```

## Shadow Report

Present findings to user:

```
| # | Object | Level | State | Queries (30d) | Users | Action |
|---|--------|-------|-------|---------------|-------|--------|
| 1 | PROD.NEW_SCHEMA.EVENTS | table | SHADOW_ACTIVE | 2,340 | 12 | ⚠️ Recommend onboard |
| 2 | PROD.NEW_SCHEMA.EVENTS_STAGING | table | SHADOW_INACTIVE | 0 | 0 | Auto-ignored (staging) |
| 3 | DEV_DB | database | SHADOW_INACTIVE | 5 | 1 | Auto-ignored (dev) |
| 4 | PROD.CORE.CUSTOMERS | table | KNOWN_DRIFTED | 5,600 | 28 | 🔄 Re-crawl triggered |
```

## Alert Integration

For production deployments, connect WATCH alerts to notification channels:

```sql
CREATE OR REPLACE NOTIFICATION INTEGRATION KG_WATCH_ALERTS
  TYPE = QUEUE
  NOTIFICATION_PROVIDER = AWS_SNS
  AWS_SNS_TOPIC_ARN = 'arn:aws:sns:...'
  AWS_SNS_ROLE_ARN = 'arn:aws:iam::...';

-- Or use email:
CREATE OR REPLACE NOTIFICATION INTEGRATION KG_WATCH_EMAIL
  TYPE = EMAIL
  ALLOWED_RECIPIENTS = ('data-team@company.com');
```
