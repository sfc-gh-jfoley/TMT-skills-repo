-- =============================================================================
-- KG Data Discovery — REFRESH_DOMAIN + REBUILD_CSS
-- Agent F (07_refresh.sql)
--
-- REFRESH_DOMAIN  orchestrates CRAWL(DELTA) → ENRICH → DETECT_RELATIONSHIPS
--                 then recreates the Cortex Search Service for a domain.
-- REBUILD_CSS     recreates the CSS only, skipping crawl/enrich/detect.
--
-- Prerequisites (run once):
--   CALL KG_CONTROL.PUBLIC.BOOTSTRAP_KG_META('<DOMAIN>');
--   CALL KG_CONTROL.PUBLIC.CONFIGURE_DOMAIN('<DOMAIN>', ARRAY_CONSTRUCT(...), NULL);
--   CALL KG_CONTROL.PUBLIC.CRAWL_DOMAIN('<DOMAIN>', 'FULL');
--   CALL KG_CONTROL.PUBLIC.ENRICH_DOMAIN('<DOMAIN>', <tier>);
--   CALL KG_CONTROL.PUBLIC.DETECT_RELATIONSHIPS('<DOMAIN>');
-- Then call:
--   CALL KG_CONTROL.PUBLIC.REFRESH_DOMAIN('<DOMAIN>', <max_tier>);
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. REFRESH_DOMAIN — full orchestrator
--    Runs CRAWL(DELTA) → ENRICH → DETECT_RELATIONSHIPS → CSS CREATE OR REPLACE
--    Updates DOMAIN_REGISTRY.status = 'ACTIVE' on success.
-- -----------------------------------------------------------------------------

CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.REFRESH_DOMAIN(
    domain_name VARCHAR,
    max_tier    NUMBER
)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    domain_upper  VARCHAR       DEFAULT UPPER(:domain_name);
    meta_db       VARCHAR       DEFAULT domain_upper || '_META';
    css_name      VARCHAR       DEFAULT domain_upper || '_SEARCH';
    css_fqn       VARCHAR       DEFAULT meta_db || '.META.' || css_name;
    wh_name       VARCHAR       DEFAULT 'SNOWADHOC';
    crawl_result  VARCHAR;
    enrich_result VARCHAR;
    rels_result   VARCHAR;
    start_ts      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP();
BEGIN
    -- -------------------------------------------------------------------------
    -- Step 0: Resolve warehouse from DOMAIN_CONFIG (key 'warehouse').
    --         Falls back to SNOWADHOC if the key is absent or NULL.
    -- -------------------------------------------------------------------------
    EXECUTE IMMEDIATE '
        SELECT COALESCE(
            (SELECT config_value::VARCHAR
             FROM ' || meta_db || '.META.DOMAIN_CONFIG
             WHERE config_key = ''warehouse''
             LIMIT 1),
            ''SNOWADHOC''
        )
    ' INTO wh_name;

    -- -------------------------------------------------------------------------
    -- Step 1: CRAWL_DOMAIN — delta mode, skips tables with matching hash
    -- -------------------------------------------------------------------------
    CALL KG_CONTROL.PUBLIC.CRAWL_DOMAIN(:domain_upper, 'DELTA') INTO :crawl_result;

    -- -------------------------------------------------------------------------
    -- Step 2: ENRICH_DOMAIN — enriches new / updated RAW_CONCEPTS rows
    -- -------------------------------------------------------------------------
    CALL KG_CONTROL.PUBLIC.ENRICH_DOMAIN(:domain_upper, :max_tier) INTO :enrich_result;

    -- -------------------------------------------------------------------------
    -- Step 3: DETECT_RELATIONSHIPS — re-runs FK + name-match + AI inference
    -- -------------------------------------------------------------------------
    CALL KG_CONTROL.PUBLIC.DETECT_RELATIONSHIPS(:domain_upper) INTO :rels_result;

    -- -------------------------------------------------------------------------
    -- Step 4: Recreate the Cortex Search Service
    --   CSS name  : {DOMAIN}_META.META.{DOMAIN}_SEARCH
    --   ON column : search_content
    --   Source    : CONCEPTS LEFT JOIN RAW_CONCEPTS for table_type / row_count
    --   Warehouse : resolved above from DOMAIN_CONFIG (default SNOWADHOC)
    -- -------------------------------------------------------------------------
    EXECUTE IMMEDIATE '
        CREATE OR REPLACE CORTEX SEARCH SERVICE ' || css_fqn || '
        ON search_content
        ATTRIBUTES source_database, source_schema, source_table, concept_level,
                   enrichment_tier, enrichment_source, object_state, table_type,
                   graduation_candidate
        WAREHOUSE = ' || wh_name || '
        TARGET_LAG = ''1 hour''
        AS
        SELECT
            c.concept_id,
            c.concept_level,
            c.domain,
            c.source_database,
            c.source_schema,
            c.source_table,
            c.table_fqn,
            c.description,
            c.search_content,
            c.tables_yaml,
            c.enrichment_source,
            c.enrichment_tier,
            c.enrichment_quality_score,
            c.object_state,
            c.is_active,
            COALESCE(rc.table_type, ''TABLE'') AS table_type,
            COALESCE(rc.row_count, 0)          AS row_count,
            COALESCE(
                (SELECT config_value::VARCHAR
                 FROM ' || meta_db || '.META.DOMAIN_CONFIG
                 WHERE config_key = ''graduation_candidate''
                 LIMIT 1),
                ''false''
            ) AS graduation_candidate
        FROM ' || meta_db || '.META.CONCEPTS c
        LEFT JOIN ' || meta_db || '.META.RAW_CONCEPTS rc
            ON c.raw_concept_id = rc.concept_id
        WHERE c.is_active = TRUE
    ';

    -- -------------------------------------------------------------------------
    -- Step 5: Invalidate query-plane assembly cache after crawl / enrich / detect
    -- -------------------------------------------------------------------------
    EXECUTE IMMEDIATE '
        UPDATE ' || meta_db || '.META.ASSEMBLY_CACHE
        SET invalidated_at = CURRENT_TIMESTAMP()
        WHERE invalidated_at IS NULL
    ';

    -- -------------------------------------------------------------------------
    -- Step 6: Update DOMAIN_REGISTRY — mark domain ACTIVE, record CSS FQN
    -- -------------------------------------------------------------------------
    UPDATE KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
    SET status                = 'ACTIVE',
        css_name              = :css_fqn,
        css_last_refreshed_at = :start_ts,
        updated_at            = CURRENT_TIMESTAMP()
    WHERE domain_name = :domain_upper;

    RETURN 'REFRESHED: ' || domain_upper
        || ' | Crawl: '  || COALESCE(:crawl_result,  'ok')
        || ' | Enrich: ' || COALESCE(:enrich_result, 'ok')
        || ' | Rels: '   || COALESCE(:rels_result,   'ok')
        || ' | CSS: '    || css_fqn || ' recreated.';
