-- =============================================================================
-- KG Data Discovery — DDL
-- Run this file once to bootstrap the KG_CONTROL database and the
-- BOOTSTRAP_KG_META procedure. After that, call:
--   CALL KG_CONTROL.PUBLIC.BOOTSTRAP_KG_META('<DOMAIN_NAME>');
-- for each domain you want to onboard.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Master Control Database
-- -----------------------------------------------------------------------------

CREATE DATABASE IF NOT EXISTS KG_CONTROL;
CREATE SCHEMA IF NOT EXISTS KG_CONTROL.PUBLIC;

-- -----------------------------------------------------------------------------
-- 2. Master Tables (live in KG_CONTROL, cross-domain)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS KG_CONTROL.PUBLIC.DOMAIN_REGISTRY (
    domain_name             VARCHAR         NOT NULL,
    meta_database           VARCHAR         NOT NULL,   -- always {domain_name}_META
    source_databases        ARRAY           NOT NULL,   -- databases crawled
    status                  VARCHAR         NOT NULL DEFAULT 'PENDING',
                                                        -- PENDING | CRAWLED | ENRICHED | ACTIVE | GRADUATED
    enrichment_max_tier     NUMBER(1)       NOT NULL DEFAULT 0,
    enrichment_daily_budget NUMBER(10,2)    NOT NULL DEFAULT 10.0,
    ontology_agent          VARCHAR,                    -- FQN after graduation
    ontology_database       VARCHAR,
    ontology_schema         VARCHAR,
    ontology_deployed_at    TIMESTAMP_NTZ,
    graduation_candidate    BOOLEAN         NOT NULL DEFAULT FALSE,
    css_name                VARCHAR,                    -- FQN of active Cortex Search Service
    css_last_refreshed_at   TIMESTAMP_NTZ,
    created_at              TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    updated_at              TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    created_by              VARCHAR         NOT NULL DEFAULT CURRENT_USER(),
    PRIMARY KEY (domain_name)
);

CREATE TABLE IF NOT EXISTS KG_CONTROL.PUBLIC.WIZARD_STATE (
    session_id              VARCHAR         NOT NULL,
    domain_name             VARCHAR,
    current_step            NUMBER(2)       NOT NULL DEFAULT 0,
    status                  VARCHAR         NOT NULL DEFAULT 'IN_PROGRESS',
                                                        -- IN_PROGRESS | COMPLETE | FAILED
    step_results            VARIANT,                    -- JSON blob: {step: {status, output, ts}}
    started_at              TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    updated_at              TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    completed_at            TIMESTAMP_NTZ,
    PRIMARY KEY (session_id)
);

CREATE TABLE IF NOT EXISTS KG_CONTROL.PUBLIC.QUERY_LOG (
    log_id                  VARCHAR         NOT NULL DEFAULT UUID_STRING(),
    domain_name             VARCHAR         NOT NULL,
    question                VARCHAR         NOT NULL,
    routing                 VARCHAR         NOT NULL,   -- ONTOLOGY_AGENT | DYNAMIC_ASSEMBLE | ONTOLOGY_FALLBACK
    concepts_used           VARIANT,                    -- array of concept_ids
    tables_used             VARIANT,                    -- array of table FQNs
    sql_generated           VARCHAR,
    row_count               NUMBER,
    execution_time_ms       NUMBER,
    user_name               VARCHAR         NOT NULL DEFAULT CURRENT_USER(),
    logged_at               TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (log_id)
);

-- -----------------------------------------------------------------------------
-- 3. BOOTSTRAP_KG_META — creates all domain-specific tables
--    Call: CALL KG_CONTROL.PUBLIC.BOOTSTRAP_KG_META('FINANCE');
--    Creates: FINANCE_META.META.{RAW_CONCEPTS, CONCEPTS, RELATIONSHIPS,
--                                 OBJECT_STATE, DOMAIN_CONFIG}
-- -----------------------------------------------------------------------------

CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.BOOTSTRAP_KG_META(
    domain_name VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    db      VARCHAR DEFAULT UPPER(domain_name) || '_META';
    schema_ VARCHAR DEFAULT UPPER(domain_name) || '_META.META';
    result  VARCHAR DEFAULT '';
BEGIN

    -- Database + schema
    EXECUTE IMMEDIATE 'CREATE DATABASE IF NOT EXISTS ' || db;
    EXECUTE IMMEDIATE 'CREATE SCHEMA IF NOT EXISTS ' || schema_;

    -- -----------------------------------------------------------------
    -- RAW_CONCEPTS
    -- Populated by CRAWL_DOMAIN (ACCOUNT_USAGE bulk) and CRAWL_TABLE
    -- (INFORMATION_SCHEMA targeted). One row per database, schema, or table.
    -- -----------------------------------------------------------------
    EXECUTE IMMEDIATE '
    CREATE TABLE IF NOT EXISTS ' || schema_ || '.RAW_CONCEPTS (
        concept_id          VARCHAR         NOT NULL DEFAULT UUID_STRING(),
        concept_level       VARCHAR         NOT NULL,   -- database | schema | table
        domain              VARCHAR         NOT NULL,
        source_database     VARCHAR         NOT NULL,
        source_schema       VARCHAR,                    -- NULL for database-level concepts
        source_table        VARCHAR,                    -- NULL for database/schema-level concepts
        table_fqn           VARCHAR,                    -- DB.SCHEMA.TABLE (table-level only)

        -- Raw metadata (populated by CRAWL)
        table_type          VARCHAR,                    -- TABLE | VIEW | EXTERNAL TABLE
        row_count           NUMBER,
        bytes               NUMBER,
        clustering_key      VARCHAR,
        comment             VARCHAR,
        created_at_src      TIMESTAMP_NTZ,
        last_altered_src    TIMESTAMP_NTZ,
        owner               VARCHAR,
        is_transient        BOOLEAN         DEFAULT FALSE,
        is_managed_access   BOOLEAN         DEFAULT FALSE,
        is_active           BOOLEAN         NOT NULL DEFAULT TRUE,

        -- Column metadata (table-level only, populated by CRAWL)
        columns_json        VARIANT,        -- [{name, type, nullable, comment, ordinal}]
        constraints_json    VARIANT,        -- [{name, type, columns, ref_table, ref_cols}]
        sample_values_json  VARIANT,        -- {col_name: [val1, val2, ...]}

        -- Crawl provenance
        crawl_source        VARCHAR,        -- ACCOUNT_USAGE | INFORMATION_SCHEMA
        crawl_timestamp     TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
        metadata_hash       VARCHAR,        -- SHA2 of columns_json for drift detection

        PRIMARY KEY (concept_id),
        UNIQUE (concept_level, source_database, source_schema, source_table)
    )';

    -- -----------------------------------------------------------------
    -- CONCEPTS
    -- Populated by ENRICH_DOMAIN. AI-enriched version of RAW_CONCEPTS.
    -- This is the table indexed by the Cortex Search Service.
    -- -----------------------------------------------------------------
    EXECUTE IMMEDIATE '
    CREATE TABLE IF NOT EXISTS ' || schema_ || '.CONCEPTS (
        concept_id              VARCHAR         NOT NULL DEFAULT UUID_STRING(),
        raw_concept_id          VARCHAR         NOT NULL,   -- FK to RAW_CONCEPTS
        concept_level           VARCHAR         NOT NULL,
        domain                  VARCHAR         NOT NULL,
        source_database         VARCHAR         NOT NULL,
        source_schema           VARCHAR,
        source_table            VARCHAR,
        table_fqn               VARCHAR,

        -- Enriched content
        description             VARCHAR,
        keywords                VARIANT,        -- ARRAY of keyword strings
        search_content          VARCHAR,        -- concatenated text for CSS indexing

        -- Structured payloads (YAML strings, Cortex Analyst compatible)
        tables_yaml             VARCHAR,        -- table FQNs, PKs, columns with types/roles
        join_keys_yaml          VARCHAR,        -- cross-table relationships
        metrics_yaml            VARCHAR,        -- pre-defined aggregations
        sample_values           VARCHAR,        -- representative values
        is_enum                 BOOLEAN         DEFAULT FALSE,

        -- Enrichment provenance
        enrichment_tier         NUMBER(1)       DEFAULT 0,
                                                -- 0=free | 1=AI_CLASSIFY | 2=AI_EXTRACT | 3=AI_COMPLETE
        enrichment_source       VARCHAR,        -- HEURISTIC | AI_CLASSIFY | AI_EXTRACT | AI_COMPLETE | ONT_CLASS
        enrichment_quality_score NUMBER(3,2),   -- 0.00–1.00
        enrichment_cost_usd     NUMBER(10,6)    DEFAULT 0,
        enrichment_timestamp    TIMESTAMP_NTZ,

        -- Query feedback
        query_count             NUMBER          NOT NULL DEFAULT 0,
        last_queried_at         TIMESTAMP_NTZ,

        -- State
        is_active               BOOLEAN         NOT NULL DEFAULT TRUE,
        object_state            VARCHAR         NOT NULL DEFAULT ''KNOWN_CURRENT'',
                                                -- KNOWN_CURRENT | KNOWN_DRIFTED | KNOWN_DELETED
                                                -- ONBOARDED_INCORRECTLY | SHADOW_ACTIVE
                                                -- SHADOW_INACTIVE | GRADUATED | ONTOLOGY_DRIFT

        created_at              TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
        updated_at              TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),

        PRIMARY KEY (concept_id),
        UNIQUE (raw_concept_id)
    )';

    -- -----------------------------------------------------------------
    -- RELATIONSHIPS
    -- Populated by DETECT_RELATIONSHIPS. Join paths between tables.
    -- -----------------------------------------------------------------
    EXECUTE IMMEDIATE '
    CREATE TABLE IF NOT EXISTS ' || schema_ || '.RELATIONSHIPS (
        relationship_id     VARCHAR         NOT NULL DEFAULT UUID_STRING(),
        domain              VARCHAR         NOT NULL,
        source_concept_id   VARCHAR         NOT NULL,
        target_concept_id   VARCHAR         NOT NULL,
        source_table        VARCHAR         NOT NULL,
        source_column       VARCHAR         NOT NULL,
        target_table        VARCHAR         NOT NULL,
        target_column       VARCHAR         NOT NULL,
        relationship_type   VARCHAR         NOT NULL,
                                            -- FK | INFERRED_FK | SHARED_KEY | SEMANTIC | ONTOLOGY
        confidence          NUMBER(3,2)     NOT NULL DEFAULT 1.0,
                                            -- 1.0 = declared FK, lower = inferred
        detection_method    VARCHAR         NOT NULL,
                                            -- CONSTRAINT | NAME_MATCH | AI_INFERRED | MANUAL | ONT_REL_DEF
        is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
        created_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
        PRIMARY KEY (relationship_id)
    )';

    -- -----------------------------------------------------------------
    -- OBJECT_STATE
    -- Populated by RUN_WATCH. Tracks state of every known + shadow object.
    -- -----------------------------------------------------------------
    EXECUTE IMMEDIATE '
    CREATE TABLE IF NOT EXISTS ' || schema_ || '.OBJECT_STATE (
        object_fqn          VARCHAR         NOT NULL,   -- DB | DB.SCHEMA | DB.SCHEMA.TABLE
        object_level        VARCHAR         NOT NULL,   -- database | schema | table
        domain              VARCHAR         NOT NULL,
        object_state        VARCHAR         NOT NULL,
                                            -- KNOWN_CURRENT | KNOWN_DRIFTED | KNOWN_DELETED
                                            -- ONBOARDED_INCORRECTLY | SHADOW_ACTIVE
                                            -- SHADOW_INACTIVE | GRADUATED | ONTOLOGY_DRIFT
        concept_id          VARCHAR,                    -- FK to CONCEPTS (NULL for shadow)

        -- Detection metadata
        first_seen          TIMESTAMP_NTZ,
        last_seen           TIMESTAMP_NTZ,
        last_access         TIMESTAMP_NTZ,
        access_count_30d    NUMBER          DEFAULT 0,
        distinct_users_30d  NUMBER          DEFAULT 0,

        -- Drift detection
        metadata_hash       VARCHAR,
        previous_hash       VARCHAR,
        drift_detected_at   TIMESTAMP_NTZ,
        drift_details       VARCHAR,

        -- Ontology-specific
        possible_ontology_class  VARCHAR,   -- hint when shadow table matches an ontology class pattern

        -- Triage
        triage_action       VARCHAR,        -- onboard | ignore | defer | re-enrich | ontology_review | NULL
        triage_reason       VARCHAR,
        triaged_by          VARCHAR,
        triaged_at          TIMESTAMP_NTZ,

        updated_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
        PRIMARY KEY (object_fqn)
    )';

    -- -----------------------------------------------------------------
    -- DOMAIN_CONFIG
    -- Populated by CONFIGURE_DOMAIN. One row per config key.
    -- -----------------------------------------------------------------
    EXECUTE IMMEDIATE '
    CREATE TABLE IF NOT EXISTS ' || schema_ || '.DOMAIN_CONFIG (
        config_key          VARCHAR         NOT NULL,
        config_value        VARIANT         NOT NULL,
        updated_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
        updated_by          VARCHAR         NOT NULL DEFAULT CURRENT_USER(),
        PRIMARY KEY (config_key)
    )';

    -- -----------------------------------------------------------------
    -- ASSEMBLY_CACHE
    -- Query-plane cache for assembled semantic context built from CONCEPTS
    -- and RELATIONSHIPS. Invalidated by REFRESH_DOMAIN after enrich / detect.
    -- -----------------------------------------------------------------
    EXECUTE IMMEDIATE '
    CREATE TABLE IF NOT EXISTS ' || schema_ || '.ASSEMBLY_CACHE (
        cache_key           VARCHAR         NOT NULL,
        domain              VARCHAR         NOT NULL,
        question_hash       VARCHAR,
        table_fqns          VARIANT         NOT NULL,
        tables_context      VARCHAR,
        sv_ddl              VARCHAR,
        join_paths          VARIANT,
        quality_score       NUMBER(3,2),
        concept_ids         VARIANT,
        created_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
        hit_count           NUMBER          NOT NULL DEFAULT 0,
        last_hit_at         TIMESTAMP_NTZ,
        invalidated_at      TIMESTAMP_NTZ,
        PRIMARY KEY (cache_key)
    )';

    -- Seed essential config keys
    EXECUTE IMMEDIATE '
    INSERT INTO ' || schema_ || '.DOMAIN_CONFIG (config_key, config_value) VALUES
        (''domain_name'',               PARSE_JSON(''"' || UPPER(domain_name) || '"'')),
        (''meta_database'',             PARSE_JSON(''"' || db || '"'')),
        (''enrichment_max_tier'',       PARSE_JSON(''0'')),
        (''enrichment_daily_budget'',   PARSE_JSON(''10.0'')),
        (''auto_onboard_schemas'',      PARSE_JSON(''[]'')),
        (''ignore_schemas'',            PARSE_JSON(''["INFORMATION_SCHEMA"]'')),
        (''refresh_schedule'',          PARSE_JSON(''"0 6 * * *"'')),
        (''watch_enabled'',             PARSE_JSON(''false'')),
        (''watch_auto_onboard'',        PARSE_JSON(''false'')),
        (''warehouse'',                 PARSE_JSON(''"SNOWADHOC"'')),
        (''ontology_agent'',            PARSE_JSON(''null'')),
        (''ontology_database'',         PARSE_JSON(''null'')),
        (''ontology_schema'',           PARSE_JSON(''null'')),
        (''ontology_deployed_at'',      PARSE_JSON(''null''))
    ';

    -- Register domain in master registry
    EXECUTE IMMEDIATE '
    INSERT INTO KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
        (domain_name, meta_database, source_databases, status)
    VALUES
        (''' || UPPER(domain_name) || ''', ''' || db || ''', ARRAY_CONSTRUCT(), ''PENDING'')
    ';

    result := 'BOOTSTRAP complete: ' || db || '.META — RAW_CONCEPTS, CONCEPTS, RELATIONSHIPS, OBJECT_STATE, DOMAIN_CONFIG created.';
    RETURN result;
