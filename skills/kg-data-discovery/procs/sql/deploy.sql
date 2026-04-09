-- ============================================================
-- KG Data Discovery — Master Deploy Script
-- ============================================================
--
-- PURPOSE
--   One-shot deployment of all KG Data Discovery stored
--   procedures to a Snowflake account.
--
-- PREREQUISITES
--   - SYSADMIN or (CREATE DATABASE + CREATE SCHEMA) privilege
--   - SNOWFLAKE.ACCOUNT_USAGE access
--     (GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <your_role>)
--   - CORTEX_USER privilege for AI enrichment (tiers 1–3 only)
--   - An active warehouse (USE WAREHOUSE <name>)
--
-- HOW TO DEPLOY
--   Option A — SnowSQL CLI:
--     snowsql -c <connection> -f procs/sql/deploy.sql
--
--   Option B — Snowsight worksheet:
--     Copy-paste and run this file (or each sourced file) sequentially.
--     Note: Snowsight does not support the !source directive.
--     Run each file listed below as a separate worksheet.
--
--   Option C — CoCo snowflake_sql_execute tool:
--     Run each section below as a separate call to snowflake_sql_execute.
--     The Python proc DDL strings (ONBOARD_WIZARD_DDL etc.) must be
--     extracted from the .py file and executed via snowflake_sql_execute.
--
-- HOW TO DEPLOY PYTHON PROCEDURES (03, 04, 05, 06, 08, 09)
--   Each Python proc file contains a DDL string variable, e.g.:
--
--     File: procs/python/03_crawl_domain.py  → CRAWL_DOMAIN_DDL
--     File: procs/python/04_crawl_table.py   → CRAWL_TABLE_DDL, CRAWL_SCHEMA_DDL
--     File: procs/python/05_enrich_domain.py → ENRICH_DOMAIN_DDL
--     File: procs/python/06_detect_rels.py   → DETECT_RELATIONSHIPS_DDL
--     File: procs/python/08_watch.py         → RUN_WATCH_DDL
--     File: procs/python/09_wizard.py        → ONBOARD_WIZARD_DDL
--
--   To deploy a Python proc:
--     1. Open the .py file
--     2. Copy the value of the DDL string (everything between triple-quotes)
--     3. Execute it as SQL in Snowsight, SnowSQL, or snowflake_sql_execute
--
--   CoCo workflow example:
--     import the .py file with the Read tool, extract the DDL string,
--     pass to snowflake_sql_execute tool.
--
-- ============================================================
-- QUICK REFERENCE — key entry points after deploy
-- ============================================================
--
-- Run the onboarding wizard (interactive step-by-step):
--   CALL KG_CONTROL.PUBLIC.ONBOARD_WIZARD('START', NULL);
--   CALL KG_CONTROL.PUBLIC.ONBOARD_WIZARD('STATUS', NULL);
--   CALL KG_CONTROL.PUBLIC.ONBOARD_WIZARD('NEXT', NULL);
--   CALL KG_CONTROL.PUBLIC.ONBOARD_WIZARD('PREV', NULL);
--   CALL KG_CONTROL.PUBLIC.ONBOARD_WIZARD('RESET', NULL);
--
-- Discover candidate domains manually:
--   CALL KG_CONTROL.PUBLIC.DISCOVER_DOMAINS('SHALLOW', 7);
--   CALL KG_CONTROL.PUBLIC.DISCOVER_DOMAINS('DEEP', 90);
--
-- Bootstrap a specific domain:
--   CALL KG_CONTROL.PUBLIC.BOOTSTRAP_KG_META('FINANCE');
--
-- Configure source databases:
--   CALL KG_CONTROL.PUBLIC.CONFIGURE_DOMAIN(
--     'FINANCE',
--     ARRAY_CONSTRUCT('FINANCE_DB', 'FINANCE_ARCHIVE'),
--     NULL
--   );
--
-- Run a full pipeline manually:
--   CALL KG_CONTROL.PUBLIC.CRAWL_DOMAIN('FINANCE', 'FULL');
--   CALL KG_CONTROL.PUBLIC.ENRICH_DOMAIN('FINANCE', 2);
--   CALL KG_CONTROL.PUBLIC.DETECT_RELATIONSHIPS('FINANCE');
--   CALL KG_CONTROL.PUBLIC.REFRESH_DOMAIN('FINANCE', 2);
--
-- Monitor for drift / shadow tables:
--   CALL KG_CONTROL.PUBLIC.RUN_WATCH('FINANCE');
--
-- Targeted single-table crawl:
--   CALL KG_CONTROL.PUBLIC.CRAWL_TABLE('FINANCE', 'FINANCE_DB.PUBLIC.ORDERS');
--   CALL KG_CONTROL.PUBLIC.CRAWL_SCHEMA('FINANCE', 'FINANCE_DB.PUBLIC');
--
-- CSS-only rebuild (no re-crawl/enrich):
--   CALL KG_CONTROL.PUBLIC.REBUILD_CSS('FINANCE');
--
-- ============================================================


-- ============================================================
-- STEP 0: Core infrastructure (KG_CONTROL database + master
--         tables + BOOTSTRAP_KG_META + DROP_KG_META)
-- ============================================================

!source procs/sql/00_ddl.sql


-- ============================================================
-- STEP 1: Discovery procs (SQL scripting)
--   Creates: DISCOVER_DOMAINS, CONFIGURE_DOMAIN
-- ============================================================

!source procs/sql/01_discover.sql


