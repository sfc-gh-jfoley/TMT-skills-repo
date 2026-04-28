---
name: sv-ddl-phase5-generate
description: Generate the CREATE SEMANTIC VIEW DDL from classified columns and relationships, with built-in self-check before presenting to user
---

# Phase 5: Generate DDL

## Purpose
Build the complete `CREATE OR REPLACE SEMANTIC VIEW` statement from the classified columns, relationships, and descriptions collected in Phases 1-4.

**Read [../reference/ddl_syntax.md](../reference/ddl_syntax.md) before generating any DDL.**

---

## Step 5.1: Build the TABLES clause

For each table in `SOURCE_TABLES`, generate the table entry.

**Template**:
```sql
<logical_alias> AS <DB>.<SCHEMA>.<PHYSICAL_TABLE>
  PRIMARY KEY ( <pk_col> [ , ... ] )       -- from RELATIONSHIPS.PRIMARY_KEYS
  WITH SYNONYMS = ( '<alias1>', '<alias2>' )  -- from BUSINESS_CONTEXT or table description
  COMMENT = '<table description>'            -- from COLUMN_DESCRIPTIONS or BUSINESS_CONTEXT
```

Rules:
- `logical_alias` should be lowercase + underscore for readability: `vehicles`, `dealers`, `orders`
- If no primary key was confirmed in Phase 4, use `UNIQUE (<best_candidate>)` instead
- Table COMMENT = generated table-level description from Phase 2

---

## Step 5.2: Build the RELATIONSHIPS clause

For each relationship in `RELATIONSHIPS`:

```sql
<rel_name> AS <left_alias> ( <left_col> ) REFERENCES <right_alias>
```

Naming convention for `rel_name`: `<left_alias>_to_<right_alias>` (e.g. `line_items_to_orders`)

If the right table has a different PK column name than the FK column:
```sql
<rel_name> AS <left_alias> ( <fk_col> ) REFERENCES <right_alias> ( <pk_col> )
```

---

## Step 5.3: Build the FACTS clause

For each column with `class = "FACT"` in `COLUMN_CLASSES`:

```sql
<table_alias>.<fact_name> AS <physical_col_name>
  WITH SYNONYMS = ( '<syn1>', '<syn2>' )
  COMMENT = '<description>'
```

⚠️ **CRITICAL RULE**: For direct column references, the alias after `AS` **must exactly match the physical column name**.
- ✅ `orders.O_TOTALPRICE AS O_TOTALPRICE`
- ❌ `orders.total_price AS O_TOTALPRICE` → will fail with "invalid identifier"

For computed expressions (derived facts), the new name is fine:
- ✅ `line_items.discounted_price AS L_EXTENDEDPRICE * (1 - L_DISCOUNT)`

**Duplicate column names across tables**: if two tables both have `AMOUNT`, define it in **one table only** (the primary source). Skip the duplicate in the other table.

---

## Step 5.4: Build the DIMENSIONS clause

For each column with `class = "DIMENSION"` or `class = "TIME_DIMENSION"`:

```sql
<table_alias>.<dim_name> AS <physical_col_name>
  WITH SYNONYMS = ( '<syn1>', '<syn2>' )
  COMMENT = '<description>'
```

Same alias rule applies: alias must match physical column name for direct references.

For computed dimensions (e.g. extracting year from date):
```sql
<table_alias>.order_year AS YEAR(<physical_date_col>)
  COMMENT = 'Calendar year extracted from order date'
```

**Cortex Search attachment** — for any dimension in `CSS_ATTACHMENTS`, append `WITH CORTEX SEARCH SERVICE`
as the **last** modifier, after `COMMENT`:

```sql
<table_alias>.<dim_name> AS <physical_col_name>
  WITH SYNONYMS = ( '<syn1>', '<syn2>' )
  COMMENT = '<description>'
  WITH CORTEX SEARCH SERVICE <db>.<schema>.<css_name>
```

⚠️ **No `AS` on the `WITH CORTEX SEARCH SERVICE` line** — it is a clause modifier, not an expression.
⚠️ **Clause order within a dimension**: `AS <expr>` → `WITH SYNONYMS` → `COMMENT` → `WITH CORTEX SEARCH SERVICE`

---

## Step 5.5: Build the METRICS clause

For each entry in `PROPOSED_METRICS`:

```sql
<table_alias>.<metric_name>
  [ USING ( <rel_name> ) ]      -- only if MULTI_REL_PAIRS includes this table pair
  AS <aggregate_expr>
  WITH SYNONYMS = ( '<syn1>', '<syn2>' )
  COMMENT = '<description>'
```

Add `USING` clause for any metric that is ambiguous due to multiple relationship paths (from `MULTI_REL_PAIRS`).

---

## Step 5.6: Build AI_SQL_GENERATION instructions

Compose a targeted instruction block from `BUSINESS_CONTEXT`:

```sql
AI_SQL_GENERATION '
  <summarize key SQL generation rules derived from business context>
  Examples:
  - Always filter by STATUS = ''ACTIVE'' unless user asks for all statuses.
  - Use ACQUISITION_DATE for time-based filtering, not LAST_MODIFIED_AT.
  - Prefer COUNT(DISTINCT DEALER_ID) for unique dealer counts.
'
```

---

## Step 5.6.5: Build AI_QUESTION_CATEGORIZATION instructions (optional)

