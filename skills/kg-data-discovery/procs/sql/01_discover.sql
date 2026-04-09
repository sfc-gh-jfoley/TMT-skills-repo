-- =============================================================================
-- KG Data Discovery — Discovery & Configuration Stored Procedures
-- Procs: DISCOVER_DOMAINS, CONFIGURE_DOMAIN
-- Location: KG_CONTROL.PUBLIC
-- Prerequisite: 00_ddl.sql must be executed first.
-- Usage:
--   CALL KG_CONTROL.PUBLIC.DISCOVER_DOMAINS('SHALLOW', 7);
--   CALL KG_CONTROL.PUBLIC.DISCOVER_DOMAINS('DEEP', 90);
--   CALL KG_CONTROL.PUBLIC.CONFIGURE_DOMAIN('FINANCE',
--       ARRAY_CONSTRUCT('FINANCE_DB', 'FINANCE_ARCHIVE'),
--       PARSE_JSON('{"enrichment_max_tier": 2, "watch_enabled": true}'));
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. DISCOVER_DOMAINS
--    Profiles the account via SNOWFLAKE.ACCOUNT_USAGE and proposes logical
--    domain boundaries, priority tiers, and graduation readiness scores.
--    Pure read — no writes. Caller decides whether to bootstrap discovered domains.
--
--    mode = 'SHALLOW' : uses 7-day lookback regardless of lookback_days param
--    mode = 'DEEP'    : uses lookback_days (recommend 30–90)
-- -----------------------------------------------------------------------------

CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.DISCOVER_DOMAINS(
    mode          VARCHAR,
    lookback_days NUMBER
)
RETURNS TABLE (
    domain_name             VARCHAR,
    source_databases        VARCHAR,
    table_count             NUMBER,
    schema_count            NUMBER,
    total_query_volume      NUMBER,
    distinct_users          NUMBER,
    fk_relationship_count   NUMBER,
    schema_change_count_30d NUMBER,
    priority_tier           VARCHAR,
    graduation_candidate    BOOLEAN,
    recommendation          VARCHAR
)
LANGUAGE SQL
AS
$$
DECLARE
    lb       NUMBER  DEFAULT IFF(UPPER(mode) = 'SHALLOW', 7, COALESCE(lookback_days, 90));
    res      RESULTSET;
    sql_stmt VARCHAR DEFAULT '';
