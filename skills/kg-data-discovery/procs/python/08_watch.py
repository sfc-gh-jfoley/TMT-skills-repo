RUN_WATCH_DDL = """
CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.RUN_WATCH(
    domain_name VARCHAR
)
RETURNS TABLE(object_fqn VARCHAR, object_level VARCHAR, object_state VARCHAR, triage_action VARCHAR, triage_reason VARCHAR, possible_ontology_class VARCHAR)
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'main'
AS
$$
import json
from datetime import datetime, timezone
from snowflake.snowpark import Session
from snowflake.snowpark import DataFrame


def get_config(session: Session, domain_name: str, key: str):
    db = domain_name.upper() + '_META'
    rows = session.sql(
        f"SELECT config_value FROM {db}.META.DOMAIN_CONFIG WHERE config_key = ?",
        [key]
    ).collect()
    if rows:
        try:
            return json.loads(rows[0][0])
        except Exception:
            return rows[0][0]
    return None


def upsert_state(session, meta_db, domain_upper, fqn, level, state,
                 action, reason, possible_ont_class=None, concept_id=None,
                 drift_details=None, access_count=None, distinct_users=None):
    now_ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    drift_ts = now_ts if state in ('KNOWN_DRIFTED', 'ONTOLOGY_DRIFT') else None
    try:
        session.sql(f"""
            MERGE INTO {meta_db}.META.OBJECT_STATE AS tgt
            USING (SELECT ? AS object_fqn) AS src ON tgt.object_fqn = src.object_fqn
            WHEN MATCHED THEN UPDATE SET
                object_state            = ?,
                triage_action           = ?,
                triage_reason           = ?,
                possible_ontology_class = COALESCE(?, tgt.possible_ontology_class),
                drift_details           = COALESCE(?, tgt.drift_details),
                drift_detected_at       = COALESCE(?, tgt.drift_detected_at),
                access_count_30d        = COALESCE(?, tgt.access_count_30d),
                distinct_users_30d      = COALESCE(?, tgt.distinct_users_30d),
                updated_at              = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                object_fqn, object_level, domain, object_state,
                concept_id, triage_action, triage_reason,
                possible_ontology_class, drift_details, drift_detected_at,
                access_count_30d, distinct_users_30d, updated_at
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, CURRENT_TIMESTAMP()
            )
        """, [
            fqn,
            state, action, reason,
            possible_ont_class, drift_details, drift_ts,
            access_count, distinct_users,
            fqn, level, domain_upper, state,
            concept_id, action, reason,
            possible_ont_class, drift_details, drift_ts,
            access_count, distinct_users,
        ]).collect()
    except Exception:
        pass


def main(session: Session, domain_name: str) -> DataFrame:
    domain_upper = domain_name.upper()
    meta_db = domain_upper + '_META'

    src_dbs_raw = get_config(session, domain_upper, 'source_databases')
    source_dbs = src_dbs_raw if isinstance(src_dbs_raw, list) else ([src_dbs_raw] if src_dbs_raw else [])

    ont_agent = get_config(session, domain_upper, 'ontology_agent')
    ont_db = get_config(session, domain_upper, 'ontology_database') if ont_agent else None
    ont_schema = get_config(session, domain_upper, 'ontology_schema') if ont_agent else None

    findings = []

    for db in source_dbs:
        db_upper = db.upper()

        # States 1 + 2: KNOWN_CURRENT / KNOWN_DRIFTED
        # CONCEPTS ∩ ACCOUNT_USAGE.TABLES — compare last_altered vs enrichment_timestamp
        try:
            known = session.sql(f"""
                SELECT c.concept_id, c.table_fqn,
                       c.enrichment_timestamp, c.metadata_hash,
                       t.last_altered
                FROM {meta_db}.META.CONCEPTS c
                JOIN SNOWFLAKE.ACCOUNT_USAGE.TABLES t
                    ON t.table_catalog = c.source_database
                   AND t.table_schema  = c.source_schema
                   AND t.table_name    = c.source_table
                WHERE c.source_database = ?
                  AND c.is_active = TRUE
                  AND c.concept_level = 'table'
                  AND t.deleted IS NULL
            """, [db_upper]).collect()

            for r in known:
                drifted = (
                    r['LAST_ALTERED'] is not None
                    and r['ENRICHMENT_TIMESTAMP'] is not None
                    and r['LAST_ALTERED'] > r['ENRICHMENT_TIMESTAMP']
                )
                if drifted:
                    state = 'KNOWN_DRIFTED'
                    action = 're-enrich'
                    reason = 'Schema altered after last enrichment. Re-run CRAWL_TABLE then ENRICH_DOMAIN.'
                    drift_details = f"last_altered {r['LAST_ALTERED']} > enrichment_timestamp {r['ENRICHMENT_TIMESTAMP']}"
                else:
                    state = 'KNOWN_CURRENT'
                    action = 'ignore'
                    reason = 'Metadata is current. No action needed.'
                    drift_details = None

                upsert_state(session, meta_db, domain_upper,
                             r['TABLE_FQN'], 'table', state, action, reason,
                             concept_id=r['CONCEPT_ID'],
                             drift_details=drift_details)
                findings.append((r['TABLE_FQN'], 'table', state, action, reason, None))
        except Exception:
            pass

        # State 3: KNOWN_DELETED — in CONCEPTS but not in ACCOUNT_USAGE.TABLES
        try:
            deleted = session.sql(f"""
                SELECT c.concept_id, c.table_fqn
                FROM {meta_db}.META.CONCEPTS c
                WHERE c.source_database = ?
                  AND c.is_active = TRUE
                  AND c.concept_level = 'table'
                  AND NOT EXISTS (
                      SELECT 1 FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES t
                      WHERE t.table_catalog = c.source_database
                        AND t.table_schema  = c.source_schema
                        AND t.table_name    = c.source_table
                        AND t.deleted IS NULL
                  )
            """, [db_upper]).collect()

            for r in deleted:
                upsert_state(session, meta_db, domain_upper,
                             r['TABLE_FQN'], 'table', 'KNOWN_DELETED',
                             'ignore', 'Object no longer exists in ACCOUNT_USAGE. Mark inactive.',
                             concept_id=r['CONCEPT_ID'])
                findings.append((
                    r['TABLE_FQN'], 'table', 'KNOWN_DELETED',
                    'ignore', 'Object no longer exists in ACCOUNT_USAGE. Mark inactive.', None
                ))
        except Exception:
            pass

        # State 4: ONBOARDED_INCORRECTLY — enrichment_quality_score < 0.3
        try:
            poor = session.sql(f"""
                SELECT c.concept_id, c.table_fqn, c.enrichment_quality_score
                FROM {meta_db}.META.CONCEPTS c
                WHERE c.source_database = ?
                  AND c.is_active = TRUE
                  AND c.concept_level = 'table'
                  AND c.enrichment_quality_score < 0.3
            """, [db_upper]).collect()

            for r in poor:
                score = r['ENRICHMENT_QUALITY_SCORE'] or 0.0
                reason = f"Quality score {score:.2f} below 0.3. Re-run ENRICH_DOMAIN with higher tier."
                upsert_state(session, meta_db, domain_upper,
                             r['TABLE_FQN'], 'table', 'ONBOARDED_INCORRECTLY',
                             're-enrich', reason,
                             concept_id=r['CONCEPT_ID'])
                findings.append((r['TABLE_FQN'], 'table', 'ONBOARDED_INCORRECTLY', 're-enrich', reason, None))
        except Exception:
            pass

        # States 5 + 6: SHADOW_ACTIVE / SHADOW_INACTIVE
        # ACCOUNT_USAGE.TABLES not in CONCEPTS — check ACCESS_HISTORY
        try:
            shadow = session.sql(f"""
                SELECT t.table_catalog || '.' || t.table_schema || '.' || t.table_name AS table_fqn,
                       t.table_schema, t.table_name
                FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES t
                WHERE t.table_catalog = ?
                  AND t.deleted IS NULL
                  AND t.table_schema != 'INFORMATION_SCHEMA'
                  AND NOT EXISTS (
                      SELECT 1 FROM {meta_db}.META.CONCEPTS c
                      WHERE c.source_database = t.table_catalog
                        AND c.source_schema   = t.table_schema
                        AND c.source_table    = t.table_name
                        AND c.is_active = TRUE
                  )
            """, [db_upper]).collect()

            if shadow:
                try:
                    access_data = session.sql(f"""
                        SELECT
                            base.value:objectName::VARCHAR AS table_fqn,
                            COUNT(*) AS access_count,
                            COUNT(DISTINCT ah.user_name) AS distinct_users
                        FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY ah,
                             LATERAL FLATTEN(input => ah.base_objects_accessed) base
                        WHERE ah.query_start_time > DATEADD('day', -30, CURRENT_TIMESTAMP())
                          AND base.value:objectDomain::VARCHAR = 'Table'
                          AND base.value:objectName::VARCHAR LIKE ?
                        GROUP BY 1
                    """, [db_upper + '.%']).collect()
                    access_map = {
                        r['TABLE_FQN'].upper(): (r['ACCESS_COUNT'], r['DISTINCT_USERS'])
                        for r in access_data
                    }
                except Exception:
                    access_map = {}

                ont_class_map = {}
                if ont_agent and ont_db and ont_schema:
                    try:
                        ont_classes = session.sql(f"""
                            SELECT class_name, _source_table
                            FROM {ont_db}.{ont_schema}.ONT_CLASS
                            WHERE _source_table IS NOT NULL
                        """).collect()
                        ont_class_map = {
                            oc['_SOURCE_TABLE'].upper(): oc['CLASS_NAME']
                            for oc in ont_classes if oc['_SOURCE_TABLE']
                        }
                    except Exception:
                        pass

                for r in shadow:
                    fqn = r['TABLE_FQN']
                    acc_info = access_map.get(fqn.upper(), (0, 0))
                    acc, dist_users = acc_info

                    if acc and acc > 0:
                        state = 'SHADOW_ACTIVE'
                        action = 'onboard'
                        reason = f"Not in KG but has {acc} access(es) in last 30d. Run CRAWL_TABLE to index."
                    else:
                        state = 'SHADOW_INACTIVE'
                        action = 'defer'
                        reason = 'Not in KG and no ACCESS_HISTORY in last 30d. Low priority.'

                    possible_ont_class = None

                    # Ontology Hook 5: compare shadow table columns against ONT_CLASS patterns
                    if ont_agent and ont_db and ont_schema and ont_class_map:
                        try:
                            parts = fqn.split('.')
                            if len(parts) == 3:
                                tbl_db, tbl_sch, tbl_tbl = parts
                                shadow_col_rows = session.sql(f"""
                                    SELECT column_name
                                    FROM SNOWFLAKE.ACCOUNT_USAGE.COLUMNS
                                    WHERE table_catalog = ?
                                      AND table_schema  = ?
                                      AND table_name    = ?
                                """, [tbl_db.upper(), tbl_sch.upper(), tbl_tbl.upper()]).collect()
                                shadow_cols = set(c['COLUMN_NAME'].upper() for c in shadow_col_rows)

                                if shadow_cols:
                                    best_class = None
                                    best_score = 0.0

                                    for src_fqn, class_name in ont_class_map.items():
                                        src_parts = src_fqn.split('.')
                                        if len(src_parts) != 3:
                                            continue
                                        oc_db, oc_sch, oc_tbl = src_parts
                                        try:
                                            ont_col_rows = session.sql(f"""
                                                SELECT column_name
                                                FROM SNOWFLAKE.ACCOUNT_USAGE.COLUMNS
                                                WHERE table_catalog = ?
                                                  AND table_schema  = ?
                                                  AND table_name    = ?
                                            """, [oc_db, oc_sch, oc_tbl]).collect()
                                        except Exception:
                                            continue
                                        ont_cols = set(c['COLUMN_NAME'].upper() for c in ont_col_rows)
                                        if not ont_cols:
                                            continue
                                        union = shadow_cols | ont_cols
                                        score = len(shadow_cols & ont_cols) / len(union)
                                        if score > best_score:
                                            best_score = score
                                            best_class = class_name

                                    if best_score >= 0.7 and best_class:
                                        possible_ont_class = best_class
                                        action = 'ontology_review'
                                        reason = (
                                            f"Column similarity {best_score:.0%} with ONT_CLASS '{best_class}'. "
                                            "Consider mapping to formal ontology class."
                                        )
                        except Exception:
                            pass

                    upsert_state(session, meta_db, domain_upper,
                                 fqn, 'table', state, action, reason,
                                 possible_ont_class=possible_ont_class,
                                 access_count=acc if acc else 0,
                                 distinct_users=dist_users if dist_users else 0)
                    findings.append((fqn, 'table', state, action, reason, possible_ont_class))
        except Exception:
            pass

        # Surface existing ONTOLOGY_DRIFT rows (Hook 4 — written by CRAWL_DOMAIN)
        try:
            drift_rows = session.sql(f"""
                SELECT os.object_fqn, os.drift_details, os.drift_detected_at
                FROM {meta_db}.META.OBJECT_STATE os
                WHERE os.object_state = 'ONTOLOGY_DRIFT'
                  AND os.domain = ?
            """, [domain_upper]).collect()

            seen_fqns = {f[0] for f in findings}
            for d in drift_rows:
                if d['OBJECT_FQN'] not in seen_fqns:
                    reason = (
                        f"Schema diverged from ontology since {d['DRIFT_DETECTED_AT']}. "
                        f"{d['DRIFT_DETAILS'] or ''}"
                    ).strip()
                    findings.append((
                        d['OBJECT_FQN'], 'table', 'ONTOLOGY_DRIFT',
                        'ontology_review', reason, None
                    ))
        except Exception:
            pass

    if not findings:
        findings = [(
            '', 'table', 'KNOWN_CURRENT',
            'ignore', 'Domain is up-to-date. No changes detected.', None
        )]

    return session.create_dataframe(
        findings,
        schema=['object_fqn', 'object_level', 'object_state',
                'triage_action', 'triage_reason', 'possible_ontology_class']
    )
$$;
"""
