---
name: snowhouse-demo-scaffold
description: "Discover a customer's actual Snowflake table schemas via Snowhouse and generate CREATE TABLE + INSERT DDL with synthetic data that mirrors their real environment. Use before running 03_ontology_architect_agent or 04_demo_builder_agent to make demos customer-specific. Triggers: scaffold demo tables, discover customer schema, snowhouse schema discovery, mirror customer tables, demo DDL from snowhouse, customer-specific demo, generate demo tables."
---

# Snowhouse Demo Scaffold

Discovers a customer's hot databases + actual table schemas via Snowhouse, then generates CREATE TABLE + INSERT DDL with synthetic data. Output feeds directly into `03_ontology_architect_agent.md` and `04_demo_builder_agent.md`.

**All queries use connection `snowhouse` + warehouse `SNOWADHOC`.**

---

## Step 0 — Account Lookup

Ask the user for a **customer name** (e.g., "T-Mobile", "Sony") and a **company slug** for the output path (e.g., `tmobile`, `sony`).

Run against `snowhouse` connection:

```sql
USE WAREHOUSE SNOWADHOC;
SELECT DISTINCT
    SF_ACCT_ID,
    SF_ACCT_NAME || ' (' || IFNULL(SF_ACCT_ALIAS,'NO ALIAS') || ')' AS SF_ACCT_DISPLAY,
    SFDC_CUST_NAME                           AS CUSTOMER_NAME,
    SF_SERVICE                               AS EDITION,
    SF_DEPLOYMENT,
    SF_CLOUD || ' → ' || PROVIDER_REGION     AS CLOUD_REGION,
    L30_CREDITS
FROM TEMP.VSHIV.SUBSCRIPTIONS_DT
WHERE UPPER(SFDC_CUST_NAME) ILIKE '%{CUSTOMER_NAME}%'
ORDER BY L30_CREDITS DESC NULLS LAST
```

- If multiple rows returned, present as table and ask user to pick one.
- Set variables: `ACCOUNT_ID`, `DEPLOYMENT`, `CUSTOMER_NAME`, `COMPANY_SLUG`, `SF_SERVICE`, `SF_ACCT_NAME`, `L30_CREDITS`.

---

## Step 1 — Database Heat Map

**⚠️ MANDATORY STOPPING POINT — present results and wait for user selection before continuing.**

```sql
USE WAREHOUSE SNOWADHOC;
SELECT
    database_name,
    COUNT(*)                                            AS query_count,
    COUNT(DISTINCT user_name)                           AS distinct_users,
    ROUND(SUM(
        LEAST(COALESCE(dpo:"JobDPO:stats":endTime::INT, 0), 4102444800000)
        - dpo:"JobDPO:primary":createdOn::INT
    ) / 3600000.0, 1)                                   AS compute_hours
FROM snowhouse_import.{DEPLOYMENT}.job_raw_v
WHERE account_id = {ACCOUNT_ID}
  AND created_on >= DATEADD(day, -90, CURRENT_DATE())
  AND child_job_type != 4
  AND bitand(flags, 2080) != 2080
  AND bitand(flags, 1073741824) != 1073741824
  AND bitand(flags, 288230376151711744) = 0
  AND current_state_id != 25
  AND database_name IS NOT NULL
GROUP BY database_name
ORDER BY query_count DESC
LIMIT 15
```

Present as table. Ask:
```
Which databases should I scaffold? (default = top 3 by query count)
Enter database names or numbers (2-4 max):
```

Set variable `SELECTED_DBS` (list of confirmed database names).

---

## Step 2 — Table Discovery

**⚠️ MANDATORY STOPPING POINT — present candidates and wait for table selection.**

For **each selected database**, run both queries:

**Query A — column inventory:**
```sql
USE WAREHOUSE SNOWADHOC;
SELECT
    schema_name,
    table_name,
    COUNT(*) AS column_count
FROM SNOWHOUSE.PRODUCT.ALL_LIVE_TABLE_COLUMNS
WHERE account_id = {ACCOUNT_ID}
  AND UPPER(database_name) = UPPER('{DB_NAME}')
  AND DS >= DATEADD(day, -3, CURRENT_DATE())
QUALIFY ROW_NUMBER() OVER (PARTITION BY schema_name, table_name, NAME ORDER BY DS DESC) = 1
GROUP BY schema_name, table_name
ORDER BY column_count DESC
LIMIT 50
```

