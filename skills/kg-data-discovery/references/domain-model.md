# Domain Model

Design patterns for KG domains — logical groupings of one or more databases.

## Convention

Each domain gets a META database and schema:

```
{DOMAIN_NAME}_META.META.*
```

Objects in the META schema:

| Object | Type | Purpose |
|--------|------|---------|
| RAW_CONCEPTS | Table | SQL-harvested metadata (DB, schema, table level) |
| CONCEPTS | Table | AI-enriched, searchable (all three levels) |
| RELATIONSHIPS | Table | Join paths (including cross-database) |
| OBJECT_STATE | Table | Current state of every known + shadow object |
| DOMAIN_CONFIG | Table | Enrichment settings, cost caps, source databases |
| {DOMAIN}_SEARCH | CSS | Cortex Search Service over CONCEPTS |

## Domain Boundary Patterns

### Pattern 1: Single Database (Default)

Most common. One database = one domain.

```
FINANCE_META.META.FINANCE_SEARCH  → covers FINANCE_DB
```

### Pattern 2: Multi-Database Domain

Multiple databases that share FK patterns and represent one logical data source.

```
SALESFORCE_META.META.SALESFORCE_SEARCH → covers SF_SHARE_1, SF_SHARE_2, SF_SHARE_3, SF_SHARE_4
```

Config:
```sql
INSERT INTO SALESFORCE_META.META.DOMAIN_CONFIG VALUES
  ('domain_name', '"SALESFORCE"'),
  ('source_databases', '["SF_SHARE_1", "SF_SHARE_2", "SF_SHARE_3", "SF_SHARE_4"]');
```

### Pattern 3: Sub-Domain (Schema-Level)

Carve out sub-domains within one database (large databases with distinct schema groups).

```
ANALYTICS_META.META.SALES_SEARCH      → covers ANALYTICS.SALES_*
ANALYTICS_META.META.MARKETING_SEARCH  → covers ANALYTICS.MARKETING_*
```

### Pattern 4: Cross-Database Functional Domain

Group tables by business function across databases.

```
REVENUE_META.META.REVENUE_SEARCH → covers
  SALESFORCE.CORE.OPPORTUNITIES
  BILLING.PUBLIC.INVOICES
  PRODUCT.PUBLIC.SUBSCRIPTIONS
```

## Domain Config Schema

```sql
-- Core configuration keys
INSERT INTO {DOMAIN}_META.META.DOMAIN_CONFIG VALUES
  ('domain_name', '"FINANCE"'),
  ('source_databases', '["FINANCE_DB"]'),
  ('source_schemas', 'null'),                    -- null = all schemas in source_databases
  ('ignore_schemas', '["INFORMATION_SCHEMA", "SCRATCH", "STAGING"]'),
  ('enrichment_max_tier', '2'),                  -- 0-3
  ('enrichment_daily_budget_credits', '5.0'),
  ('auto_onboard_schemas', '["PUBLIC", "CORE", "MART"]'),
  ('refresh_schedule', '"0 6 * * *"'),           -- cron
  ('watch_enabled', 'true'),
  ('watch_auto_onboard', 'false'),
  ('css_target_lag', '"1 hour"'),
  ('css_warehouse', '"COMPUTE_WH"');
```

## When to Split vs Merge

**Split a domain when:**
- Schema groups serve completely different user populations
- Tables in different groups never join
- Enrichment needs differ dramatically (one group well-documented, another undocumented)

**Merge databases into one domain when:**
- They share FK patterns (common ID columns)
- They're queried together (co-access in ACCESS_HISTORY)
- They represent one data source split across multiple shares
- They share the same owner role

## Creating a Domain

```sql
CREATE DATABASE IF NOT EXISTS {DOMAIN}_META;
CREATE SCHEMA IF NOT EXISTS {DOMAIN}_META.META;

CREATE TABLE {DOMAIN}_META.META.RAW_CONCEPTS (...);   -- See core-architecture.md
CREATE TABLE {DOMAIN}_META.META.CONCEPTS (...);
CREATE TABLE {DOMAIN}_META.META.RELATIONSHIPS (...);
CREATE TABLE {DOMAIN}_META.META.OBJECT_STATE (...);
CREATE TABLE {DOMAIN}_META.META.DOMAIN_CONFIG (...);
```

## Renaming / Restructuring Domains

1. Create new domain META database
2. Migrate CONCEPTS rows (update domain column)
3. Recreate CSS on new CONCEPTS
4. Drop old META database
5. Update master KG if it exists
