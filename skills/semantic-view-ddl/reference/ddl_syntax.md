---
name: semantic-view-ddl-syntax-reference
description: Complete CREATE SEMANTIC VIEW DDL syntax with all pitfalls, examples, and battle-tested rules
---

# CREATE SEMANTIC VIEW — DDL Syntax Reference

## Top-level template

```sql
CREATE [ OR REPLACE ] SEMANTIC VIEW [ IF NOT EXISTS ] <db>.<schema>.<name>
  TABLES ( logicalTable [ , ... ] )
  [ RELATIONSHIPS ( relationshipDef [ , ... ] ) ]
  [ FACTS ( factExpression [ , ... ] ) ]
  [ DIMENSIONS ( dimensionExpression [ , ... ] ) ]
  [ METRICS ( { metricExpression | windowFunctionMetricExpression } [ , ... ] ) ]
  [ COMMENT = '<comment_about_semantic_view>' ]
  [ AI_SQL_GENERATION '<instructions_for_sql_generation>' ]
  [ AI_QUESTION_CATEGORIZATION '<instructions_for_question_categorization>' ]
  [ AI_VERIFIED_QUERIES ( verifiedQuery [ , ... ] ) ]
  [ COPY GRANTS ]
```

---

## Clause grammar

### logicalTable

```sql
[ <table_alias> AS ] <database>.<schema>.<physical_table>
  [ PRIMARY KEY ( <col> [ , ... ] ) ]
  [ UNIQUE ( <col> [ , ... ] ) [ ... ] ]
  [ CONSTRAINT [ <constraint_name> ] DISTINCT RANGE BETWEEN <start_col> AND <end_col> EXCLUSIVE ]
  [ WITH SYNONYMS [ = ] ( '<synonym>' [ , ... ] ) ]
  [ COMMENT = '<table description>' ]
```

### relationshipDef

```sql
[ <rel_name> AS ]
<left_table_alias> ( <fk_col> [ , ... ] )
REFERENCES <right_table_alias>
[ ( <pk_col> [ , ... ] ) ]
```

For ASOF joins (matching on nearest-prior date):
```sql
<left_table_alias> ( <fk_col>, <date_col> )
REFERENCES <right_table_alias> ( <pk_col>, ASOF <date_col> )
```

### factExpression

```sql
[ PRIVATE | PUBLIC ] <table_alias>.<fact_name> AS <sql_expr>
  [ WITH SYNONYMS [ = ] ( '<synonym>' [ , ... ] ) ]
  [ COMMENT = '<description>' ]
```

### dimensionExpression

```sql
[ PUBLIC ] <table_alias>.<dim_name> AS <sql_expr>
  [ WITH SYNONYMS [ = ] ( '<synonym>' [ , ... ] ) ]
  [ COMMENT = '<description>' ]
  [ WITH CORTEX SEARCH SERVICE <db>.<schema>.<css_name> [ USING <col_name> ] ]
```

### metricExpression

```sql
[ { PRIVATE | PUBLIC } ] <table_alias>.<metric_name>
  [ USING ( <relationship_name> [ , ... ] ) ]
  [ NON ADDITIVE BY ( <dim> [ { ASC | DESC } ] [ NULLS { FIRST | LAST } ] [ , ... ] ) ]
  AS <aggregate_sql_expr>
  [ WITH SYNONYMS [ = ] ( '<synonym>' [ , ... ] ) ]
  [ COMMENT = '<description>' ]
```

### windowFunctionMetricExpression

```sql
[ { PRIVATE | PUBLIC } ] <table_alias>.<metric_name>
  AS <window_function> ( <metric> ) OVER (
    [ PARTITION BY { <exprs_using_dimensions_or_metrics> | EXCLUDING <dimensions> } ]
    [ ORDER BY <exprs_using_dimensions_or_metrics> [ ASC | DESC ] [ NULLS { FIRST | LAST } ] [, ...] ]
    [ <windowFrameClause> ]
  )
```

Use `windowFunctionMetricExpression` for running totals, rankings, period-over-period comparisons, etc.
Window function metrics reference other metrics (not raw columns) inside the `OVER` clause.

### verifiedQuery (for AI_VERIFIED_QUERIES)

```sql
<vq_name> AS (
  QUESTION '<natural language question>'
  [ VERIFIED_AT <timestamp> ]
  [ ONBOARDING_QUESTION TRUE | FALSE ]
  [ VERIFIED_BY '( <purpose> = <contact> )' ]
  SQL '<sql_query>'
)
```