**Query B — query frequency by table reference:**
```sql
USE WAREHOUSE SNOWADHOC;
SELECT
    UPPER(REGEXP_SUBSTR(
        IFF(bitand(flags, 549755813888) = 0,
            IFF(bitand(flags, 34359738368) = 0,
                strip_null_value(dpo:"JobDPO:description":description)::STRING, ''),
            ''),
        '[A-Za-z0-9_$]+\\.[A-Za-z0-9_$]+\\.[A-Za-z0-9_$]+',
        1, 1, 'i'
    )) AS table_ref,
    COUNT(*) AS mention_count
FROM snowhouse_import.{DEPLOYMENT}.job_raw_v
WHERE account_id = {ACCOUNT_ID}
  AND UPPER(database_name) = UPPER('{DB_NAME}')
  AND created_on >= DATEADD(day, -90, CURRENT_DATE())
  AND child_job_type != 4
  AND bitand(flags, 2080) != 2080
  AND bitand(flags, 1073741824) != 1073741824
  AND bitand(flags, 288230376151711744) = 0
  AND current_state_id != 25
GROUP BY table_ref
HAVING table_ref IS NOT NULL
ORDER BY mention_count DESC
LIMIT 30
```

Merge results (join Query A + B on table_name, rank by `mention_count` then `column_count`). Present combined table:

| DB | Schema | Table | Columns | Query Mentions |
|----|--------|-------|---------|----------------|
| ...| ...    | ...   | ...     | ...            |

Ask:
```
Which tables should I scaffold? (default = top 10 by query mentions)
More tables = longer DDL generation.
```

Set variable `SELECTED_TABLES` (list of {db, schema, table} tuples).

---

## Step 2.5 — Join Graph Analysis

> **Note:** If Query B in Step 2 returned all NULLs (flag redaction active on this account), skip this step and print:
> `⚠ Join graph skipped — query text not available for this account (flag redaction active).`

Discover which tables co-appear in the same JOIN queries. Deduplicates on `query_parameterized_hash` first so 200M+ repeated query executions collapse to unique query patterns before the expensive regex expansion.

```sql
USE WAREHOUSE SNOWADHOC;
WITH unique_patterns AS (
    SELECT
        ANY_VALUE(job_id) AS job_id,
        ANY_VALUE(
            IFF(bitand(flags, 549755813888) = 0,
                IFF(bitand(flags, 34359738368) = 0,
                    strip_null_value(dpo:"JobDPO:description":description)::STRING, ''),
                '')
        ) AS qtext
    FROM snowhouse_import.{DEPLOYMENT}.job_raw_v
    WHERE account_id = {ACCOUNT_ID}
      AND UPPER(database_name) IN ({SELECTED_DBS_QUOTED_LIST})
      AND created_on >= DATEADD(day, -90, CURRENT_DATE())
      AND child_job_type != 4
      AND bitand(flags, 2080) != 2080
      AND bitand(flags, 1073741824) != 1073741824
      AND bitand(flags, 288230376151711744) = 0
      AND current_state_id != 25
      AND query_parameterized_hash IS NOT NULL
    GROUP BY query_parameterized_hash
),
join_patterns AS (
    SELECT job_id, qtext
    FROM unique_patterns
    WHERE UPPER(qtext) LIKE '%JOIN%'
),
refs AS (
    SELECT
        q.job_id,
        UPPER(REGEXP_SUBSTR(q.qtext,
            '[A-Za-z0-9_$]+\\.[A-Za-z0-9_$]+\\.[A-Za-z0-9_$]+',
            1, s.n, 'i')) AS table_ref
    FROM join_patterns q
    CROSS JOIN (
        SELECT 1 AS n UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
        UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8
    ) s
)
SELECT
    LEAST(r1.table_ref, r2.table_ref)    AS table_a,
    GREATEST(r1.table_ref, r2.table_ref) AS table_b,
    COUNT(DISTINCT r1.job_id)            AS shared_queries,
    CASE
        WHEN COUNT(DISTINCT r1.job_id) >= 20 THEN 'HIGH'
        WHEN COUNT(DISTINCT r1.job_id) >= 5  THEN 'MEDIUM'
        ELSE 'LOW'
    END AS confidence
FROM refs r1
JOIN refs r2
    ON  r1.job_id    = r2.job_id
    AND r1.table_ref < r2.table_ref
    AND r1.table_ref IS NOT NULL
    AND r2.table_ref IS NOT NULL
GROUP BY 1, 2
HAVING shared_queries >= 3
ORDER BY shared_queries DESC
LIMIT 30
```

