---
name: sv-ddl-phase7-iterate-enrich
description: Add AI_VERIFIED_QUERIES, iterate on description quality, and export final DDL for HOLs or version control
---

# Phase 7: Iterate & Enrich

## Purpose
Polish the semantic view after initial validation:
1. Add `AI_VERIFIED_QUERIES` (curated Q&A pairs for Cortex Analyst)
2. Improve descriptions based on what failed in Phase 6
3. Export the final DDL for HOL setup scripts or version control

This phase repeats as many times as needed.

---

## Step 7.1: Generate AI_VERIFIED_QUERIES

`AI_VERIFIED_QUERIES` embeds curated question→SQL pairs directly in the semantic view DDL.
These are displayed as starter questions in Snowflake Intelligence and improve Cortex Analyst's accuracy.

Ask user: "Do you want to add verified queries (example questions and their SQL)? These become the onboarding questions shown in Snowflake Intelligence."

### Auto-generate from passing self-test questions

Use the passing questions from Phase 6 as the foundation:

```sql
ALTER SEMANTIC VIEW <SV_DB>.<SV_SCHEMA>.<SV_NAME>
  SET AI_VERIFIED_QUERIES = (
    <vq_name_1> AS (
      QUESTION '<passing question from Phase 6 test>'
      ONBOARDING_QUESTION TRUE
      SQL '<validated SQL from Phase 6 test>'
    )
    [ , ... ]
  );
```

Alternatively, rebuild the SV with `AI_VERIFIED_QUERIES` in the `CREATE OR REPLACE` statement:

```sql
CREATE OR REPLACE SEMANTIC VIEW <SV_DB>.<SV_SCHEMA>.<SV_NAME>
  TABLES ( ... )
  RELATIONSHIPS ( ... )
  FACTS ( ... )
  DIMENSIONS ( ... )
  METRICS ( ... )
  COMMENT = '...'
  AI_SQL_GENERATION '...'
  AI_VERIFIED_QUERIES (
    q1 AS (
      QUESTION 'What is total inventory value by dealer?'
      ONBOARDING_QUESTION TRUE
      SQL 'SELECT DEALER_NAME, SUM(LIST_PRICE) AS total_value
           FROM vehicles
           JOIN dealers ON vehicles.DEALER_ID = dealers.DEALER_ID
           GROUP BY DEALER_NAME
           ORDER BY total_value DESC'
    ),
    q2 AS (
      QUESTION 'How many active vehicles are currently listed?'
      ONBOARDING_QUESTION TRUE
      SQL 'SELECT COUNT(*) AS active_vehicle_count
           FROM vehicles
           WHERE LISTING_STATUS = ''ACTIVE'''
    ),
    q3 AS (
      QUESTION 'Show average days on lot by vehicle make'
      SQL 'SELECT MAKE, AVG(DAYS_IN_INVENTORY) AS avg_days_on_lot
           FROM vehicles
           GROUP BY MAKE
           ORDER BY avg_days_on_lot DESC'
    )
  );
```

**Note**: Single quotes inside SQL strings must be escaped as `''` (two single quotes).

---

## Step 7.2: Improve descriptions for failed questions

For each question that failed or warned in Phase 6, improve the relevant column descriptions:

### Option A: Patch individual column descriptions

```sql
-- Improve a dimension description to help Cortex Analyst understand it
ALTER SEMANTIC VIEW <SV_DB>.<SV_SCHEMA>.<SV_NAME>
  ALTER DIMENSION <table_alias>.<dim_name>
  SET COMMENT = '<improved description with explicit values and usage guidance>';
```

### Option B: Rebuild with CREATE OR REPLACE

For multi-column fixes, it's cleaner to `CREATE OR REPLACE` the entire SV with updated COMMENT clauses.
Use the DDL generated in Phase 5 as the base — edit the specific COMMENT strings and re-execute.

After any description change:
1. Re-run the failing questions from Phase 6 Step 6.4
2. If they now pass → PASS ✓
3. If still failing → investigate further or note for `AI_SQL_GENERATION` instruction

---

## Step 7.3: Refine AI_SQL_GENERATION instructions

Based on patterns observed in Phase 6, extend the `AI_SQL_GENERATION` block:

Common additions:
- Default filter clauses: `Always filter LISTING_STATUS = 'ACTIVE' unless the user asks for all statuses`
- Preferred join paths: `When joining vehicles to dealers, use the dealer_to_vehicles relationship`
- Date handling: `Use DATE_TRUNC('month', ACQUISITION_DATE) for monthly grouping`
- Aggregation preferences: `Use COUNT(DISTINCT DEALER_ID) for unique dealer counts, not COUNT(*)`

Update via:
```sql
ALTER SEMANTIC VIEW <SV_DB>.<SV_SCHEMA>.<SV_NAME>
  SET AI_SQL_GENERATION = '<updated instructions>';
```

---

## Step 7.4: Export final DDL

Generate the complete final DDL with all enrichments for:
- HOL setup scripts (`hol_setup.sql`)
- Version control
- Sharing with colleagues

```sql
-- Complete final DDL:
CREATE OR REPLACE SEMANTIC VIEW <SV_DB>.<SV_SCHEMA>.<SV_NAME>
  TABLES ( ... )
  RELATIONSHIPS ( ... )
  FACTS ( ... )
  DIMENSIONS ( ... )
  METRICS ( ... )
  COMMENT = '...'
  AI_SQL_GENERATION '...'
  AI_VERIFIED_QUERIES ( ... );
```

Present this as a complete, self-contained SQL block the user can paste into any worksheet or setup script.

---

## Step 7.5: Final summary

```
✅ Semantic View Complete

  <SV_DB>.<SV_SCHEMA>.<SV_NAME>

  Tables:          N
  Facts:           N
  Dimensions:      N  (including N time dimensions)
  Metrics:         N
  Relationships:   N
  Verified Queries: N  (N marked as onboarding questions)

  Self-test: N/N questions passing
  Descriptions: AI-generated for N columns

  DDL saved above — copy to hol_setup.sql or version control.

Next options:
  - Add this SV to a Cortex Agent   → run cortex-agent skill
  - Add more verified queries       → repeat Phase 7
  - Optimize with Cortex Analyst    → run semantic-view skill (existing/optimization path)
  - Run agent evaluation            → run agent-flag-tester skill
```

⚠️ **STOPPING POINT** — Present final summary and wait for user's next action.
