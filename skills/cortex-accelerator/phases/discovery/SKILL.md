---
name: cortex-accelerator-discovery
description: "Phases 1-3 of cortex-accelerator. Hypothesizes domain/entity/metric
  candidates from scan signals, detects gaps (missing docs, FKs) and conflicts
  (same metric different calculations, same entity different scope), and scores
  trust per conflicting definition."
parent_skill: cortex-accelerator
---

# Phases 1–3: Hypothesize, Gaps, Conflicts

Takes the scan scorecard as input. Produces a gap + conflict report with trust scores.
Nothing is built here. No human decisions are locked in yet.

## Phase 1: Hypothesize

### Domain Candidates

Cluster tables by co-query frequency:

```sql
-- Tables that appear together in queries → likely same domain
WITH query_tables AS (
  SELECT QUERY_ID,
    REGEXP_SUBSTR(QUERY_TEXT, '[A-Z_]+\\.[A-Z_]+\\.[A-Z_]+', 1, seq4()) AS table_ref
  FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY,
    TABLE(GENERATOR(ROWCOUNT => 10))
  WHERE START_TIME >= DATEADD(day, -30, CURRENT_TIMESTAMP())
    AND QUERY_TYPE = 'SELECT'
)
SELECT t1.table_ref AS table_a, t2.table_ref AS table_b,
  COUNT(DISTINCT t1.QUERY_ID) AS co_occurrence
FROM query_tables t1 JOIN query_tables t2
  ON t1.QUERY_ID = t2.QUERY_ID AND t1.table_ref < t2.table_ref
GROUP BY 1, 2
ORDER BY co_occurrence DESC
LIMIT 100;
```

Present domain clusters with confidence:
```
Hypothesis: 3 domains detected

  CRM (confidence: HIGH)
    CUSTOMERS, ACCOUNTS, OPPORTUNITIES, CONTACTS
    Evidence: co-queried 847 times, 14 users, clear naming

  FINANCE (confidence: MEDIUM)
    INVOICES, PAYMENTS, GL_ENTRIES, REVENUE_SUMMARY
    Evidence: co-queried 312 times, 4 users

  UNKNOWN_CLUSTER (confidence: LOW)
    SFMC_XXXXX__DLL, BDM_TCR_V2, ACCT_HIER_X
    Evidence: co-queried 89 times, naming is cryptic
    → KG enrichment required to classify
```

### Entity Candidates

For each domain, classify tables:

```sql
-- Bridge/mapping tables: equal FK ratios, no unique business columns
-- Core entities: queried standalone, have a primary key pattern
-- Staging: high row churn, _TMP/_STAGING/_LOAD in name, never joined to final

SELECT TABLE_NAME,
  ROW_COUNT,
  LAST_ALTERED,
  COMMENT
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
  AND (TABLE_NAME ILIKE '%_TMP%' OR TABLE_NAME ILIKE '%_STAGING%'
    OR TABLE_NAME ILIKE '%_LOAD%' OR TABLE_NAME ILIKE '%_BACKUP%');
```

Label each table: `CORE_ENTITY` | `BRIDGE_TABLE` | `STAGING` | `AGGREGATE` | `UNKNOWN`

### Metric Candidates

```sql
-- Columns used in SUM/COUNT/AVG → metric candidates
SELECT
  REGEXP_SUBSTR(QUERY_TEXT, '(SUM|COUNT|AVG|MIN|MAX)\\s*\\(([^)]+)\\)', 1, 1, 'ie', 2)
    AS aggregated_col,
  COUNT(*) AS usage_count
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD(day, -30, CURRENT_TIMESTAMP())
  AND QUERY_TYPE = 'SELECT'
GROUP BY 1
HAVING aggregated_col IS NOT NULL
ORDER BY usage_count DESC
LIMIT 50;
```

## Phase 2: Gap Report

Gaps are missing information that will degrade output quality if not filled.

### Gap Categories

**Documentation gaps** (cause garbage labels in semantic views):
- Tables with no COMMENT and cryptic names
- Columns with no COMMENT used in SELECT or aggregations
- Tables with ROW_COUNT > 10K and no documentation at all

**Relationship gaps** (cause wrong joins):
- No FK constraints anywhere in schema
- Join patterns in queries not confirmed by any constraint
- Same entity key appears under different column names across tables

