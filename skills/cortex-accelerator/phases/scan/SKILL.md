---
name: cortex-accelerator-scan
description: "Phase 0 of cortex-accelerator. Scans schema quality, query history,
  data quality, PII classification, and access permissions. Produces a per-domain
  readiness scorecard that routes the pipeline."
parent_skill: cortex-accelerator
---

# Phase 0: Scan & Score

Collect signals. Produce a readiness scorecard per domain candidate. Do not hypothesize
yet — this phase is pure signal collection.

## Step 1: Confirm Scope

Ask the user (or detect from entry point):
- Which databases/schemas to include?
- Which role will end users query with?
- Are there databases to explicitly exclude (staging, dev, archive)?

In Autonomous mode: scan all non-system databases with query activity in last 30 days.

## Step 2: Schema Quality Scan

```sql
-- Table comment coverage
SELECT
  TABLE_CATALOG, TABLE_SCHEMA,
  COUNT(*) AS total_tables,
  COUNT(COMMENT) AS commented_tables,
  ROUND(COUNT(COMMENT)/COUNT(*)*100, 1) AS comment_pct
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
GROUP BY 1, 2
ORDER BY comment_pct ASC;

-- Column comment coverage (sample per schema)
SELECT
  TABLE_CATALOG, TABLE_SCHEMA,
  COUNT(*) AS total_cols,
  COUNT(COMMENT) AS commented_cols,
  ROUND(COUNT(COMMENT)/COUNT(*)*100, 1) AS comment_pct
FROM INFORMATION_SCHEMA.COLUMNS
GROUP BY 1, 2
ORDER BY comment_pct ASC;

-- Data type hygiene — all-VARCHAR schemas are high risk
SELECT TABLE_SCHEMA,
  COUNT(*) AS total_cols,
  SUM(CASE WHEN DATA_TYPE = 'TEXT' THEN 1 ELSE 0 END) AS varchar_cols,
  ROUND(SUM(CASE WHEN DATA_TYPE = 'TEXT' THEN 1 ELSE 0 END)/COUNT(*)*100,1) AS varchar_pct
FROM INFORMATION_SCHEMA.COLUMNS
GROUP BY 1
ORDER BY varchar_pct DESC;
```

**Flag:** comment_pct < 30% → KG enrichment recommended.
**Flag:** varchar_pct > 70% → dimension/fact classification will be unreliable.

## Step 3: Query History Signals

```sql
-- Volume, user diversity, error rate, cross-DB complexity (last 30 days)
SELECT
  DATABASE_NAME,
  COUNT(*) AS query_count,
  COUNT(DISTINCT USER_NAME) AS distinct_users,
  ROUND(AVG(CASE WHEN ERROR_CODE IS NOT NULL THEN 1.0 ELSE 0 END)*100, 2) AS error_rate_pct,
  SUM(CASE WHEN QUERY_TEXT ILIKE '%INFORMATION_SCHEMA%' THEN 0
           WHEN REGEXP_COUNT(QUERY_TEXT, '[A-Z_]+\\.[A-Z_]+\\.[A-Z_]+') > 2 THEN 1
           ELSE 0 END) AS cross_db_queries
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD(day, -30, CURRENT_TIMESTAMP())
  AND QUERY_TYPE = 'SELECT'
  AND EXECUTION_STATUS = 'SUCCESS'
GROUP BY 1
ORDER BY query_count DESC;

-- Scheduled vs ad-hoc signal (BI tool proxy)
SELECT
  CASE WHEN QUERY_TAG != '' THEN 'tagged'
       WHEN USER_NAME ILIKE '%svc%' OR USER_NAME ILIKE '%service%' THEN 'service_account'
       WHEN HOUR(START_TIME) BETWEEN 6 AND 20 THEN 'business_hours'
       ELSE 'off_hours'
  END AS query_type,
  COUNT(*) AS cnt
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD(day, -30, CURRENT_TIMESTAMP())
  AND QUERY_TYPE = 'SELECT'
GROUP BY 1;
```

