-- =============================================================================
-- KG Data Discovery — Query Plane Checkpoints
-- Manual/Snowflake-side validation queries for new query-plane artifacts.
-- Replace placeholders before execution.
-- =============================================================================

-- 1. Verify query-plane tables exist
SHOW TABLES LIKE 'QUESTION_PLAN' IN SCHEMA __DOMAIN_META_DB__.META;
SHOW TABLES LIKE 'SEMANTIC_PLAN' IN SCHEMA __DOMAIN_META_DB__.META;
SHOW TABLES LIKE 'TRANSIENT_JOIN_GRAPH' IN SCHEMA __DOMAIN_META_DB__.META;
SHOW TABLES LIKE 'TRANSIENT_METRIC_BINDINGS' IN SCHEMA __DOMAIN_META_DB__.META;
SHOW TABLES LIKE 'TRANSIENT_SEMANTIC_SPEC' IN SCHEMA __DOMAIN_META_DB__.META;

-- 2. Verify QUERY_LOG extension columns exist
DESC TABLE KG_CONTROL.PUBLIC.QUERY_LOG;

-- 3. Smoke test existing domain selection inputs
SELECT domain_name, meta_database, status, css_name
FROM KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
WHERE status IN ('ENRICHED', 'ACTIVE', 'GRADUATED')
ORDER BY updated_at DESC;

-- 4. Manual call skeletons for Python procs after deployment
-- CALL KG_CONTROL.PUBLIC.RESOLVE_QUERY_CONTEXT('total revenue last quarter', 'FINANCE', 3, FALSE);
-- CALL KG_CONTROL.PUBLIC.BUILD_TRANSIENT_CONTRACT('FINANCE_META', '<plan_id>', '<semantic_plan_id>', 'FINANCE');
-- CALL KG_CONTROL.PUBLIC.VALIDATE_TRANSIENT_CONTRACT('FINANCE_META', '<semantic_plan_id>');
-- CALL KG_CONTROL.PUBLIC.DETECT_SEMANTIC_CONFLICTS('FINANCE', 'FINANCE_META', '<ONT_DB>', '<ONT_SCHEMA>');
-- CALL KG_CONTROL.PUBLIC.VERIFY_METRIC_BINDINGS('FINANCE', '<ONT_DB>', '<ONT_SCHEMA>', 'DB.SCHEMA.SEMANTIC_VIEW_NAME');