**`{SELECTED_DBS_QUOTED_LIST}`** — comma-separated quoted list, e.g. `'CRM_DB', 'BILLING_DB'`.

Present results:

| Table A | Table B | Shared Queries | Confidence | Inferred Join Key |
|---------|---------|----------------|------------|-------------------|
| ...     | ...     | ...            | HIGH/MED/LOW | *(filled after Step 3)* |

**Infer join keys after Step 3:** For each pair, compare the column lists of both tables. Column names appearing in both (e.g. `customer_id`, `device_id`) are the likely FK/join key. Fill in the "Inferred Join Key" column then.

Save the results as variable `JOIN_GRAPH` for use in Step 4.

---

## Step 2.75 — Query Pattern Extraction

> **Note:** If Query B in Step 2 returned all NULLs (flag redaction active), skip this step and print:
> `⚠ Query patterns skipped — query text not available for this account (flag redaction active).`

Extract the top production SQL patterns for the selected databases. These reveal how analysts actually use the data — WHERE filters, aggregations, CASE WHEN business rules, column aliases, and CTE patterns — all of which feed into semantic view definitions and agent instructions.

```sql
USE WAREHOUSE SNOWADHOC;
WITH unique_patterns AS (
    SELECT
        query_parameterized_hash,
        ANY_VALUE(
            IFF(bitand(flags, 549755813888) = 0,
                IFF(bitand(flags, 34359738368) = 0,
                    strip_null_value(dpo:"JobDPO:description":description)::STRING, ''),
                '')
        ) AS qtext,
        ANY_VALUE(user_name) AS sample_user,
        COUNT(*) AS execution_count,
        COUNT(DISTINCT user_name) AS distinct_users,
        MIN(created_on) AS first_seen,
        MAX(created_on) AS last_seen
    FROM snowhouse_import.{DEPLOYMENT}.job_raw_v
    WHERE account_id = {ACCOUNT_ID}
      AND UPPER(database_name) IN ({SELECTED_DBS_QUOTED_LIST})
      AND created_on >= DATEADD(day, -90, CURRENT_DATE())
      AND child_job_type != 4
      AND bitand(flags, 2080) != 2080
      AND bitand(flags, 1073741824) != 1073741824
      AND bitand(flags, 288230376151711744) = 0
      AND current_state_id != 25
      AND query_parameterized_hash IS NOT NULL
    GROUP BY query_parameterized_hash
)
SELECT
    query_parameterized_hash,
    qtext,
    sample_user,
    execution_count,
    distinct_users,
    first_seen,
    last_seen
FROM unique_patterns
WHERE LENGTH(qtext) > 50
  AND LENGTH(qtext) < 10000
  AND UPPER(qtext) LIKE '%SELECT%'
ORDER BY execution_count DESC
LIMIT 30
```

**`{SELECTED_DBS_QUOTED_LIST}`** — same comma-separated quoted list from Step 2.5.

Set variable `QUERY_PATTERNS` (list of {hash, qtext, execution_count, distinct_users, sample_user, first_seen, last_seen}).