BEGIN
    sql_stmt :=
    'WITH
    raw_dbs AS (
        SELECT
            d.database_name,
            COALESCE(
                NULLIF(
                    REGEXP_REPLACE(UPPER(d.database_name),
                                   ''(_DB|_DW|_PROD|_DEV|_STAGE|_STG)$'', ''''),
                    ''''
                ),
                UPPER(d.database_name)
            ) AS domain_name
        FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES d
        WHERE d.deleted IS NULL
          AND UPPER(d.database_name) NOT IN
              (''SNOWFLAKE'', ''SNOWFLAKE_SAMPLE_DATA'', ''KG_CONTROL'')
          AND NOT REGEXP_LIKE(UPPER(d.database_name), ''.*_META$'')
    ),
    table_stats AS (
        SELECT
            t.TABLE_CATALOG                AS database_name,
            COUNT(*)                       AS table_count,
            COUNT(DISTINCT t.TABLE_SCHEMA) AS schema_count
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES t
        WHERE t.DELETED IS NULL
        GROUP BY t.TABLE_CATALOG
    ),
    schema_changes AS (
        SELECT
            t.TABLE_CATALOG AS database_name,
            COUNT(*)        AS schema_change_count_30d
        FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES t
        WHERE t.DELETED IS NULL
          AND t.LAST_ALTERED > DATEADD(day, -30, CURRENT_DATE())
        GROUP BY t.TABLE_CATALOG
    ),
    query_vol AS (
        SELECT
            q.DATABASE_NAME AS database_name,
            COUNT(*)        AS total_query_volume
        FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
        WHERE q.START_TIME >= DATEADD(day, -' || lb || ', CURRENT_DATE())
          AND q.DATABASE_NAME IS NOT NULL
          AND q.DATABASE_NAME != ''''
        GROUP BY q.DATABASE_NAME
    ),
    user_access AS (
        SELECT
            UPPER(SPLIT_PART(f.VALUE:objectName::VARCHAR, ''.'', 1)) AS database_name,
            COUNT(DISTINCT ah.USER_NAME)                              AS distinct_users
        FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY ah,
             LATERAL FLATTEN(INPUT => ah.BASE_OBJECTS_ACCESSED) AS f
        WHERE ah.QUERY_START_TIME >= DATEADD(day, -' || lb || ', CURRENT_DATE())
          AND f.VALUE:objectDomain::VARCHAR IN (''Table'', ''View'')
          AND SPLIT_PART(f.VALUE:objectName::VARCHAR, ''.'', 1) IS NOT NULL
          AND SPLIT_PART(f.VALUE:objectName::VARCHAR, ''.'', 1) != ''''
        GROUP BY UPPER(SPLIT_PART(f.VALUE:objectName::VARCHAR, ''.'', 1))
    ),
    fk_counts AS (
        SELECT
            od.REFERENCING_DATABASE AS database_name,
            COUNT(*)                AS fk_relationship_count
        FROM SNOWFLAKE.ACCOUNT_USAGE.OBJECT_DEPENDENCIES od
        WHERE od.REFERENCING_DATABASE IS NOT NULL
          AND od.REFERENCING_DATABASE != ''''
        GROUP BY od.REFERENCING_DATABASE
    ),
    domain_agg AS (
        SELECT
            d.domain_name,
            LISTAGG(DISTINCT d.database_name, '','')      AS source_databases,
            COALESCE(SUM(ts.table_count),              0) AS table_count,
            COALESCE(SUM(ts.schema_count),             0) AS schema_count,
            COALESCE(SUM(qv.total_query_volume),       0) AS total_query_volume,
            COALESCE(MAX(ua.distinct_users),           0) AS distinct_users,
            COALESCE(SUM(fk.fk_relationship_count),    0) AS fk_relationship_count,
            COALESCE(SUM(sc.schema_change_count_30d),  0) AS schema_change_count_30d
        FROM raw_dbs d
        LEFT JOIN table_stats    ts ON UPPER(ts.database_name) = UPPER(d.database_name)
        LEFT JOIN schema_changes sc ON UPPER(sc.database_name) = UPPER(d.database_name)
        LEFT JOIN query_vol      qv ON UPPER(qv.database_name) = UPPER(d.database_name)
        LEFT JOIN user_access    ua ON UPPER(ua.database_name) = UPPER(d.database_name)
        LEFT JOIN fk_counts      fk ON UPPER(fk.database_name) = UPPER(d.database_name)
        GROUP BY d.domain_name
        HAVING COALESCE(SUM(ts.table_count), 0) > 0
            OR COALESCE(SUM(qv.total_query_volume), 0) > 0
    )
    SELECT
        domain_name::VARCHAR,
        source_databases::VARCHAR,
        table_count::NUMBER,
        schema_count::NUMBER,
        total_query_volume::NUMBER,
        distinct_users::NUMBER,
        fk_relationship_count::NUMBER,
        schema_change_count_30d::NUMBER,
        CASE
            WHEN total_query_volume > 500
                 AND table_count BETWEEN 5 AND 200     THEN ''PHASE_1''
            WHEN total_query_volume > 100
                 OR  table_count > 200                  THEN ''PHASE_2''
            WHEN total_query_volume > 0                 THEN ''PHASE_3''
            ELSE ''LOW''
        END::VARCHAR AS priority_tier,
        IFF(
            fk_relationship_count  >= 2
            AND table_count        >= 3
            AND total_query_volume >  100
            AND schema_change_count_30d = 0,
            TRUE, FALSE
        )::BOOLEAN AS graduation_candidate,
        CASE
            WHEN total_query_volume > 500
                 AND table_count BETWEEN 5 AND 200
                 AND schema_change_count_30d = 0
                THEN ''High query volume, stable schema — ideal first domain''
            WHEN table_count > 200
                THEN ''Large schema, start with SHALLOW crawl''
            WHEN total_query_volume > 100
                 AND schema_change_count_30d > 0
                THEN ''Active schema changes — enrich after stabilization''
            WHEN fk_relationship_count >= 2
                 AND total_query_volume > 100
                THEN ''FK-rich domain — strong graduation candidate''
            WHEN fk_relationship_count >= 2
                THEN ''FK relationships detected — consider onboarding''
            WHEN total_query_volume > 0
                THEN ''Low activity — monitor before onboarding''
            ELSE ''No recent query activity — consider skipping''
        END::VARCHAR AS recommendation
    FROM domain_agg
    ORDER BY total_query_volume DESC, table_count DESC';

    res := (EXECUTE IMMEDIATE sql_stmt);
    RETURN TABLE(res);
END;
$$;


-- -----------------------------------------------------------------------------
-- 2. CONFIGURE_DOMAIN
--    Updates DOMAIN_REGISTRY.source_databases and upserts config keys into
--    {DOMAIN}_META.META.DOMAIN_CONFIG.
--    Domain must exist in DOMAIN_REGISTRY (run BOOTSTRAP_KG_META first).
-- -----------------------------------------------------------------------------

CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.CONFIGURE_DOMAIN(
    domain_name      VARCHAR,
    source_databases ARRAY,
    config_overrides VARIANT
)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    domain_upper  VARCHAR   DEFAULT UPPER(domain_name);
    meta_schema   VARCHAR   DEFAULT UPPER(domain_name) || '_META.META';
    check_count   NUMBER    DEFAULT 0;
    num_dbs       NUMBER    DEFAULT 0;
    tier_val      VARCHAR   DEFAULT '0';
    tier_res      RESULTSET;
    err_not_found EXCEPTION (-20001, 'Domain not found in DOMAIN_REGISTRY — run BOOTSTRAP_KG_META first');
BEGIN
    check_count := (
        SELECT COUNT(*)
        FROM KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
        WHERE domain_name = :domain_upper
    );

    IF (check_count = 0) THEN
        RAISE err_not_found;
    END IF;

    num_dbs := ARRAY_SIZE(source_databases);

    UPDATE KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
    SET    source_databases = :source_databases,
           updated_at       = CURRENT_TIMESTAMP()
    WHERE  domain_name = :domain_upper;

    EXECUTE IMMEDIATE '
    MERGE INTO ' || meta_schema || '.DOMAIN_CONFIG AS t
    USING (SELECT ? AS config_key, PARSE_JSON(?) AS config_value) AS s
    ON t.config_key = s.config_key
    WHEN MATCHED THEN
        UPDATE SET config_value = s.config_value,
                   updated_at   = CURRENT_TIMESTAMP(),
                   updated_by   = CURRENT_USER()
    WHEN NOT MATCHED THEN
        INSERT (config_key, config_value, updated_at, updated_by)
        VALUES (s.config_key, s.config_value, CURRENT_TIMESTAMP(), CURRENT_USER())
    ' USING ('source_databases', TO_VARCHAR(:source_databases));

    IF (config_overrides IS NOT NULL) THEN
        FOR rec IN (
            SELECT f.KEY::VARCHAR        AS k,
                   TO_VARCHAR(f.VALUE)   AS v
            FROM TABLE(FLATTEN(INPUT => config_overrides)) AS f
        ) DO
            EXECUTE IMMEDIATE '
            MERGE INTO ' || meta_schema || '.DOMAIN_CONFIG AS t
            USING (SELECT ? AS config_key, PARSE_JSON(?) AS config_value) AS s
            ON t.config_key = s.config_key
            WHEN MATCHED THEN
                UPDATE SET config_value = s.config_value,
                           updated_at   = CURRENT_TIMESTAMP(),
                           updated_by   = CURRENT_USER()
            WHEN NOT MATCHED THEN
                INSERT (config_key, config_value, updated_at, updated_by)
                VALUES (s.config_key, s.config_value, CURRENT_TIMESTAMP(), CURRENT_USER())
            ' USING (rec.k, rec.v);
        END FOR;
    END IF;

    tier_res := (EXECUTE IMMEDIATE '
        SELECT COALESCE(config_value::VARCHAR, ''0'') AS tier_value
        FROM ' || meta_schema || '.DOMAIN_CONFIG
        WHERE config_key = ''enrichment_max_tier'''
    );
    FOR r IN tier_res DO
        tier_val := r.tier_value;
    END FOR;

    RETURN 'CONFIGURED: ' || domain_upper || ' — ' || num_dbs::VARCHAR
        || ' source databases, tier=' || tier_val;
END;
$$;


-- -----------------------------------------------------------------------------
-- Validation — run after deploy to confirm procedures exist
-- -----------------------------------------------------------------------------

SHOW PROCEDURES LIKE '%DISCOVER%' IN SCHEMA KG_CONTROL.PUBLIC;
SHOW PROCEDURES LIKE '%CONFIGURE%' IN SCHEMA KG_CONTROL.PUBLIC;