---

## Critical rules — violations produce silent wrong results or DDL errors

| # | Rule | Common mistake |
|---|------|----------------|
| 1 | Clause order is **enforced**: TABLES → RELATIONSHIPS → FACTS → DIMENSIONS → METRICS | Putting DIMENSIONS before RELATIONSHIPS |
| 2 | TABLES alone → "No queryable expression" error. Need FACTS **or** DIMENSIONS minimum | Defining only TABLES block |
| 3 | For a direct column reference, the alias **MUST match the physical column name exactly** | `orders.order_date AS order_dt` → broken. Must be `AS o_orderdate` if physical col is `o_orderdate` |
| 4 | Computed expressions **CAN** have a new name | `orders.order_year AS YEAR(o_orderdate)` is valid |
| 5 | A column with the same name appearing in multiple tables → define as fact/dim from **ONE table only**, skip the others | Defining `CUSTOMER_ID` from both orders and customers tables |
| 6 | The **right-hand table** in a REFERENCES clause needs `PRIMARY KEY` or `UNIQUE` on the join column | Referencing a table with no key constraint → join fails |
| 7 | `PRIVATE` is valid on facts and metrics; dimensions only support `PUBLIC` | Using `PRIVATE` on a dimension |
| 8 | When two relationship paths exist between the same pair of tables, use `USING (rel_name)` on the metric | Ambiguous routing causes query errors |
| 9 | `NON ADDITIVE BY` marks a metric as non-additive along the given dimensions (e.g. DISTINCT COUNT by user) | Omitting this causes incorrect roll-up aggregation |
| 10 | `AI_VERIFIED_QUERIES` SQL must reference the logical alias names (not physical table.col), and use the SV's fact/dim/metric names | Using physical table names in VQ SQL |

---

## Common column classification guide

| Column characteristics | Classify as |
|------------------------|-------------|
| `INTEGER`, `NUMBER`, `FLOAT` that represents a measured value | FACT |
| `DATE`, `TIMESTAMP`, `DATETIME` | DIMENSION (time dimension — name it clearly) |
| `VARCHAR`, `TEXT`, `BOOLEAN` that is a category, label, or ID used in filters | DIMENSION |
| Aggregate expression: `SUM(...)`, `COUNT(...)`, `AVG(...)` — not a raw column | METRIC |
| `NUMBER` used as a foreign key / ID (not summed) | DIMENSION |

---

## Full working example (TPC-H)

```sql
CREATE OR REPLACE SEMANTIC VIEW MY_DB.PUBLIC.TPCH_REVENUE_SV
  TABLES (
    orders    AS SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS
      PRIMARY KEY (O_ORDERKEY)
      WITH SYNONYMS = ('sales orders', 'purchase orders')
      COMMENT = 'All customer orders',
    customers AS SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER
      PRIMARY KEY (C_CUSTKEY)
      COMMENT = 'Customer master data',
    line_items AS SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.LINEITEM
      PRIMARY KEY (L_ORDERKEY, L_LINENUMBER)
      COMMENT = 'Individual line items within orders'
  )
  RELATIONSHIPS (
    orders_to_customers AS orders (O_CUSTKEY) REFERENCES customers,
    line_item_to_orders AS line_items (L_ORDERKEY) REFERENCES orders
  )
  FACTS (
    orders.O_TOTALPRICE AS O_TOTALPRICE
      COMMENT = 'Total price of the order',
    line_items.L_EXTENDEDPRICE AS L_EXTENDEDPRICE
      COMMENT = 'Line item extended price before discount',
    line_items.discounted_price AS L_EXTENDEDPRICE * (1 - L_DISCOUNT)
      COMMENT = 'Line item price after applying discount'
  )
  DIMENSIONS (
    customers.C_NAME AS C_NAME
      WITH SYNONYMS = ('customer name', 'client name')
      COMMENT = 'Full name of the customer',
    customers.C_MKTSEGMENT AS C_MKTSEGMENT
      WITH SYNONYMS = ('market segment', 'industry')
      COMMENT = 'Market segment the customer belongs to',
    orders.O_ORDERDATE AS O_ORDERDATE
      COMMENT = 'Date the order was placed',
    orders.order_year AS YEAR(O_ORDERDATE)
      COMMENT = 'Calendar year the order was placed',
    orders.O_ORDERSTATUS AS O_ORDERSTATUS
      WITH SYNONYMS = ('order status', 'status')
      COMMENT = 'Current order status: O (Open), F (Fulfilled), P (Partial)'
  )
  METRICS (
    customers.customer_count AS COUNT(C_CUSTKEY)
      COMMENT = 'Total number of customers',
    orders.total_revenue AS SUM(O_TOTALPRICE)
      COMMENT = 'Sum of all order values',
    orders.avg_order_value AS AVG(O_TOTALPRICE)
      COMMENT = 'Average value per order'
  )
  COMMENT = 'Revenue and customer analytics semantic view on TPC-H data'
  AI_SQL_GENERATION 'Always filter orders by O_ORDERSTATUS when a status is mentioned. Use O_ORDERDATE for all time-based filtering. Prefer COUNT(DISTINCT C_CUSTKEY) for unique customer counts.'
  AI_VERIFIED_QUERIES (
    top_customers AS (
      QUESTION 'Who are the top 10 customers by total revenue?'
      ONBOARDING_QUESTION TRUE
      SQL 'SELECT C_NAME, SUM(O_TOTALPRICE) AS total_revenue
           FROM orders JOIN customers ON O_CUSTKEY = C_CUSTKEY
           GROUP BY C_NAME ORDER BY total_revenue DESC LIMIT 10'
    ),
    monthly_revenue AS (
      QUESTION 'What is total revenue by month?'
      SQL 'SELECT DATE_TRUNC(''month'', O_ORDERDATE) AS month, SUM(O_TOTALPRICE) AS revenue
           FROM orders GROUP BY 1 ORDER BY 1'
    )
  );
```