**⚠️ IMPORTANT: Filter out non-analyst noise before analysis.**
Exclude patterns that match these CDC/ETL/metadata signatures:
- `ATTREP_CHANGES` or `REPLICATE_OP` — Qlik CDC replication
- `INFORMATION_SCHEMA.DATABASES` / `INFORMATION_SCHEMA.COLUMNS` — schema inspection
- `SYSTEM$AUTHORIZE` / `SYSTEM$BOOTSTRAP` — session setup
- `_STAGE_STREAM...LATERAL FLATTEN` — stream schema discovery
- Queries that start with `INSERT INTO`, `DELETE FROM`, `MERGE INTO` — DML, not analytics
Focus on queries starting with `SELECT` that contain JOINs, GROUP BY, aggregations, CASE WHEN, OVER(), or are used by 3+ distinct users.

### Analysis Phase A — Per-Pattern Extraction

For each query pattern, parse and note:
1. **Tables referenced** — full `DB.SCHEMA.TABLE` references
2. **WHERE filters** — which columns are filtered, what values/ranges
3. **Aggregations** — SUM/COUNT/AVG/MIN/MAX and on which columns
4. **GROUP BY columns** — these are candidate dimensions
5. **CASE WHEN expressions** — business rules and derived categories
6. **Column aliases** — how analysts name computed columns (candidate synonyms)
7. **CTEs** — reusable subquery patterns

### Analysis Phase B — Domain Categorization