**Flag:** cross_db_queries > 20% of total → KG path required.
**Flag:** distinct_users = 1 and query_count > 500 → not representative; ask who else queries.
**Flag:** error_rate > 10% → data/schema instability, investigate before building.

## Step 4: Data Quality & Freshness

```sql
-- Table freshness (last DML)
SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME,
  LAST_ALTERED,
  DATEDIFF(day, LAST_ALTERED, CURRENT_DATE()) AS days_since_update,
  ROW_COUNT
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY days_since_update DESC;

-- Check for existing DMF results
SHOW DATA METRIC FUNCTIONS IN ACCOUNT;
```

**Flag:** days_since_update > 60 on heavily queried table → data may be stale, warn user.
**Flag:** ROW_COUNT = 0 on referenced table → exclude from domain candidates.

## Step 5: PII & Governance Check

```sql
-- Existing masking policies
SHOW MASKING POLICIES IN ACCOUNT;

-- Existing row access policies
SHOW ROW ACCESS POLICIES IN ACCOUNT;

-- Tags applied (Snowflake tagging)
SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
WHERE TAG_NAME IN ('PII', 'SENSITIVE', 'CONFIDENTIAL')
LIMIT 100;
```

Run SYSTEM$CLASSIFY on a sample of high-frequency tables:
```sql
SELECT SYSTEM$CLASSIFY('DATABASE.SCHEMA.TABLE', {}) AS classification;
```

**Flag:** PII columns exist with no masking policy → BLOCKING. Agent cannot be deployed
until masking is confirmed or user explicitly accepts the exposure risk.

## Step 6: Access Check

```sql
-- Verify target role has grants on key tables
SHOW GRANTS TO ROLE <TARGET_ROLE>;

-- Check future grants
SHOW FUTURE GRANTS IN SCHEMA <DATABASE.SCHEMA>;
```

Ask user: "What role will end users query the agent with?"
Check that role has SELECT on all tables that will enter the semantic layer.

**Flag:** Missing SELECT grant → BLOCKING. Must be resolved before deployment.

## Step 7: Produce Readiness Scorecard

For each database/domain candidate, score 0–100:

| Signal | Weight | Green | Yellow | Red |
|--------|--------|-------|--------|-----|
| Table comment coverage | 20 | >60% | 30-60% | <30% |
| Column comment coverage | 15 | >50% | 20-50% | <20% |
| Query volume (30d) | 15 | >100 | 20-100 | <20 |
| User diversity | 10 | >5 users | 2-5 | 1 user |
| Error rate | 10 | <3% | 3-10% | >10% |
| FK coverage | 10 | >50% | 20-50% | <20% |
| Data freshness | 10 | <7d | 7-60d | >60d |
| No PII gaps | 10 | All masked | Some gaps | Unmasked PII |

Present scorecard:
```
Domain: CRM_DB
  Schema comments:    ██░░░░  28%  RED
  Column comments:    ███░░░  45%  YELLOW
  Query volume:       ██████  900  GREEN
  User diversity:     █████░  12   GREEN
  Error rate:         █████░  2%   GREEN
  FK coverage:        ██░░░░  20%  YELLOW
  Data freshness:     ██████  2d   GREEN
  PII governance:     ████░░  gaps YELLOW
  ─────────────────────────────────────
  Score: 61/100  →  REMEDIATION NEEDED
  Recommendation: KG enrichment for schema docs + resolve PII gaps
```

## Step 8: Routing Decision

| Score | Path |
|-------|------|
| ≥ 75 | Clean path — proceed to discovery without KG |
| 40–74 | User prompted: KG enrichment OR provide documentation |
| < 40 | KG required — no shortcut |
| Any BLOCKING flag | Must resolve before continuing |

**⚠️ STOPPING POINT:** Present scorecard to user. Confirm routing decision.

**If BLOCKING flags exist:** Do not proceed. Walk user through resolution steps.
**Otherwise:** Load `phases/discovery/SKILL.md` and pass scorecard as context.
