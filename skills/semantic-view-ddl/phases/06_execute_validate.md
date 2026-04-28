---
name: sv-ddl-phase6-execute-validate
description: Execute the DDL, validate with DESCRIBE SEMANTIC VIEW, and run a self-test question loop — iterate until passing
---

# Phase 6: Execute & Validate

## Purpose
Execute the DDL, confirm it was created correctly, and run a self-test question loop to verify Cortex Analyst can answer business questions from it.
This is the **iterative core** of the skill — failures loop back to Phase 5 for DDL fixes.

---

## Step 6.1: Execute the DDL

```sql
<paste DDL from Phase 5>
```

**Expected result**: `Semantic view <name> successfully created.`

**If DDL fails**, go to Step 6.2 (error handling). Otherwise proceed to Step 6.3.

---

## Step 6.2: Error handling map

| Error message | Root cause | Fix (return to Phase 5) |
|--------------|-----------|------------------------|
| `No queryable expression` | No FACTS or DIMENSIONS defined | Add at least one FACTS clause |
| `invalid identifier '<X>'` | Fact/dim alias doesn't match physical column name | Change `AS <X>` to match exact physical column name from DESCRIBE TABLE |
| `Duplicate identifier '<X>'` | Column `<X>` defined in multiple tables' FACTS/DIMS | Keep it in one table, remove from others |
| `Object '<table>' does not exist or not authorized` | Physical table path wrong or no access | Run `SELECT * FROM <table> LIMIT 1` to verify; fix path |
| `Relationship '<r>' requires a primary key` | Right-hand REFERENCES table has no PK/UNIQUE | Add `PRIMARY KEY (<col>)` to that table in TABLES clause |
| `Ambiguous relationship` | Two paths between same table pair, no USING | Add `USING (<rel_name>)` to the affected metric |
| `PRIVATE not allowed` | PRIVATE on a dimension | Remove PRIVATE modifier |

After identifying the error:
1. Fix the DDL in Phase 5
2. Re-run the self-check (Step 5.8)
3. Return to Step 6.1

---

## Step 6.3: Structural validation with DESCRIBE

```sql
DESCRIBE SEMANTIC VIEW <SV_DB>.<SV_SCHEMA>.<SV_NAME>;
```

Verify the output contains:
- ✅ All expected tables (rows with `object_kind = 'TABLE'`)
- ✅ All expected facts (rows with `object_kind = 'FACT'`)
- ✅ All expected dimensions (rows with `object_kind = 'DIMENSION'`)
- ✅ All expected metrics (rows with `object_kind = 'METRIC'`)
- ✅ All relationships (rows with `object_kind = 'RELATIONSHIP'`)

Report a summary:
```
DESCRIBE results:
  Tables:        N ✓
  Facts:         N ✓ / N expected
  Dimensions:    N ✓ / N expected
  Metrics:       N ✓ / N expected
  Relationships: N ✓
```

If any counts are lower than expected, find the missing element and fix.

---

## Step 6.4: Cortex Analyst self-test question loop

Test the semantic view by asking 3-5 sample questions via Cortex Analyst.

Generate test questions automatically from `BUSINESS_CONTEXT` and `COLUMN_CLASSES`:
- One aggregate question (SUM or COUNT a METRIC)
- One filter question (filter on a DIMENSION)
- One time-series question (group by TIME_DIMENSION)
- One join question (metric from one table, filter from another)
- One from `PROPOSED_METRICS` if available

Execute via SQL:
```sql
SELECT SNOWFLAKE.CORTEX.ANALYST(
  '<natural language question>',
  OBJECT_CONSTRUCT(
    'semantic_view', '<SV_DB>.<SV_SCHEMA>.<SV_NAME>'
  )
) AS result;
```

Or use DATA_AGENT_RUN if an agent exists for this SV.

For each question, capture:
- The generated SQL
- Any error or "I don't understand" response
- Whether the SQL looks semantically correct

---

## Step 6.5: Self-evaluate test results

For each test question, score:

| Result | Score | Action |
|--------|-------|--------|
| Valid SQL returned, uses expected tables/columns | PASS ✓ | Continue |
| Valid SQL but uses unexpected join path or wrong column | WARN ⚠️ | Note for Phase 7 iteration |
| "I cannot answer" or empty response | FAIL ✗ | Identify root cause |
| SQL error when executed | FAIL ✗ | Fix DDL or add description clarity |

**Common FAIL root causes**:

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Metric not found | Column classified wrong (FACT should be METRIC) | Move from FACTS to METRICS as aggregate expression |
| Wrong table joined | Relationship missing | Add relationship in Phase 4, regenerate DDL |
| Filter not working | DIMENSION missing or misnamed | Check DIMENSION alias matches user's expected filter language |
| Date truncation wrong | No AI_SQL_GENERATION instruction for date handling | Add date format instruction to AI_SQL_GENERATION |
| Wrong aggregation | Ambiguous metric direction | Add description to METRIC with explicit aggregation note |

---

## Step 6.6: Present validation results

```
Validation Results for <SV_NAME>

  DDL execution:    ✓ Success
  DESCRIBE check:   ✓ 4 tables, 18 facts, 22 dimensions, 6 metrics, 3 relationships

  Self-test questions:
    ✓ "What is total inventory value by dealer?"   → SUM(LIST_PRICE) GROUP BY DEALER_NAME
    ✓ "How many vehicles are active?"              → COUNT(*) WHERE LISTING_STATUS = 'ACTIVE'
    ✓ "Show vehicles by month of acquisition"     → GROUP BY DATE_TRUNC('month', ACQUISITION_DATE)
    ✗ "Which dealers have the most aged inventory?" → failed: DAYS_IN_INVENTORY not found
    ⚠️ "Average list price by market segment"     → joined on wrong table

  Issues found: 2
  Recommendation: Fix DAYS_IN_INVENTORY classification + add market segment relationship
```

---

## Step 6.7: Decide — iterate or proceed

If **0 failures**: proceed to Phase 7 (enrichment / verified queries).

If **any failures**: return to Phase 5 with the specific fixes identified. Increment iteration counter.

**Iteration limit**: after 3 rounds without progress, stop and present the issues to the user for manual input.

⚠️ **STOPPING POINT** — Present validation results. Ask:
```
Validation complete.
  Passed: N/N questions
  Issues: N

Options:
  1. Fix and iterate → return to Phase 5
  2. Accept as-is → proceed to Phase 7 (add verified queries, export)
  3. Show me the failing SQL so I can debug it manually
```
