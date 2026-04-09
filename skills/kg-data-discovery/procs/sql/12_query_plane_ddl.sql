-- =============================================================================
-- KG Data Discovery — Query Plane DDL
-- Creates query-planning and transient semantic contract tables.
-- Apply after 00_ddl.sql / BOOTSTRAP_KG_META are deployed.
-- =============================================================================

-- Template notes:
-- Replace __DOMAIN_META_DB__ with the actual domain meta database, e.g. FINANCE_META
-- Example: FINANCE_META.META.QUESTION_PLAN

CREATE TABLE IF NOT EXISTS __DOMAIN_META_DB__.META.QUESTION_PLAN (
    plan_id               VARCHAR         NOT NULL,
    user_question         VARCHAR         NOT NULL,
    normalized_question   VARCHAR,
    detected_intent       VARCHAR,
    detected_entities     ARRAY,
    detected_metrics      ARRAY,
    detected_filters      VARIANT,
    detected_time_scope   VARIANT,
    detected_grain        VARCHAR,
    domain_candidates     ARRAY,
    confidence            FLOAT,
    created_at            TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (plan_id)
);

CREATE TABLE IF NOT EXISTS __DOMAIN_META_DB__.META.SEMANTIC_PLAN (
    semantic_plan_id        VARCHAR         NOT NULL,
    plan_id                 VARCHAR         NOT NULL,
    chosen_route            VARCHAR         NOT NULL,
    chosen_semantic_view    VARCHAR,
    chosen_ontology_agent   VARCHAR,
    use_transient_contract  BOOLEAN         NOT NULL DEFAULT FALSE,
    route_confidence        FLOAT,
    ambiguity_reason        VARIANT,
    blocking_conflicts      ARRAY,
    created_at              TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (semantic_plan_id)
);

CREATE TABLE IF NOT EXISTS __DOMAIN_META_DB__.META.TRANSIENT_JOIN_GRAPH (
    semantic_plan_id     VARCHAR         NOT NULL,
    edge_order           NUMBER          NOT NULL,
    source_object        VARCHAR         NOT NULL,
    target_object        VARCHAR         NOT NULL,
    source_key           VARCHAR,
    target_key           VARCHAR,
    relationship_type    VARCHAR,
    confidence           FLOAT,
    provenance           VARCHAR,
    created_at           TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS __DOMAIN_META_DB__.META.TRANSIENT_METRIC_BINDINGS (
    semantic_plan_id         VARCHAR         NOT NULL,
    metric_name              VARCHAR         NOT NULL,
    canonical_metric_name    VARCHAR,
    sql_expression           VARCHAR,
    grain                    VARCHAR,
    source                   VARCHAR,
    confidence               FLOAT,
    chosen                   BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at               TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS __DOMAIN_META_DB__.META.TRANSIENT_SEMANTIC_SPEC (
    semantic_plan_id       VARCHAR         NOT NULL,
    semantic_spec          VARIANT         NOT NULL,
    generated_sql_preview  VARCHAR,
    compile_status         VARCHAR,
    compile_error          VARCHAR,
    created_at             TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

ALTER TABLE KG_CONTROL.PUBLIC.QUERY_LOG
    ADD COLUMN IF NOT EXISTS resolution_route VARCHAR;

ALTER TABLE KG_CONTROL.PUBLIC.QUERY_LOG
    ADD COLUMN IF NOT EXISTS assembly_quality_score NUMBER(3,2);

ALTER TABLE KG_CONTROL.PUBLIC.QUERY_LOG
    ADD COLUMN IF NOT EXISTS cache_hit BOOLEAN DEFAULT FALSE;