---

## COMMENT placement — three distinct scopes

There are **three separate places** where `COMMENT` can appear. They are not interchangeable.

| Scope | Where it goes | Example |
|-------|--------------|---------|
| **Per-table** | Inside the TABLES clause, on the table entry | `orders AS db.s.ORDERS ... COMMENT = 'All customer orders'` |
| **Per-fact / per-dim / per-metric** | Inline on the expression, after `WITH SYNONYMS` | `orders.O_TOTALPRICE AS O_TOTALPRICE COMMENT = 'Order total'` |
| **Top-level SV** | After the closing `)` of the METRICS block, before `AI_SQL_GENERATION` | `COMMENT = 'Revenue analytics SV'` at column-0 depth |

**Wrong placements that produce errors or silent bugs:**
- Top-level COMMENT placed *before* METRICS → parser error
- Top-level COMMENT placed *inside* any clause block → misread as table/expression comment or parser error
- Per-table COMMENT placed outside the TABLES clause → attaches to wrong scope

Quick visual:
```sql
CREATE OR REPLACE SEMANTIC VIEW db.s.name
  TABLES (
    orders AS db.s.ORDERS
      COMMENT = 'All orders'        -- ← per-table COMMENT (inside TABLES clause)
  )
  FACTS (
    orders.O_TOTALPRICE AS O_TOTALPRICE
      COMMENT = 'Order total'       -- ← per-fact COMMENT (inline on expression)
  )
  METRICS (
    orders.total_revenue AS SUM(O_TOTALPRICE)
      COMMENT = 'Total revenue'     -- ← per-metric COMMENT (inline on expression)
  )
  COMMENT = 'Revenue analytics SV'  -- ← TOP-LEVEL SV COMMENT (after METRICS closing paren)
  AI_SQL_GENERATION '...';
```

---

## Error cheat sheet

| Error message | Root cause | Fix |
|--------------|-----------|-----|
| `No queryable expression` | TABLES defined but no FACTS or DIMENSIONS | Add at least one FACTS or DIMENSIONS clause |
| `invalid identifier 'X'` | Fact/dim alias doesn't match physical column name | Change alias to match exact physical column name |
| `Duplicate identifier` | Same column name defined in multiple tables' FACTS/DIMENSIONS | Keep definition on one table, remove from others |
| `relationship ... requires primary key` | Right-hand table in REFERENCES has no PRIMARY KEY or UNIQUE | Add PRIMARY KEY to the referenced table |
| `ambiguous relationship` | Two relationship paths between same tables | Add `USING (relationship_name)` on the metric |
| `Object does not exist` | Physical table path wrong or role lacks access | Verify `SELECT * FROM db.schema.table LIMIT 1` first |
| `PRIVATE not allowed on dimension` | Used PRIVATE on a dimension expression | Remove PRIVATE; use PUBLIC or no modifier |
