# Core Session

Session start workflow for KG Data Discovery. Run this before any operation.

## Session Start Workflow

### 1. Connection Check

```sql
SELECT CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA();
```

**Required roles:** SYSADMIN or equivalent (needs ACCOUNT_USAGE access, CREATE DATABASE, CREATE CORTEX SEARCH SERVICE).

If role lacks ACCOUNT_USAGE access:
```sql
USE ROLE ACCOUNTADMIN;
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <user_role>;
```

### 2. Detect Existing KG

Check if any KG infrastructure already exists in the account:

```sql
-- Check for existing domain META databases
SHOW DATABASES LIKE '%_META';

-- Check for existing Cortex Search Services (KG convention: *_SEARCH in META schema)
SHOW CORTEX SEARCH SERVICES IN ACCOUNT;

-- Check for existing CONCEPTS tables
SELECT table_catalog, table_schema, table_name, row_count
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE table_name = 'CONCEPTS'
  AND deleted IS NULL
ORDER BY last_altered DESC;

-- Check for existing KG Router (from knowledge_graph_router project)
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE table_catalog = 'SNOWFLAKE_INTELLIGENCE'
  AND table_schema = 'KNOWLEDGE_GRAPH'
  AND deleted IS NULL;
```

### 3. Report State

Based on detection, report one of:

| State | Description | Next Action |
|-------|-------------|-------------|
| **No KG** | No META databases, no CONCEPTS tables | Start with DISCOVER (Step 0) |
| **KG Router exists** | SNOWFLAKE_INTELLIGENCE.KNOWLEDGE_GRAPH found | Can build on existing router, extend with domain-specific KGs |
| **Domain KGs exist** | One or more *_META databases found | Inventory existing domains, check health, identify gaps |
| **Full KG** | Multiple domains + master CSS | Check freshness, run WATCH for drift/shadow |

### 4. Scope Confirmation

Before proceeding, confirm the target scope with the user:

- **Account-wide discovery** — Run DISCOVER first, then plan domain onboarding
- **Specific database** — Skip DISCOVER, go directly to ONBOARD
- **Specific domain** — Use existing domain boundaries if KG exists
- **Maintenance** — Check domain health, run WATCH, refresh stale concepts

## Session Context Variables

Track these throughout the session:

```
DOMAIN_NAME:       (set during ONBOARD or detected from existing KG)
META_DATABASE:     {DOMAIN_NAME}_META
META_SCHEMA:       META
SEARCH_SERVICE:    {DOMAIN_NAME}_SEARCH
SOURCE_DATABASES:  [list of databases in this domain]
WAREHOUSE:         (session warehouse)
ENRICHMENT_TIER:   (0-3, set based on budget and data source type)
```

## Reconnection / Resume

If a session is interrupted, check the investigation diary (if one was started) and the OBJECT_STATE table for the domain to understand where work left off:

```sql
-- Check last crawl timestamp
SELECT MAX(crawl_timestamp) FROM <DOMAIN>_META.META.RAW_CONCEPTS;

-- Check enrichment progress
SELECT enrichment_tier, COUNT(*), AVG(enrichment_quality_score)
FROM <DOMAIN>_META.META.CONCEPTS
GROUP BY enrichment_tier;

-- Check object state distribution
SELECT object_state, object_level, COUNT(*)
FROM <DOMAIN>_META.META.OBJECT_STATE
GROUP BY 1, 2
ORDER BY 1, 2;
```

## Error Handling

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `ACCOUNT_USAGE access denied` | Role lacks IMPORTED PRIVILEGES on SNOWFLAKE | Grant via ACCOUNTADMIN |
| `Warehouse suspended` | No active warehouse | `ALTER WAREHOUSE <WH> RESUME` |
| `CSS creation failed` | Missing warehouse or empty source table | Verify CONCEPTS has rows, warehouse is active |
| `AI function error` | Model not available or credit limit | Check CORTEX_ENABLED, credit balance |
| `Insufficient privileges` | Role can't create objects in META database | Grant CREATE SCHEMA, CREATE TABLE on META database |