Classify each pattern into a business domain based on table names and query content.
Use these heuristics (adapt names to the customer's actual schema):
- Tables containing `subscriber`, `customer`, `account`, `person` → **SUBSCRIBER/CUSTOMER**
- Tables containing `order`, `fulfillment`, `orchestration` → **ORDER_MANAGEMENT**
- Tables containing `transaction`, `billing`, `payment`, `invoice`, `mrc` → **BILLING**
- Tables containing `cdr`, `usage`, `network`, `tower`, `signal` → **NETWORK/USAGE**
- Tables containing `churn`, `retention`, `risk`, `propensity` → **CHURN/RETENTION**
- Tables containing `device`, `imei`, `inventory`, `serial` → **DEVICE/INVENTORY**
- Tables containing `case`, `incident`, `interaction`, `care`, `contact` → **CARE/SUPPORT**
- Tables containing `port`, `switch`, `migration` → **PORTING/MIGRATION**
- Tables containing `schedule`, `workforce`, `agent`, `employee` → **WORKFORCE**

Produce a **domain heat map** — count of unique patterns and max distinct_users per domain.

### Analysis Phase C — Cross-DB Join Chains

From the filtered patterns, identify queries that reference tables in **2+ different databases**.
For each cross-DB join, note:
- The full join chain: `DB1.SCHEMA.TABLE` → `DB2.SCHEMA.TABLE` → `DB3.SCHEMA.TABLE`
- The join keys used (column names in ON clauses)
- How many patterns share this chain
- Whether the join is direct (2 tables) or transitive (3+ tables chained)

These are the highest-value ontology relationships — they represent manual integration work analysts do today.

### Analysis Phase D — VARIANT/JSON Pain Detection

Flag patterns that contain any of:
- `PARSE_JSON(...)` or `TRY_PARSE_JSON(...)`
- `column:path::type` semi-structured access
- `LATERAL FLATTEN(...)` on document columns
- `OBJECT_CONSTRUCT(...)` or `ARRAY_AGG(...)`

Count how many patterns and distinct users rely on VARIANT extraction. This quantifies the "semi-structured data wrangling tax" the ontology/semantic view eliminates.

### Analysis Phase E — Gap Analysis

Compare domain heat map against total query volume per database (from Step 1).
Flag domains where:
- **High operational volume but low analyst coverage** (e.g., many ETL queries but few analyst SELECTs) → data exists but is inaccessible to analysts
- **Low pattern count but high user count** → many people need this data but only simple lookups exist (no aggregations/joins)
- **Zero or near-zero patterns** for expected business domains → completely dark to analytics

These gaps are the strongest positioning for the ontology/agent demo.

### Analysis Phase F — Competitive Positioning Signals

Identify patterns that strengthen the "data you can't afford to move" narrative:
- **Real-time monitoring** — queries with `>= CURRENT_DATE` or `DATEADD(MIN, -15, ...)` lookback windows
- **Compliance/regulatory** — 911/E911 queries, PII-adjacent lookups, audit trails
- **Cross-product identity** — queries joining subscriber data across multiple brands/products
- **High-frequency operational** — patterns with 10K+ executions (operational dashboards that must stay near the data)

Store all analysis phases as variable `PATTERN_ANALYSIS` for use in Step 4.

---

## Step 3 — Schema Extraction

For each confirmed table, run:

```sql
USE WAREHOUSE SNOWADHOC;
SELECT
    NAME                           AS column_name,
    DATA_TYPE_ENCODED:type::STRING AS data_type,
    ORDINAL                        AS ordinal_position
FROM SNOWHOUSE.PRODUCT.ALL_LIVE_TABLE_COLUMNS
WHERE account_id = {ACCOUNT_ID}
  AND UPPER(database_name) = UPPER('{DB_NAME}')
  AND UPPER(schema_name)   = UPPER('{SCHEMA_NAME}')
  AND UPPER(table_name)    = UPPER('{TABLE_NAME}')
  AND DS >= DATEADD(day, -3, CURRENT_DATE())
QUALIFY ROW_NUMBER() OVER (PARTITION BY NAME ORDER BY DS DESC) = 1
ORDER BY ORDINAL
```

Collect all schemas before generating anything.

---

## Step 4 — Generate DDL and Write Output Files

**⚠️ MANDATORY STOPPING POINT — confirm before writing:**
```
Ready to generate DDL for {N} tables ({total_columns} columns).
Write to customers/{company_slug}/? (Y/N)
```

Wait for explicit Y before writing anything.

---

### Data Type Mapping (Snowhouse → DDL)

| Snowhouse type | DDL type |
|----------------|----------|
| varchar, text, string, char | VARCHAR |
| number, decimal, numeric, int, bigint, smallint, tinyint | NUMBER |
| float, double, real | FLOAT |
| date | DATE |
| timestamp_ntz, timestamp_ltz, timestamp_tz, datetime | TIMESTAMP_NTZ |
| boolean | BOOLEAN |
| variant, object, array | VARIANT |
| binary, varbinary | BINARY |

---

### Fake Data Generation Rules

Match by **column name pattern** (case-insensitive):

| Pattern | Generated value |
|---------|----------------|
| `*_ID`, `*_KEY`, `*_UUID*`, `*_GUID*` | Sequential integers (1,2,3…) or UUID-format strings |
| `*_NAME*`, `*_LABEL*`, `*_TITLE*` | Realistic names for customer's domain |
| `*_DATE*`, `*_AT`, `*_TIME*` | Recent DATE/TIMESTAMP (last 12 months) |
| `*_AMOUNT*`, `*_REVENUE*`, `*_COST*`, `*_PRICE*`, `*_FEE*`, `*_VALUE*` | Industry-realistic dollar amounts |
| `*_STATUS*`, `*_STATE*`, `*_TYPE*`, `*_TIER*`, `*_CATEGORY*` | Domain-appropriate enum values (ACTIVE/INACTIVE, etc.) |
| `*_EMAIL*` | `user{N}@example.com` format |
| `*_PHONE*`, `*_MSISDN*` | `555-0100` through `555-0119` |
| `*_CODE*`, `*_NUM*` | Short alphanumeric (e.g., `A001`) |
| BOOLEAN | Mix of TRUE / FALSE |
| VARIANT | `PARSE_JSON('{"key": "value"}')` with realistic structure |

**Never use NULL for NOT NULL columns.** Generate 15–20 INSERT rows per table.

---

### DDL Structure Per Table

```sql
-- ============================================================
-- TABLE: {TABLE_NAME}
-- SOURCE: {original_db}.{schema_name}.{table_name}
-- Query mentions (90d): {N}  |  Columns: {N}
-- Synthetic data only — mirrors real schema structure
-- ============================================================
CREATE OR REPLACE TABLE {COMPANY_SLUG_UPPER}_DEMO.PUBLIC.{TABLE_NAME} (
    {column_name_1}  {data_type},
    {column_name_2}  {data_type}
    -- ...
);

INSERT INTO {COMPANY_SLUG_UPPER}_DEMO.PUBLIC.{TABLE_NAME} VALUES
    (...),
    (...);
```

---

### Write File 1 — `demo_tables.sql`

Path: `~/src/demos/ontology-demo/customers/{company_slug}/demo_tables.sql`

```sql
-- ============================================================
-- SNOWHOUSE DEMO SCAFFOLD — {CUSTOMER_NAME_UPPER}
-- Account: {SF_ACCT_NAME} (ID: {ACCOUNT_ID})
-- Deployment: {DEPLOYMENT}  |  Edition: {SF_SERVICE}
-- Generated: {today's date}
-- Source DBs: {comma-separated list}
-- Tables: {N}  |  Columns: {N}  |  Seed rows: {N}
-- SYNTHETIC DATA ONLY — not a copy of customer data
-- ============================================================
-- USAGE: Feed to 03_ontology_architect_agent.md
--   → Reference these table names in system_mapping.json
--   → Use column names when designing ontology class attributes
-- ============================================================

USE ROLE SYSADMIN;
CREATE DATABASE IF NOT EXISTS {COMPANY_SLUG_UPPER}_DEMO;
CREATE SCHEMA IF NOT EXISTS {COMPANY_SLUG_UPPER}_DEMO.PUBLIC;
USE DATABASE {COMPANY_SLUG_UPPER}_DEMO;
USE SCHEMA PUBLIC;
```

Then all CREATE TABLE + INSERT blocks. End with:
```sql
-- ============================================================
-- NEXT STEPS
-- 1. Run 01_company_research_agent.md (web research)
-- 2. Open 03_ontology_architect_agent.md
--    → Read schema_summary.md BEFORE Step 2 (class design)
--    → Map ontology classes to real table names in system_mapping.json
-- 3. Run 04_demo_builder_agent.md
--    → KG_NODE/KG_EDGE build on top of these scaffolded tables
-- ============================================================
```

---

### Write File 2 — `schema_summary.md`

Path: `~/src/demos/ontology-demo/customers/{company_slug}/schema_summary.md`

```markdown
# {CUSTOMER_NAME} — Snowhouse Schema Discovery

*Generated: {date} | Account ID: {ACCOUNT_ID} | Deployment: {DEPLOYMENT}*

## Account Overview
| Field | Value |
|-------|-------|
| Account | {SF_ACCT_NAME} |
| Edition | {SF_SERVICE} |
| L30 Credits | {L30_CREDITS} |
| Deployment | {DEPLOYMENT} |

## Database Heat Map (Last 90 Days)
| Database | Queries | Users | Compute Hours |
|----------|---------|-------|---------------|
[rows from Step 1]

## Scaffolded Tables
### {DB_NAME}
| Schema | Table | Columns | Query Mentions |
|--------|-------|---------|----------------|
[rows from Step 2]

## Column Inventory
### {TABLE_NAME} (source: {DB}.{SCHEMA}.{TABLE})
| Column | Type | Nullable | Domain Inference |
|--------|------|----------|-----------------|
[rows from Step 3 — infer domain from column name patterns]

## Domain Inference
Based on column names, inferred ontology domains:
- **[DOMAIN]**: {TABLE_1}, {TABLE_2} → maps to OWL class {ClassName}

## Next Steps
1. Run `01_company_research_agent.md` for web research
2. Open `03_ontology_architect_agent.md`
   - Read this file BEFORE Step 2 (class design)
   - Also read `join_graph.md` if present — it pre-seeds `relations.json`
   - Also read `query_patterns.md` if present — it provides semantic view recommendations
   - Map ontology classes to real table names in system_mapping.json
3. Run `04_demo_builder_agent.md`
   - Reference `demo_tables.sql` as the physical foundation
   - Reference `query_patterns.md` for semantic view facts/dimensions/metrics/synonyms
   - KG_NODE/KG_EDGE build on top of these scaffolded tables
```

---

### Write File 3 — `join_graph.md`

**Only write this file if Step 2.5 returned results (i.e., join graph query was not skipped).**

Path: `~/src/demos/ontology-demo/customers/{company_slug}/join_graph.md`

```markdown
# {CUSTOMER_NAME} — Query Join Graph

*Generated: {date} | Account ID: {ACCOUNT_ID} | Deployment: {DEPLOYMENT}*
*Source: {N} unique query patterns analyzed (last 90 days) across {SELECTED_DBS}*

## Table Relationship Pairs

| Table A | Table B | Shared Queries | Confidence | Inferred Join Key |
|---------|---------|----------------|------------|-------------------|
[rows from Step 2.5 + inferred join keys from Step 3 column overlap]

## Relationship Inferences for relations.json

Use these as pre-seeded candidates when running `03_ontology_architect_agent.md`:
- **HIGH confidence** (≥20 shared queries) → `demo_priority: HIGH`, `source: query_analysis`
- **MEDIUM confidence** (5–19 shared queries) → `demo_priority: MEDIUM`, `source: query_analysis`
- **LOW confidence** (3–4 shared queries) → use as supporting evidence only

## Next Step

Open `03_ontology_architect_agent.md` — Step 1B will read this file and use the
HIGH/MEDIUM pairs as candidate entries in `relations.json` automatically.
```

---

### Write File 4 — `query_patterns.md`

**Only write this file if Step 2.75 returned results (i.e., query text was not redacted).**

Path: `~/src/demos/ontology-demo/customers/{company_slug}/query_patterns.md`

```markdown
# {CUSTOMER_NAME} — Production Query Patterns

*Generated: {date} | Account ID: {ACCOUNT_ID} | Deployment: {DEPLOYMENT}*
*Source: Top 30 query patterns by execution count (last 90 days) across {SELECTED_DBS}*

## Summary

| Metric | Value |
|--------|-------|
| Unique query patterns analyzed | {N} |
| Total executions represented | {sum of execution_count} |
| Distinct users across patterns | {N} |
| Cross-DB join patterns | {N} |
| VARIANT/JSON extraction patterns | {N} |

## Domain Heat Map

| Domain | Unique Patterns | Total Executions | Max Users | Key Tables |
|--------|----------------|------------------|-----------|------------|
[rows from Phase B — sorted by total executions descending]

**Gap flags:** [from Phase E — domains with high ETL volume but low analyst coverage]

## Cross-Database Join Chains

| Join Chain | Join Keys | Patterns | Users | Type |
|------------|-----------|----------|-------|------|
[rows from Phase C — cross-DB table references with inferred join keys]

Each chain = one ontology relationship that eliminates a manual JOIN.

## VARIANT/JSON Pain Index

| Pattern Description | VARIANT Operations | Patterns | Users |
|--------------------|--------------------|----------|-------|
[rows from Phase D — semi-structured extraction patterns]

## Competitive Positioning Signals

| Signal Type | Example | Patterns | Why it can't move |
|-------------|---------|----------|-------------------|
[rows from Phase F — real-time, compliance, cross-product, high-frequency]

## Top Query Patterns

### Pattern 1 — {brief description inferred from SQL}
- **Domain:** {from Phase B} | **Cross-DB:** {Yes/No}
- **Executions:** {execution_count} | **Users:** {distinct_users} | **Last seen:** {last_seen}
- **Tables:** {list of DB.SCHEMA.TABLE references}
- **VARIANT ops:** {parse_json / LATERAL FLATTEN calls, if any}
- **Aggregations:** {SUM/COUNT/AVG columns, if any}
- **Filters:** {WHERE clause columns and value patterns}
- **GROUP BY:** {columns — candidate dimensions}
- **Business rules:** {CASE WHEN expressions, if any}
- **Column aliases:** {analyst-chosen names — candidate synonyms}

```sql
{sanitized query text — replace literal values with placeholders}
```

[repeat for each pattern...]

## Semantic View Recommendations

Based on the query patterns above:

### Candidate Facts (aggregated columns)
| Column | Aggregation | Source Table | Pattern Count |
|--------|-------------|-------------|---------------|
[columns that appear in SUM/COUNT/AVG across multiple patterns]

### Candidate Dimensions (GROUP BY / WHERE columns)
| Column | Source Table | Pattern Count | Sample Values |
|--------|-------------|---------------|---------------|
[columns that appear in GROUP BY or WHERE across multiple patterns]

### Candidate Metrics (common aggregation expressions)
| Expression | Alias Used | Pattern Count |
|------------|-----------|---------------|
[e.g., SUM(amount), COUNT(DISTINCT customer_id), AVG(score)]

### Candidate Synonyms (column aliases used by analysts)
| Physical Column | Aliases Used | Pattern Count |
|-----------------|-------------|---------------|
[e.g., TOTAL_MONTHLY_VALUE → "monthly_spend", "household_value"]

## Agent Instruction Recommendations

Sample questions for the Cortex Agent (derived from most common patterns):
1. {natural language version of Pattern 1}
2. {natural language version of Pattern 2}
3. {natural language version of Pattern 3}
[up to 6 questions]

**Agent context from business rules:** Include CASE WHEN mappings in agent instructions:
[e.g., "ICCID prefix 89012 = T-Mobile, 89014 = AT&T, 89105 = DISH"]

## Executive Talking Points

- **Data silo cost:** {N} cross-DB join patterns across {N} users = manual integration tax
- **Analytics gap:** {domain} has {N} analyst patterns despite {N} ETL queries — invisible to business
- **Semi-structured tax:** {N} patterns require VARIANT parsing → named columns in semantic view
- **Can't-move data:** {real-time/compliance/high-frequency signals from Phase F}

## Next Steps

- Feed **Domain Heat Map** into ontology class design (03_ontology_architect_agent.md)
- Feed **Cross-DB Join Chains** into relations.json (pre-seeded like join_graph.md)
- Feed **Candidate Facts/Dimensions/Metrics** into semantic view creation
- Feed **Candidate Synonyms** into semantic view WITH SYNONYMS clauses
- Feed **Agent Instruction Recommendations** into agent sample_questions
- Feed **Business rules** from CASE WHEN into agent instruction context
- Use **Executive Talking Points** in demo walkthrough and slide deck
- Use **Gap Analysis** to position: "here's what your analysts can't do today"
```

---

## Completion Summary

After **all** files are written, print:

```
SNOWHOUSE SCAFFOLD COMPLETE — {CUSTOMER_NAME}
================================================
Account: {SF_ACCT_NAME} (ID: {ACCOUNT_ID})
Deployment: {DEPLOYMENT}  |  Edition: {SF_SERVICE}

Databases scaffolded: {N}
Tables scaffolded:    {N}
Total columns:        {N}
Seed rows generated:  {N}

OUTPUT:
  demo_tables.sql     → customers/{company_slug}/demo_tables.sql
  schema_summary.md   → customers/{company_slug}/schema_summary.md
  join_graph.md       → customers/{company_slug}/join_graph.md       (if join graph ran)
  query_patterns.md   → customers/{company_slug}/query_patterns.md   (if query text available)

NEXT STEP:
  1. Run 01_company_research_agent.md (web research)
  2. Open 03_ontology_architect_agent.md
     → Read schema_summary.md BEFORE Step 2
     → Read join_graph.md if present — pre-seeds relations.json
     → Read query_patterns.md if present — provides SV recommendations
     → Map ontology classes to real table names in Step 5
  3. Run 04_demo_builder_agent.md
     → KG_NODE/KG_EDGE build on top of demo_tables.sql
     → Use query_patterns.md for semantic view facts/dimensions/metrics/synonyms
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `SUBSCRIPTIONS_DT` returns 0 rows | Customer name spelling | Try shorter substring or account ID directly |
| `ALL_LIVE_TABLE_COLUMNS` returns 0 rows | DB name case mismatch | Use UPPER() compare; try alternate casing |
| `job_raw_v` returns 0 rows | Wrong DEPLOYMENT | Re-check SF_DEPLOYMENT from SUBSCRIPTIONS_DT |
| Query B returns all NULLs | Flag redaction active on account | Use only Query A rankings; skip Query B |
| `customers/{slug}/` dir missing | First run for this customer | Create dir before writing files |
| Zero-copy share DBs return 0 rows in `ALL_LIVE_TABLE_COLUMNS` | Shared databases (e.g., Salesforce SFMC shares) are owned by the provider account, not the customer — they won't appear in `ALL_LIVE_TABLE_COLUMNS` for the customer's `account_id` | Use `job_raw_v` query text to infer table names from SQL patterns; manually craft DDL from known share schema documentation |
