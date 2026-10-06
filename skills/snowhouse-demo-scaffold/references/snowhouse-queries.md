# Snowhouse Queries Reference

SQL queries for discovering customer accounts, BI warehouses, and high-value objects from Snowhouse metadata.

## Account Discovery

Find all Snowflake accounts for a customer:

```sql
SELECT DISTINCT 
    salesforce_account_id,
    salesforce_account_name, 
    snowflake_account_id,
    snowflake_account_name, 
    snowflake_account_alias,
    snowflake_deployment
FROM FINANCE.CUSTOMER.SUBSCRIPTION
WHERE salesforce_account_name ILIKE '%[CUSTOMER_NAME]%';
```

**Output:** List of accounts. Note `snowflake_deployment` for subsequent queries.

---

## BI Warehouse Identification

Find warehouses used for analytics (replace `[snowflake_deployment]` and `[snowflake_account_id]`):

```sql
SELECT 
    WAREHOUSE_NAME,
    COUNT(*) as query_count,
    AVG(EXECUTION_TIME) as avg_execution_ms,
    SUM(CREDITS_USED) as total_credits,
    COUNT(DISTINCT dpo:"JobDPO:userId"::STRING) as distinct_users
FROM SNOWHOUSE_IMPORT.[snowflake_deployment].JOB_RAW_V
WHERE ACCOUNT_ID = [snowflake_account_id]
  AND START_TIME >= DATEADD(day, -14, CURRENT_TIMESTAMP())
GROUP BY 1
HAVING query_count > 100
ORDER BY query_count DESC;
```

**BI Warehouse Indicators:**
- Names containing: `BI`, `REPORTING`, `ANALYTICS`, `SIGMA`, `TABLEAU`, `LOOKER`, `POWERBI`, `MODE`, `METABASE`, `THOUGHTSPOT`
- High query count with low avg execution time (interactive queries)
- Multiple distinct users (shared reporting warehouse)
- Moderate credit consumption (not ETL-heavy)

---

## High-Value Objects Discovery

Find most-queried tables from BI warehouses:

```sql
SELECT 
    DATABASE_NAME,
    SCHEMA_NAME,
    NAME as object_name,
    OBJECT_TYPE,
    COUNT(*) as query_count,
    COUNT(DISTINCT dpo:"JobDPO:userId"::STRING) as distinct_users
FROM SNOWHOUSE_IMPORT.[snowflake_deployment].TABLE_ETL_V
WHERE ACCOUNT_ID = [snowflake_account_id]
  AND WAREHOUSE_NAME IN ([BI_WAREHOUSES])
  AND QUERY_START_TIME >= DATEADD(day, -14, CURRENT_TIMESTAMP())
GROUP BY 1, 2, 3, 4
ORDER BY query_count DESC
LIMIT 100;
```

---

## Query Patterns Analysis

Extract business queries with aggregations:

```sql
SELECT 
    dpo:"JobDPO:description"::STRING as query_text,
    COUNT(*) as execution_count
FROM SNOWHOUSE_IMPORT.[snowflake_deployment].JOB_RAW_V
WHERE ACCOUNT_ID = [snowflake_account_id]
  AND WAREHOUSE_NAME IN ([BI_WAREHOUSES])
  AND START_TIME >= DATEADD(day, -14, CURRENT_TIMESTAMP())
  AND query_text ILIKE '%SELECT%'
  AND (query_text ILIKE '%SUM(%' OR query_text ILIKE '%COUNT(%' 
       OR query_text ILIKE '%AVG(%' OR query_text ILIKE '%GROUP BY%')
GROUP BY 1
ORDER BY execution_count DESC
LIMIT 50;
```

---

## Column Metadata Extraction

Get column details for top tables:

```sql
SELECT 
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE,
    ORDINAL
FROM SNOWHOUSE_IMPORT.[snowflake_deployment].TABLE_COLUMN_ETL_V
WHERE ACCOUNT_ID = [snowflake_account_id]
  AND DATABASE_NAME = '[DATABASE]'
  AND TABLE_NAME IN ([TOP_TABLES])
ORDER BY TABLE_NAME, ORDINAL;
```

---

## Column Name Mappings

Snowhouse uses different column names than ACCOUNT_USAGE:

| ACCOUNT_USAGE | Snowhouse |
|---------------|-----------|
| QUERY_TEXT | `dpo:"JobDPO:description"::STRING` |
| USER_NAME | `dpo:"JobDPO:userId"::STRING` |
| TABLE_NAME | NAME |
| ORDINAL_POSITION | ORDINAL |

---

## Snowhouse Views Reference

| View | Purpose |
|------|---------|
| `SNOWHOUSE_IMPORT.[deployment].JOB_RAW_V` | Query history and execution details |
| `SNOWHOUSE_IMPORT.[deployment].TABLE_ETL_V` | Table access patterns and usage |
| `SNOWHOUSE_IMPORT.[deployment].TABLE_COLUMN_ETL_V` | Column metadata |
| `SNOWHOUSE_IMPORT.[deployment].ACCOUNT_ETL_V` | Account metadata |
| `FINANCE.CUSTOMER.SUBSCRIPTION` | Customer account mapping |

---

## Domain Clustering Patterns

After discovering tables, cluster by naming patterns:

| Pattern | Domain | Example Tables |
|---------|--------|----------------|
| `FACT_`, `ORDER`, `DELIVERY`, `TRANSACTION`, `EVENT` | Operations | FACT_ORDERS, MAINDBLOCAL_DELIVERY |
| `DIM_`, `DIMENSION_`, `MASTER_`, `LOOKUP` | Dimensions | DIMENSION_STORE, DIM_DATE |
| `USER`, `CUSTOMER`, `CONSUMER`, `MEMBER` | Users | DIMENSION_CONSUMERS, USER_PROFILE |
| `PRODUCT`, `CATALOG`, `ITEM`, `SKU` | Products | CATALOG_UMP, PRODUCT_MASTER |
| `CAMPAIGN`, `AD_`, `PROMOTION` | Marketing | DIM_CAMPAIGN_HISTORY |
| `REVENUE`, `COST`, `PAYMENT`, `CURRENCY` | Finance | FACT_REVENUE, PAYMENTS |
