-- =============================================================================
-- KG Data Discovery — Promotion Loop Scaffolding
-- Additive only. Generates promotion candidates from repeated transient-contract success.
-- =============================================================================

CREATE TABLE IF NOT EXISTS KG_CONTROL.PUBLIC.PROMOTION_CANDIDATES (
    candidate_id        VARCHAR         NOT NULL,
    domain_name         VARCHAR         NOT NULL,
    route_source        VARCHAR         NOT NULL,
    sample_questions    VARIANT,
    evidence_payload    VARIANT,
    proposed_sv_name    VARCHAR,
    proposed_sv_ddl     VARCHAR,
    approval_status     VARCHAR         NOT NULL DEFAULT 'SV_CANDIDATE',
    created_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (candidate_id)
);

CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.PROMOTE_QUERY_PATTERNS(
    domain_name       VARCHAR,
    min_query_count   NUMBER,
    min_success_rate  FLOAT
)
RETURNS VARIANT
LANGUAGE SQL
AS
$$
DECLARE
    candidate_count NUMBER DEFAULT 0;
BEGIN
    INSERT INTO KG_CONTROL.PUBLIC.PROMOTION_CANDIDATES (
        candidate_id, domain_name, route_source, sample_questions, evidence_payload, proposed_sv_name, proposed_sv_ddl
    )
    SELECT
        UUID_STRING(),
        :domain_name,
        'TRANSIENT_CONTRACT',
        ARRAY_AGG(question),
        OBJECT_CONSTRUCT(
            'query_count', COUNT(*),
            'success_count', COUNT_IF(execution_status = 'validated'),
            'avg_quality', AVG(assembly_quality_score)
        ),
        :domain_name || '_PROMOTED_SV',
        NULL
    FROM KG_CONTROL.PUBLIC.QUERY_LOG
    WHERE resolution_route = 'TRANSIENT_CONTRACT'
      AND execution_status = 'validated'
      AND ( :domain_name IS NULL OR question ILIKE '%' || :domain_name || '%' )
    GROUP BY 1,2,3,6,7;

    candidate_count := SQLROWCOUNT;

    RETURN OBJECT_CONSTRUCT(
        'status', 'ok',
        'candidates_created', candidate_count
    );
END;
$$;
