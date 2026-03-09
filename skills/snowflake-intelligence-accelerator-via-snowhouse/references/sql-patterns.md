# SQL Patterns Reference

Critical SQL syntax patterns for Snowflake Intelligence components.

## Semantic View Syntax

**Pattern:** `TABLE_ALIAS.semantic_name AS actual_source_column`
- LEFT side: User-friendly name for AI/analysts to query
- RIGHT side: **MUST EXACTLY MATCH** column in source table

```sql
CREATE OR REPLACE SEMANTIC VIEW MY_SEMANTIC_VIEW
    TABLES (
        ALIAS AS SCHEMA.TABLE_NAME
            WITH SYNONYMS = ('synonym1', 'synonym2')
            COMMENT = 'Description of the table'
    )
    FACTS (
        ALIAS.revenue AS AMOUNT_USD
            WITH SYNONYMS = ('sales', 'income')
            COMMENT = 'Revenue in USD',
        ALIAS.delivery_fee AS FEE
            COMMENT = 'Delivery fee in cents'
    )
    DIMENSIONS (
        ALIAS.market_id AS MARKET
            WITH SYNONYMS = ('region')
            COMMENT = 'Market identifier'
    );
```

**Common Errors:**
```sql
-- WRONG: Column name mismatch
DELIVERIES.delivery_fee AS DELIVERY_FEE    -- DELIVERY_FEE doesn't exist

-- CORRECT: Actual column name
DELIVERIES.delivery_fee AS FEE             -- FEE exists in source
```

**Rules:**
- Keywords UPPERCASE with spaces: `WITH SYNONYMS =`, `COMMENT =`
- Always verify actual column names in base tables first

---

## Cortex Search Service Syntax

**Single search column required** - concatenate fields into SEARCH_TEXT:

```sql
CREATE OR REPLACE CORTEX SEARCH SERVICE my_search_service
ON SEARCH_TEXT
WAREHOUSE = my_warehouse
TARGET_LAG = '1 day'
AS (
    SELECT 
        id,
        product_name,
        category,
        brand,
        CONCAT(
            COALESCE(product_name, ''), ' ',
            COALESCE(category, ''), ' ',
            COALESCE(brand, '')
        ) AS SEARCH_TEXT
    FROM source_table
);
```

**Wrong:**
```sql
ON product_name, category, brand  -- ERROR: multiple columns not allowed
```

---

## Agent Creation Syntax

**Use `FROM SPECIFICATION` syntax** (not direct table insert):

```sql
CREATE OR REPLACE AGENT SNOWFLAKE_INTELLIGENCE.AGENTS.[CUSTOMER]_Platform_Agent
WITH PROFILE='{ "display_name": "[Customer] Platform Intelligence Agent" }'
    COMMENT='Description'
FROM SPECIFICATION $$
{
  "models": { "orchestration": "" },
  "instructions": {
    "response": "You are a [Customer] data analyst...",
    "orchestration": "Use semantic views for analytics...",
    "sample_questions": [
      {"question": "What are the top 10 markets?"},
      {"question": "Compare performance across segments"}
    ]
  },
  "tools": [
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "Query Operations",
        "description": "Query operations data..."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_search",
        "name": "Search Products",
        "description": "Search products..."
      }
    },
    {
      "tool_spec": {
        "type": "generic",
        "name": "Generate_Streamlit_App",
        "description": "Generate dashboards...",
        "input_schema": {
          "type": "object",
          "properties": {
            "user_input": {
              "description": "Dashboard requirements",
              "type": "string"
            }
          },
          "required": ["user_input"]
        }
      }
    }
  ],
  "tool_resources": {
    "Query Operations": {
      "semantic_view": "SI_[CUSTOMER].[CUSTOMER]_SNOW_INTELLIGENCE.SEMANTIC_VIEW"
    },
    "Search Products": {
      "name": "SI_[CUSTOMER].[CUSTOMER]_SNOW_INTELLIGENCE.SEARCH_SERVICE",
      "id_column": "PRODUCT_ID",
      "title_column": "PRODUCT_NAME",
      "max_results": 10
    },
    "Generate_Streamlit_App": {
      "execution_environment": {
        "query_timeout": 0,
        "type": "warehouse",
        "warehouse": "[CUSTOMER]_snow_intelligence_WH"
      },
      "identifier": "SI_[CUSTOMER].[CUSTOMER]_SNOW_INTELLIGENCE.GENERATE_STREAMLIT_APP",
      "name": "GENERATE_STREAMLIT_APP(VARCHAR)",
      "type": "procedure"
    }
  }
}
$$;

-- Grant access
GRANT USAGE ON AGENT ... TO ROLE PUBLIC;
```