`AI_QUESTION_CATEGORIZATION` tells Cortex Analyst how to route or classify user questions — for example,
directing operational questions vs. analytical questions to different tools or response styles.

Include this clause when:
- The semantic view spans multiple distinct subject areas (e.g., inventory + billing + network)
- The business context mentions distinct user personas or use-case buckets
- You want the agent to distinguish question types (e.g., "lookup" vs. "aggregate trend")

Template:
```sql
AI_QUESTION_CATEGORIZATION '
  <describe how to categorize incoming questions>
  Examples:
  - Questions about individual records or lookups → respond with a direct lookup query.
  - Questions about trends or aggregates → respond with a GROUP BY or window query.
  - Questions about <subject_area_A> → focus on <table_alias_A> and its relationships.
'
```

If the business context is narrow and single-domain, this clause can be omitted. When in doubt, include a
minimal categorization that separates lookups from aggregates.

---

## Step 5.7: Assemble the full DDL

Combine all sections in the **mandatory order**: TABLES → RELATIONSHIPS → FACTS → DIMENSIONS → METRICS

Template:
```sql
CREATE OR REPLACE SEMANTIC VIEW <SV_DB>.<SV_SCHEMA>.<SV_NAME>
  TABLES (
    <table entries>
  )
  RELATIONSHIPS (
    <relationship entries>
  )
  FACTS (
    <fact entries>
  )
  DIMENSIONS (
    <dimension entries>
  )
  METRICS (
    <metric entries>
  )
  COMMENT = '<semantic view description>'
  AI_SQL_GENERATION '<generation instructions>'
  [ AI_QUESTION_CATEGORIZATION '<categorization instructions>' ];
```

If no relationships: omit the RELATIONSHIPS block entirely (do not leave it empty).
If AI_QUESTION_CATEGORIZATION was not needed (Step 5.6.5): omit that clause entirely.

---

## Step 5.8: Self-check before presenting to user

Before showing the DDL to the user, perform these checks internally:

### Syntax self-checks (all must pass)

| Check | How to verify |
|-------|--------------|
| Clause order: TABLES → RELATIONSHIPS → FACTS → DIMENSIONS → METRICS | Read the generated DDL top-to-bottom |
| Every fact/dim with direct column ref has alias = physical column name | Compare `AS <alias>` against `DESCRIBE TABLE` column list |
| No duplicate column names across FACTS sections | Scan all FACTS entries for repeated alias names |
| Every REFERENCES table has PRIMARY KEY or UNIQUE defined | Check TABLES clause for each right-hand table in RELATIONSHIPS |
| USING clause present for every metric involving a MULTI_REL_PAIRS table pair | Cross-reference metrics against MULTI_REL_PAIRS list |
| No empty RELATIONSHIPS block | If 0 relationships, block must be absent entirely |
| Physical table names are fully qualified (`DB.SCHEMA.TABLE`) | Scan TABLES clause |
| String literals in metric expressions use single-quotes with NO extra escaping — `COUNT_IF(OUTCOME = 'WON')` is correct; `COUNT_IF(OUTCOME = ''WON'')` is **wrong** and will fail at execution | Scan every `AS <aggregate_expr>` in METRICS for `''` double-quote patterns |
| Non-standard column names (from `NON_STANDARD_COLUMNS`) are double-quoted **everywhere** they appear: in `AS <alias>`, inside computed expressions, and in `AI_SQL_GENERATION` examples. Use `REPLACE(col_name, '"', '""')` for names that themselves contain a double-quote character. Example: `t."user@email.com" AS "user@email.com"`. Standard names (`[A-Z0-9_]` only, not starting with digit) need no quoting. | Cross-reference every column name in FACTS/DIMENSIONS/METRICS against `NON_STANDARD_COLUMNS`; fail if any appears unquoted |
| **COMMENT placement** — three distinct scopes, each goes in the right place: (1) per-table COMMENT inside the TABLES clause on the table entry, (2) per-fact/dim/metric COMMENT inline on the expression, (3) top-level SV COMMENT appears **after the closing `)` of the METRICS block**, before `AI_SQL_GENERATION`. A top-level COMMENT inside any clause, or placed before METRICS, is a bug. | Scan the assembled DDL: top-level COMMENT must appear at column-0 depth, after `  )` of METRICS |
| **`WITH CORTEX SEARCH SERVICE` placement and syntax** — must appear as the **last** modifier on a dimension, after `COMMENT`. No `AS` keyword on this line — it is a clause modifier, not an expression. Wrong order or adding `AS` will cause a parser error. | Scan all dimensions in `CSS_ATTACHMENTS`: confirm CSS line is last, has no `AS` |

### Self-check output

Present internally (not to user yet):
```
Self-check: 11/11 checks passed ✓
Proceeding to present DDL.
```

If any check fails — **fix the DDL first**, then re-run self-check. Do not present broken DDL to user.

---

## Step 5.9: Present DDL to user

Present the full DDL in a code block. Include a brief summary:

```
✅ DDL generated — self-check passed

Semantic View: <SV_DB>.<SV_SCHEMA>.<SV_NAME>
  Tables:        N  (<list of logical aliases>)
  Relationships: N
  Facts:         N  (direct column references)
  Dimensions:    N  (including N time dimensions)
  Metrics:       N  (aggregate expressions)

[DDL here]

Next step: Phase 6 — execute and validate.
Type 'go' to execute, or make edits first.
```

⚠️ **STOPPING POINT** — Wait for user to approve or request changes.