END;
$$;

-- -----------------------------------------------------------------------------
-- 2. REBUILD_CSS — CSS-only refresh (no crawl / enrich / detect)
--    Use when CONCEPTS data is already current and only the search index
--    needs to be dropped + recreated (e.g. after schema change or CSS error).
-- -----------------------------------------------------------------------------

CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.REBUILD_CSS(
    domain_name VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    domain_upper VARCHAR       DEFAULT UPPER(:domain_name);
    meta_db      VARCHAR       DEFAULT domain_upper || '_META';
    css_name     VARCHAR       DEFAULT domain_upper || '_SEARCH';
    css_fqn      VARCHAR       DEFAULT meta_db || '.META.' || css_name;
    wh_name      VARCHAR       DEFAULT 'SNOWADHOC';
BEGIN
    -- -------------------------------------------------------------------------
    -- Step 0: Resolve warehouse from DOMAIN_CONFIG (key 'warehouse').
    --         Falls back to SNOWADHOC if the key is absent or NULL.
    -- -------------------------------------------------------------------------
    EXECUTE IMMEDIATE '
        SELECT COALESCE(
            (SELECT config_value::VARCHAR
             FROM ' || meta_db || '.META.DOMAIN_CONFIG
             WHERE config_key = ''warehouse''
             LIMIT 1),
            ''SNOWADHOC''
        )
    ' INTO wh_name;

    -- -------------------------------------------------------------------------
    -- Step 1: Recreate the Cortex Search Service
    --   Identical DDL to REFRESH_DOMAIN — same CSS shape, same source query.
    -- -------------------------------------------------------------------------
    EXECUTE IMMEDIATE '
        CREATE OR REPLACE CORTEX SEARCH SERVICE ' || css_fqn || '
        ON search_content
        ATTRIBUTES source_database, source_schema, source_table, concept_level,
                   enrichment_tier, enrichment_source, object_state, table_type,
                   graduation_candidate
        WAREHOUSE = ' || wh_name || '
        TARGET_LAG = ''1 hour''
        AS
        SELECT
            c.concept_id,
            c.concept_level,
            c.domain,
            c.source_database,
            c.source_schema,
            c.source_table,
            c.table_fqn,
            c.description,
            c.search_content,
            c.tables_yaml,
            c.enrichment_source,
            c.enrichment_tier,
            c.enrichment_quality_score,
            c.object_state,
            c.is_active,
            COALESCE(rc.table_type, ''TABLE'') AS table_type,
            COALESCE(rc.row_count, 0)          AS row_count,
            COALESCE(
                (SELECT config_value::VARCHAR
                 FROM ' || meta_db || '.META.DOMAIN_CONFIG
                 WHERE config_key = ''graduation_candidate''
                 LIMIT 1),
                ''false''
            ) AS graduation_candidate
        FROM ' || meta_db || '.META.CONCEPTS c
        LEFT JOIN ' || meta_db || '.META.RAW_CONCEPTS rc
            ON c.raw_concept_id = rc.concept_id
        WHERE c.is_active = TRUE
    ';

    -- -------------------------------------------------------------------------
    -- Step 2: Update DOMAIN_REGISTRY — record new CSS FQN and refresh time
    -- -------------------------------------------------------------------------
    UPDATE KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
    SET css_name              = :css_fqn,
        css_last_refreshed_at = CURRENT_TIMESTAMP(),
        updated_at            = CURRENT_TIMESTAMP()
    WHERE domain_name = :domain_upper;

    RETURN 'CSS REBUILT: ' || css_fqn
        || ' | Warehouse: ' || wh_name
        || ' | Domain: '    || domain_upper;
END;
$$;

-- -----------------------------------------------------------------------------
-- 3. Validation — run after deploy to confirm both procs exist
-- -----------------------------------------------------------------------------

SHOW PROCEDURES LIKE '%REFRESH%' IN SCHEMA KG_CONTROL.PUBLIC;
SHOW PROCEDURES LIKE '%REBUILD_CSS%' IN SCHEMA KG_CONTROL.PUBLIC;
