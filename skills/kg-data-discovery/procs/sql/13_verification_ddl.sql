-- =============================================================================
-- KG Data Discovery — Verification Layer DDL
-- Creates ontology/KG conflict registry and metric canonicalization tables.
-- Replace __ONT_DB__ and __ONT_SCHEMA__ with actual ontology database/schema.
-- =============================================================================

CREATE TABLE IF NOT EXISTS __ONT_DB__.__ONT_SCHEMA__.ONT_CONFLICT_REGISTRY (
    conflict_id         VARCHAR         NOT NULL,
    domain_name         VARCHAR         NOT NULL,
    conflict_type       VARCHAR         NOT NULL,
    severity            VARCHAR         NOT NULL,
    ont_object_ref      VARCHAR,
    kg_object_ref       VARCHAR,
    semantic_view_ref   VARCHAR,
    conflict_detail     VARIANT,
    resolution_status   VARCHAR         NOT NULL DEFAULT 'OPEN',
    resolution_note     VARCHAR,
    detected_at         TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    resolved_at         TIMESTAMP_NTZ,
    PRIMARY KEY (conflict_id)
);

CREATE TABLE IF NOT EXISTS __ONT_DB__.__ONT_SCHEMA__.CANONICAL_METRIC_DECISIONS (
    decision_id               VARCHAR         NOT NULL,
    domain_name               VARCHAR         NOT NULL,
    metric_name               VARCHAR         NOT NULL,
    chosen_definition_source  VARCHAR,
    chosen_expression         VARCHAR,
    supporting_evidence       VARIANT,
    confidence                FLOAT,
    status                    VARCHAR,
    created_at                TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (decision_id)
);

CREATE TABLE IF NOT EXISTS __ONT_DB__.__ONT_SCHEMA__.METRIC_DEFINITION_EVIDENCE (
    evidence_id          VARCHAR         NOT NULL,
    domain_name          VARCHAR         NOT NULL,
    metric_name          VARCHAR         NOT NULL,
    source_type          VARCHAR         NOT NULL,
    source_ref           VARCHAR,
    expression_text      VARCHAR,
    evidence_payload     VARIANT,
    created_at           TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (evidence_id)
);
