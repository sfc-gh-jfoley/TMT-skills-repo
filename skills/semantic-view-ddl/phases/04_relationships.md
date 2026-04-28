---
name: sv-ddl-phase4-relationships
description: Detect foreign key relationships between tables using column naming patterns, confirm with user, and validate with cardinality checks
---

# Phase 4: Relationship Detection

## Purpose
Identify which tables join to which, and on which columns.
Wrong or missing relationships are the most common cause of bad Cortex Analyst SQL generation.

---

## Step 4.1: Auto-detect candidate relationships

Scan `TABLE_PROFILES` for FK column naming patterns.

### Pattern matching rules

For every pair of tables (A, B):

1. **Exact name match**: column `X` appears in both tables → candidate join on `X`
2. **Table-prefixed FK**: table B has primary key `B_ID`; table A has column `B_ID` → A.B_ID → B.B_ID
3. **Suffix match**: table A has `<prefix>_ID` and table B has a column matching `<prefix>` or `<prefix>_ID`
4. **Common FK suffixes**: `_KEY`, `_CODE`, `_NBR`, `_NO`, `_SK`

```python
# Pseudocode for pattern detection
for col_a in table_a.columns:
    for col_b in table_b.columns:
        if col_a.name == col_b.name and col_a.name ends with FK_SUFFIXES:
            → candidate join: table_a.col_a → table_b.col_b
```

Also check for existing foreign key constraints:
```sql
SELECT
    fk.TABLE_NAME,
    fk.COLUMN_NAME,
    pk.TABLE_NAME AS REF_TABLE,
    pk.COLUMN_NAME AS REF_COLUMN
FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE fk ON rc.CONSTRAINT_NAME = fk.CONSTRAINT_NAME
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE pk ON rc.UNIQUE_CONSTRAINT_NAME = pk.CONSTRAINT_NAME
WHERE fk.TABLE_SCHEMA = '<schema>';
```

(This often returns nothing in Snowflake since FK constraints are not enforced, but worth checking.)

---

## Step 4.2: Validate candidate joins with cardinality check

For each candidate join, verify it's actually N:1 (many-to-one) and not M:N:

```sql
-- Does table_a.fk_col have all values in table_b.pk_col? (referential integrity)
SELECT
    COUNT(*)                                    AS total_a,
    COUNT(DISTINCT a.<fk_col>)                  AS distinct_fk_values,
    COUNT(DISTINCT b.<pk_col>)                  AS distinct_pk_values,
    -- Check if FK values all exist in PK
    SUM(CASE WHEN b.<pk_col> IS NULL THEN 1 ELSE 0 END) AS unmatched_rows
FROM <table_a> a
LEFT JOIN <table_b> b ON a.<fk_col> = b.<pk_col>
LIMIT 1000000;
```

Use results to classify:
- `unmatched_rows > 0` → data quality warning (note it, but don't block)
- `distinct_fk_values ≈ total_a` → likely a 1:1 join
- `distinct_fk_values << total_a` → N:1 (many-to-one) — the expected case

---

## Step 4.3: Present relationship candidates for confirmation

```
Detected relationships (confirm or edit):

  1. line_items → orders  (MANY-TO-ONE)
     line_items.ORDER_ID references orders.ORDER_ID
     Cardinality: 120,000 line_items, 30,000 distinct ORDER_ID → ~4 items/order ✓

  2. orders → customers  (MANY-TO-ONE)
     orders.CUSTOMER_ID references customers.CUSTOMER_ID
     Cardinality: 30,000 orders, 8,500 distinct CUSTOMER_ID → ~3.5 orders/customer ✓

  3. vehicles → dealers  (MANY-TO-ONE)  ⚠️ WARNING: 234 unmatched rows
     vehicles.DEALER_ID references dealers.DEALER_ID
     234 vehicles have DEALER_ID values not in dealers table

No relationship detected between: orders ↔ vehicles (no common ID columns found)

Add missing relationships? Remove any above? (type changes or 'ok')
```

⚠️ **STOPPING POINT** — Wait for user to confirm.

---

## Step 4.4: Identify the "one" side — PRIMARY KEY confirmation

For each relationship, the right-hand (referenced) table **must** have PRIMARY KEY or UNIQUE on the join column.

For each reference table, run uniqueness check:
```sql
SELECT
    COUNT(*)                        AS total_rows,
    COUNT(DISTINCT <pk_col>)        AS distinct_values,
    COUNT(*) - COUNT(DISTINCT <pk_col>) AS duplicates
FROM <db>.<schema>.<ref_table>;
```

- `duplicates = 0` → can safely use `PRIMARY KEY (<pk_col>)` ✓
- `duplicates > 0` → the column is NOT a unique key; use `UNIQUE` only if a composite key is needed, or redesign

Report to user if any reference table fails the uniqueness check.

---

## Step 4.5: Handle multiple relationships between same table pair

If two tables have more than one relationship (e.g. `flights → airports` via both `departure_airport` and `arrival_airport`):

```
⚠️  Multiple relationships detected: flights → airports
    1. flights.DEPARTURE_AIRPORT → airports.AIRPORT_CODE  (named: flight_departure_airport)
    2. flights.ARRIVAL_AIRPORT   → airports.AIRPORT_CODE  (named: flight_arrival_airport)

Metrics that use both relationships will need USING (relationship_name) clause.
This will be handled automatically in Phase 5.
```

---

## Output variables

| Variable | Contents |
|----------|----------|
| `RELATIONSHIPS` | List of {name, left_table, left_col, right_table, right_col, cardinality_validated} |
| `PRIMARY_KEYS` | Per-table: {table → [pk_cols]} |
| `MULTI_REL_PAIRS` | Pairs of tables with >1 relationship path (need USING clause) |