**Domain boundary gaps** (cause polluted semantic views):
- Tables co-queried with multiple domain clusters equally
- No clear primary entity table for a domain candidate

Format each gap:
```
GAP [G001]: 34 columns in CUSTOMERS have no documentation
  Impact: dimension names will be "Col A", "Cust Id X", "Amt Flg"
  Fix options: (A) KG enrichment, (B) Upload CSV, (C) Answer questions
  Severity: HIGH — these columns appear in 60% of CRM queries

GAP [G002]: No FK constraints defined anywhere in FINANCE schema
  Impact: all relationships are guessed from join patterns (wrong ~30%)
  Fix options: (A) PowerBI relationships, (B) dbt test:relationships, (C) Interview
  Severity: MEDIUM — relationship inference may still be reasonable
```

## Phase 3: Conflict Detection + Trust Scoring

Conflicts are contradictory information. More dangerous than gaps because they're
invisible — users get different numbers from the same question.

### Detect Conflicts

**Metric conflicts** — same logical name, different calculation:
```sql
-- Find columns named similarly but in different tables with different aggregations
SELECT
  COLUMN_NAME,
  TABLE_SCHEMA,
  TABLE_NAME,
  DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME IN (
  SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
  GROUP BY COLUMN_NAME HAVING COUNT(DISTINCT TABLE_NAME) > 2
)
AND DATA_TYPE IN ('NUMBER', 'FLOAT', 'DECIMAL')
ORDER BY COLUMN_NAME;
```

**Entity conflicts** — same concept, radically different row counts:
```sql
SELECT TABLE_NAME, ROW_COUNT, TABLE_SCHEMA
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME ILIKE '%CUSTOMER%' OR TABLE_NAME ILIKE '%ACCOUNT%'
ORDER BY ROW_COUNT DESC;
```

### Trust Scoring

For each conflicting definition, score 0–100:

| Signal | Weight |
|--------|--------|
| Query frequency (30d) | 30 |
| Distinct users | 25 |
| Scheduled executions (service accounts, tagged) | 20 |
| Low error rate | 15 |
| Trend direction (90d, growing=+, declining=-) | 10 |

**BI tool boosts** (applied after base score):
- Found in dbt metrics layer: +35
- Found in PowerBI DAX measure: +30
- Found in Tableau calculated field: +25

**Trust caveats — always check:**
- High frequency + high error rate → not trusted despite volume
- Low frequency + scheduled + zero errors → may be authoritative (finance close)
- Single user accounts for >80% of queries → not consensus

### Conflict Report Format

```
CONFLICT [C001]: "revenue" — 3 definitions (BLOCKING)
  Finance:    SUM(net_amount)          score: 91  ★ RECOMMENDED
              18 users, 142 scheduled runs, 1.2% error, +12% trend
  CRM:        SUM(opportunity_amount)  score: 38
              4 users, 8 scheduled, 8.4% error, -18% trend
  Marketing:  SUM(attributed_pipeline) score: 14
              1 user, 0 scheduled, 22% error, -41% trend
  → Recommend Finance as canonical. Federate CRM + Marketing as domain-scoped.
  → human_decision: PENDING

CONFLICT [C002]: "customer" — different scope (BLOCKING)
  CRM:     2.1M rows, any account record
  Finance: 180K rows, paid in last 90 days
  Support: 42K rows, open ticket
  → No shared key detected across CRM and Finance.
  → Requires MDM mapping table or user decision.
  → human_decision: PENDING

NON-BLOCKING [C003]: "order" exists at line + invoice grain
  → Will federate: crm_order_line, finance_order_invoice
  → No human decision required, but document grain in semantic view.
```

### Severity Classification

| Severity | Meaning | Pipeline impact |
|----------|---------|-----------------|
| BLOCKING | Cannot build correctly until resolved | Pipeline halted |
| NON-BLOCKING | Build with explicit separation, flag for governance | Proceed with federated names |
| INFORMATIONAL | Log for governance team | No impact |

**⚠️ STOPPING POINT:** Present gap + conflict report to user.
Confirm they have reviewed it before proceeding to Phase 4.

**Next:** Load `phases/resolution/SKILL.md`.