-- ============================================================
-- STEP 2: Crawl procs (Snowpark Python)
--   Creates: CRAWL_DOMAIN           ← from procs/python/03_crawl_domain.py
--            CRAWL_TABLE            ← from procs/python/04_crawl_table.py
--            CRAWL_SCHEMA           ← from procs/python/04_crawl_table.py
--
--   These files contain CREATE OR REPLACE PROCEDURE DDL strings.
--   Execute the DDL string from each file via Snowsight or the
--   CoCo snowflake_sql_execute tool (see instructions above).
-- ============================================================

-- Manual execution required for:
--   procs/python/03_crawl_domain.py  → CRAWL_DOMAIN_DDL
--   procs/python/04_crawl_table.py   → CRAWL_TABLE_DDL + CRAWL_SCHEMA_DDL


-- ============================================================
-- STEP 3: Enrich proc (Snowpark Python)
--   Creates: ENRICH_DOMAIN          ← from procs/python/05_enrich_domain.py
--
--   Execute: ENRICH_DOMAIN_DDL
-- ============================================================

-- Manual execution required for:
--   procs/python/05_enrich_domain.py → ENRICH_DOMAIN_DDL


-- ============================================================
-- STEP 4: Relationship detection proc (Snowpark Python)
--   Creates: DETECT_RELATIONSHIPS   ← from procs/python/06_detect_rels.py
--
--   Execute: DETECT_RELATIONSHIPS_DDL
-- ============================================================

-- Manual execution required for:
--   procs/python/06_detect_rels.py  → DETECT_RELATIONSHIPS_DDL


-- ============================================================
-- STEP 5: Refresh + CSS orchestrator (SQL scripting)
--   Creates: REFRESH_DOMAIN, REBUILD_CSS
-- ============================================================

!source procs/sql/07_refresh.sql


-- ============================================================
-- STEP 6: Watch proc (Snowpark Python)
--   Creates: RUN_WATCH              ← from procs/python/08_watch.py
--
--   Execute: RUN_WATCH_DDL
-- ============================================================

-- Manual execution required for:
--   procs/python/08_watch.py        → RUN_WATCH_DDL


-- ============================================================
-- STEP 7: Onboarding wizard (Snowpark Python)
--   Creates: ONBOARD_WIZARD         ← from procs/python/09_wizard.py
--
--   Execute: ONBOARD_WIZARD_DDL
-- ============================================================

-- Manual execution required for:
--   procs/python/09_wizard.py       → ONBOARD_WIZARD_DDL


-- ============================================================
-- STEP 8: Query-plane DDL (SQL scripting)
--   Creates: QUESTION_PLAN, SEMANTIC_PLAN, TRANSIENT_JOIN_GRAPH,
--            TRANSIENT_METRIC_BINDINGS, TRANSIENT_SEMANTIC_SPEC
--   Replace __DOMAIN_META_DB__ placeholders before execution.
-- ============================================================

-- Manual execution required for:
--   procs/sql/12_query_plane_ddl.sql


-- ============================================================
-- STEP 9: Verification layer DDL (SQL scripting)
--   Creates: ONT_CONFLICT_REGISTRY, CANONICAL_METRIC_DECISIONS,
--            METRIC_DEFINITION_EVIDENCE
--   Replace __ONT_DB__ and __ONT_SCHEMA__ placeholders before execution.
-- ============================================================

-- Manual execution required for:
--   procs/sql/13_verification_ddl.sql


-- ============================================================
-- STEP 10: Query-plane and verification Python procedures
--   Creates: RESOLVE_QUERY_CONTEXT, BUILD_TRANSIENT_CONTRACT,
--            VALIDATE_TRANSIENT_CONTRACT, DETECT_SEMANTIC_CONFLICTS,
--            VERIFY_METRIC_BINDINGS
-- ============================================================

-- Manual execution required for:
--   procs/python/10_detect_semantic_conflicts.py
--   procs/python/11_verify_metric_bindings.py
--   procs/python/12_resolve_query_context.py
--   procs/python/13_build_transient_contract.py
--   procs/python/14_validate_transient_contract.py


-- ============================================================
-- DEPLOYMENT VALIDATION
-- Confirm all procs exist and master tables are queryable.
-- ============================================================

SHOW PROCEDURES IN SCHEMA KG_CONTROL.PUBLIC;

SELECT 'KG_CONTROL.PUBLIC.DOMAIN_REGISTRY' AS table_name,
       COUNT(*) AS row_count
FROM KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
UNION ALL
SELECT 'KG_CONTROL.PUBLIC.WIZARD_STATE',    COUNT(*)
FROM KG_CONTROL.PUBLIC.WIZARD_STATE
UNION ALL
SELECT 'KG_CONTROL.PUBLIC.QUERY_LOG',       COUNT(*)
FROM KG_CONTROL.PUBLIC.QUERY_LOG;

-- Expected proc inventory after full deployment
SELECT proc_name, 'ready' AS deploy_status FROM (
    VALUES
        ('BOOTSTRAP_KG_META'),
        ('DROP_KG_META'),
        ('DISCOVER_DOMAINS'),
        ('CONFIGURE_DOMAIN'),
        ('CRAWL_DOMAIN'),
        ('CRAWL_TABLE'),
        ('CRAWL_SCHEMA'),
        ('ENRICH_DOMAIN'),
        ('DETECT_RELATIONSHIPS'),
        ('REFRESH_DOMAIN'),
        ('REBUILD_CSS'),
        ('RUN_WATCH'),
        ('ONBOARD_WIZARD')
) t (proc_name)
ORDER BY proc_name;
