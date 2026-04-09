-- =============================================================================
-- Rank candidate Snowhouse databases for artifact generation
-- Read-only discovery query. Run in Snowhouse.
-- =============================================================================

WITH table_activity AS (
  SELECT 
    tq.database_name,
    tq.deployment,
    tq.owner_account_id,
    SUM(tq.table_num_queries)     AS total_table_queries,
    COUNT(DISTINCT tq.table_id)   AS distinct_tables,
    COUNT(DISTINCT tq.schema_id)  AS distinct_schemas
  FROM SNOWHOUSE.PRODUCT.ADOPTION_FRAMEWORK_TABLE_QUERIES tq
  WHERE tq.ds = (SELECT MAX(ds) FROM SNOWHOUSE.PRODUCT.ADOPTION_FRAMEWORK_TABLE_QUERIES)
  GROUP BY 1,2,3
),
col_activity AS (
  SELECT
    cq.database_name,
    cq.deployment,
    SUM(cq.col_num_queries)         AS total_col_queries,
    COUNT(DISTINCT cq.full_col)     AS distinct_cols_queried,
    COUNT(DISTINCT cq.table_id)     AS tables_with_col_data
  FROM SNOWHOUSE.PRODUCT.ADOPTION_FRAMEWORK_COLUMN_QUERIES cq
  WHERE cq.ds = (SELECT MAX(ds) FROM SNOWHOUSE.PRODUCT.ADOPTION_FRAMEWORK_COLUMN_QUERIES)
  GROUP BY 1,2
),
scored AS (
  SELECT
    t.database_name,
    t.deployment,
    t.owner_account_id,
    t.total_table_queries,
    t.distinct_tables,
    t.distinct_schemas,
    COALESCE(c.distinct_cols_queried, 0) AS distinct_cols_queried,
    ROUND(COALESCE(c.distinct_cols_queried, 0)::FLOAT / NULLIF(t.distinct_tables, 0), 2) AS avg_cols_per_active_table,
    ROUND(t.total_table_queries::FLOAT / NULLIF(t.distinct_tables, 0), 0) AS avg_queries_per_table,
    (
      0.40 * PERCENT_RANK() OVER (ORDER BY t.total_table_queries)
      + 0.25 * PERCENT_RANK() OVER (ORDER BY t.distinct_tables)
      + 0.20 * PERCENT_RANK() OVER (ORDER BY COALESCE(c.distinct_cols_queried, 0)::FLOAT / NULLIF(t.distinct_tables, 0))
      + 0.15 * PERCENT_RANK() OVER (ORDER BY t.distinct_schemas)
    ) AS composite_score
  FROM table_activity t
  LEFT JOIN col_activity c
    ON t.database_name = c.database_name AND t.deployment = c.deployment
  WHERE t.total_table_queries > 1000
    AND t.distinct_tables >= 5
    AND t.distinct_schemas >= 1
)
SELECT
  database_name,
  deployment,
  owner_account_id,
  total_table_queries,
  distinct_tables,
  distinct_schemas,
  distinct_cols_queried,
  avg_cols_per_active_table,
  avg_queries_per_table,
  ROUND(composite_score, 4) AS composite_score
FROM scored
ORDER BY composite_score DESC
LIMIT 20;
