-- =============================================================================
-- KG Data Discovery — Ops / Regression Runner Scaffolding
-- =============================================================================

CREATE TABLE IF NOT EXISTS KG_CONTROL.PUBLIC.REGRESSION_RESULTS (
    run_id              VARCHAR         NOT NULL,
    test_name           VARCHAR         NOT NULL,
    status              VARCHAR         NOT NULL,
    detail              VARIANT,
    created_at          TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.RUN_QUERY_PLANE_REGRESSION(
    domain_name VARCHAR
)
RETURNS VARIANT
LANGUAGE SQL
AS
$$
BEGIN
    INSERT INTO KG_CONTROL.PUBLIC.REGRESSION_RESULTS (run_id, test_name, status, detail)
    SELECT UUID_STRING(), 'domain_exists',
           CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL' END,
           OBJECT_CONSTRUCT('domain_name', :domain_name, 'count', COUNT(*))
    FROM KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
    WHERE domain_name = :domain_name;

    INSERT INTO KG_CONTROL.PUBLIC.REGRESSION_RESULTS (run_id, test_name, status, detail)
    SELECT UUID_STRING(), 'query_plane_tables_present',
           'INFO',
           OBJECT_CONSTRUCT('domain_name', :domain_name, 'meta_db', :domain_name || '_META');

    RETURN OBJECT_CONSTRUCT(
        'status', 'ok',
        'domain_name', :domain_name,
        'message', 'Regression scaffolding executed'
    );
END;
$$;