END;
$$;

-- -----------------------------------------------------------------------------
-- 4. Helper: DROP_KG_META — removes a domain (for cleanup/reset)
--    Call: CALL KG_CONTROL.PUBLIC.DROP_KG_META('FINANCE', FALSE);
--    Set force=TRUE to also drop the _META database.
-- -----------------------------------------------------------------------------

CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.DROP_KG_META(
    domain_name VARCHAR,
    force       BOOLEAN DEFAULT FALSE
)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    db VARCHAR DEFAULT UPPER(domain_name) || '_META';
BEGIN
    DELETE FROM KG_CONTROL.PUBLIC.DOMAIN_REGISTRY WHERE domain_name = UPPER(:domain_name);
    DELETE FROM KG_CONTROL.PUBLIC.WIZARD_STATE     WHERE domain_name = UPPER(:domain_name);

    IF (force) THEN
        EXECUTE IMMEDIATE 'DROP DATABASE IF EXISTS ' || db;
        RETURN 'Dropped registry entry and database ' || db;
    END IF;

    RETURN 'Removed registry entry. Database ' || db || ' retained (pass force=TRUE to drop it).';
END;
$$;

-- -----------------------------------------------------------------------------
-- 5. Validation — run after deploy to confirm all objects exist
-- -----------------------------------------------------------------------------

SHOW PROCEDURES LIKE '%KG%' IN SCHEMA KG_CONTROL.PUBLIC;
SELECT 'KG_CONTROL.PUBLIC.DOMAIN_REGISTRY'  AS obj, COUNT(*) AS rows FROM KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
UNION ALL
SELECT 'KG_CONTROL.PUBLIC.WIZARD_STATE',    COUNT(*) FROM KG_CONTROL.PUBLIC.WIZARD_STATE
UNION ALL
SELECT 'KG_CONTROL.PUBLIC.QUERY_LOG',       COUNT(*) FROM KG_CONTROL.PUBLIC.QUERY_LOG;