**Tool Parameter Matching:**
`input_schema` property names must EXACTLY match procedure parameter names:
```sql
-- Procedure signature: SEND_MAIL(RECIPIENT_EMAIL VARCHAR, SUBJECT VARCHAR, BODY_CONTENT VARCHAR)

-- WRONG
"properties": { "recipient": {...}, "body": {...} }

-- CORRECT  
"properties": { "recipient_email": {...}, "body_content": {...} }
```

---

## Stored Procedure Gotchas

### Temporary Tables
No fully-qualified names for temp tables:
```sql
-- WRONG
CREATE TEMPORARY TABLE SI_ACME.SCHEMA.temp_pool AS ...

-- CORRECT
CREATE TEMPORARY TABLE temp_pool AS ...
```

### Unsupported Subqueries
Replace scalar subqueries with JOINs:
```sql
-- WRONG (fails in procedures)
SELECT (SELECT id FROM pool ORDER BY random() LIMIT 1) as id FROM generator;

-- CORRECT
SELECT mp.id FROM (
    SELECT uniform(1, 20, random()) as pool_number FROM generator
) gen JOIN pool mp ON gen.pool_number = mp.id;
```

### Procedure Overloading
When changing parameter count, DROP old signature first:
```sql
DROP PROCEDURE IF EXISTS MY_SCHEMA.MY_PROC(VARCHAR, VARCHAR);
CREATE OR REPLACE PROCEDURE MY_SCHEMA.MY_PROC(USER_INPUT VARCHAR) ...
```

---

## Synthetic Data Patterns

### Power-Law Distribution
```sql
-- Some stores much more popular than others
LEAST(CEIL(POW(uniform(0.0, 1.0, random()), 0.5) * :stores_count), :stores_count)::INTEGER
```

### Tiered Distribution
```sql
CASE 
    WHEN uniform(1, 100, random()) <= 15 THEN 0                           -- 15% no tip
    WHEN uniform(1, 100, random()) <= 50 THEN uniform(100, 300, random()) -- 35% small
    WHEN uniform(1, 100, random()) <= 80 THEN uniform(300, 600, random()) -- 30% standard
    ELSE uniform(600, 1200, random())                                     -- 20% generous
END as tip_amount
```

### Geographic Weighting
```sql
CASE 
    WHEN uniform(1, 100, random()) <= 15 THEN 1   -- SF: 15%
    WHEN uniform(1, 100, random()) <= 30 THEN 3   -- NYC: 15%
    WHEN uniform(1, 100, random()) <= 42 THEN 2   -- LA: 12%
    ELSE uniform(1, 20, random())                 -- Other: 58%
END as market_number
```

---

## Naming Conventions

| Object | Pattern | Example |
|--------|---------|---------|
| Role | `[CUSTOMER]_snow_intelligence` | `ACME_snow_intelligence` |
| Warehouse | `[CUSTOMER]_snow_intelligence_WH` | `ACME_snow_intelligence_WH` |
| Database | `SI_[CUSTOMER]` | `SI_ACME` |
| Schema | `[CUSTOMER]_SNOW_INTELLIGENCE` | `ACME_SNOW_INTELLIGENCE` |
| Agent | `[CUSTOMER]_Platform_Agent` | `ACME_Platform_Agent` |

---

## Privilege Management

Procedures run as CALLER - grant to both ACCOUNTADMIN and Intelligence role:

```sql
-- For procedure to write to source DBs
GRANT ALL PRIVILEGES ON DATABASE SOURCE_DB TO ROLE ACCOUNTADMIN;
GRANT ALL PRIVILEGES ON DATABASE SOURCE_DB TO ROLE [CUSTOMER]_snow_intelligence;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA SOURCE_DB.SCHEMA TO ROLE [CUSTOMER]_snow_intelligence;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA SOURCE_DB.SCHEMA TO ROLE [CUSTOMER]_snow_intelligence;
```
