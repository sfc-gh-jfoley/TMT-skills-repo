CRAWL_DOMAIN_DDL = """
CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.CRAWL_DOMAIN(
    domain_name VARCHAR,
    mode VARCHAR
)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'main'
AS
$$
import hashlib
import json
import uuid
from datetime import datetime, timezone
from snowflake.snowpark import Session


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


def compute_hash(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def main(session: Session, domain_name: str, mode: str) -> str:
    domain_upper = domain_name.upper()
    meta_db = domain_upper + '_META'
    mode_upper = mode.upper()

    source_databases = get_config(session, domain_upper, 'source_databases') or []
    ignore_schemas_cfg = get_config(session, domain_upper, 'ignore_schemas') or ['INFORMATION_SCHEMA']
    ignore_schemas = [s.upper() for s in ignore_schemas_cfg]
    if 'INFORMATION_SCHEMA' not in ignore_schemas:
        ignore_schemas.append('INFORMATION_SCHEMA')

    crawl_ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    total_tables = 0
    total_schemas = 0
    total_databases = 0

    all_rows = []

    for db_name in source_databases:
        db_upper = db_name.upper()

        db_rows = session.sql("""
            SELECT database_name, database_owner, comment, created,
                   'database' AS concept_level
            FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES
            WHERE deleted IS NULL
              AND database_name = ?
        """, [db_upper]).collect()

        schema_rows = session.sql("""
            SELECT catalog_name AS source_database,
                   schema_name AS source_schema,
                   schema_owner AS owner,
                   is_managed_access,
                   'schema' AS concept_level
            FROM SNOWFLAKE.ACCOUNT_USAGE.SCHEMATA
            WHERE deleted IS NULL
              AND catalog_name = ?
              AND schema_name NOT IN ('INFORMATION_SCHEMA')
        """, [db_upper]).collect()

        table_rows = session.sql("""
            SELECT table_catalog AS source_database,
                   table_schema AS source_schema,
                   table_name AS source_table,
                   table_type,
                   row_count,
                   bytes,
                   clustering_key,
                   comment,
                   created AS created_at_src,
                   last_altered AS last_altered_src,
                   table_owner AS owner,
                   is_transient
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
            WHERE deleted IS NULL
              AND table_catalog = ?
              AND table_schema NOT IN ('INFORMATION_SCHEMA')
        """, [db_upper]).collect()

        col_rows = session.sql("""
            SELECT table_catalog, table_schema, table_name,
                   column_name, data_type, is_nullable, column_default, comment,
                   ordinal_position
            FROM SNOWFLAKE.ACCOUNT_USAGE.COLUMNS
            WHERE table_catalog = ?
              AND table_schema NOT IN ('INFORMATION_SCHEMA')
            ORDER BY table_schema, table_name, ordinal_position
        """, [db_upper]).collect()

        constraint_rows = session.sql("""
            SELECT table_catalog, table_schema, table_name,
                   constraint_name, constraint_type,
                   NULL AS ref_table_name
            FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_CONSTRAINTS
            WHERE table_catalog = ?
              AND constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
        """, [db_upper]).collect()

        cols_by_table = {}
        for c in col_rows:
            sch = c['TABLE_SCHEMA'].upper()
            tbl = c['TABLE_NAME'].upper()
            if sch in ignore_schemas:
                continue
            key = (sch, tbl)
            if key not in cols_by_table:
                cols_by_table[key] = []
            cols_by_table[key].append({
                'name': c['COLUMN_NAME'],
                'type': c['DATA_TYPE'],
                'nullable': c['IS_NULLABLE'],
                'comment': c['COMMENT'],
                'ordinal': c['ORDINAL_POSITION']
            })

        constraints_by_table = {}
        for cn in constraint_rows:
            sch = cn['TABLE_SCHEMA'].upper()
            tbl = cn['TABLE_NAME'].upper()
            if sch in ignore_schemas:
                continue
            key = (sch, tbl)
            if key not in constraints_by_table:
                constraints_by_table[key] = []
            constraints_by_table[key].append({
                'name': cn['CONSTRAINT_NAME'],
                'type': cn['CONSTRAINT_TYPE'],
                'columns': [],
                'ref_table': cn['REF_TABLE_NAME'],
                'ref_cols': []
            })

        if db_rows:
            db_row = db_rows[0]
            total_databases += 1
            all_rows.append({
                'concept_id': str(uuid.uuid4()),
                'concept_level': 'database',
                'domain': domain_upper,
                'source_database': db_upper,
                'source_schema': None,
                'source_table': None,
                'table_fqn': None,
                'table_type': None,
                'row_count': None,
                'bytes': None,
                'clustering_key': None,
                'comment': db_row['COMMENT'],
                'created_at_src': str(db_row['CREATED']) if db_row['CREATED'] else None,
                'last_altered_src': None,
                'owner': db_row['DATABASE_OWNER'],
                'is_transient': False,
                'is_managed_access': False,
                'is_active': True,
                'columns_json': None,
                'constraints_json': None,
                'sample_values_json': None,
                'crawl_source': 'ACCOUNT_USAGE',
                'crawl_timestamp': crawl_ts,
                'metadata_hash': None
            })

        seen_schemas = set()
        for sr in schema_rows:
            sch = sr['SOURCE_SCHEMA'].upper()
            if sch in ignore_schemas:
                continue
            seen_schemas.add(sch)
            total_schemas += 1
            all_rows.append({
                'concept_id': str(uuid.uuid4()),
                'concept_level': 'schema',
                'domain': domain_upper,
                'source_database': db_upper,
                'source_schema': sch,
                'source_table': None,
                'table_fqn': None,
                'table_type': None,
                'row_count': None,
                'bytes': None,
                'clustering_key': None,
                'comment': None,
                'created_at_src': None,
                'last_altered_src': None,
                'owner': sr['OWNER'],
                'is_transient': False,
                'is_managed_access': sr['IS_MANAGED_ACCESS'] == 'YES' if sr['IS_MANAGED_ACCESS'] else False,
                'is_active': True,
                'columns_json': None,
                'constraints_json': None,
                'sample_values_json': None,
                'crawl_source': 'ACCOUNT_USAGE',
                'crawl_timestamp': crawl_ts,
                'metadata_hash': None
            })

        for tr in table_rows:
            sch = tr['SOURCE_SCHEMA'].upper()
            tbl = tr['SOURCE_TABLE'].upper()
            if sch in ignore_schemas:
                continue
            total_tables += 1
            key = (sch, tbl)
            cols = cols_by_table.get(key, [])
            constraints = constraints_by_table.get(key, [])
            cols_json_str = json.dumps(cols, default=str)
            constraints_json_str = json.dumps(constraints, default=str)
            meta_hash = compute_hash(cols_json_str)
            table_fqn = f"{db_upper}.{sch}.{tbl}"
            is_transient = tr['IS_TRANSIENT'] == 'YES' if tr['IS_TRANSIENT'] else False
            all_rows.append({
                'concept_id': str(uuid.uuid4()),
                'concept_level': 'table',
                'domain': domain_upper,
                'source_database': db_upper,
                'source_schema': sch,
                'source_table': tbl,
                'table_fqn': table_fqn,
                'table_type': tr['TABLE_TYPE'],
                'row_count': tr['ROW_COUNT'],
                'bytes': tr['BYTES'],
                'clustering_key': tr['CLUSTERING_KEY'],
                'comment': tr['COMMENT'],
                'created_at_src': str(tr['CREATED_AT_SRC']) if tr['CREATED_AT_SRC'] else None,
                'last_altered_src': str(tr['LAST_ALTERED_SRC']) if tr['LAST_ALTERED_SRC'] else None,
                'owner': tr['OWNER'],
                'is_transient': is_transient,
                'is_managed_access': False,
                'is_active': True,
                'columns_json': cols_json_str,
                'constraints_json': constraints_json_str,
                'sample_values_json': None,
                'crawl_source': 'ACCOUNT_USAGE',
                'crawl_timestamp': crawl_ts,
                'metadata_hash': meta_hash
            })

    target = f"{meta_db}.META.RAW_CONCEPTS"

    if mode_upper == 'FULL':
        session.sql(f"""
            DELETE FROM {target}
            WHERE domain = ?
        """, [domain_upper]).collect()

        for row in all_rows:
            session.sql(f"""
                INSERT INTO {target} (
                    concept_id, concept_level, domain,
                    source_database, source_schema, source_table,
                    table_fqn, table_type, row_count, bytes,
                    clustering_key, comment, created_at_src, last_altered_src,
                    owner, is_transient, is_managed_access, is_active,
                    columns_json, constraints_json, sample_values_json,
                    crawl_source, crawl_timestamp, metadata_hash
                ) VALUES (
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    PARSE_JSON(?), PARSE_JSON(?), PARSE_JSON(?),
                    ?, ?, ?
                )
            """, [
                row['concept_id'], row['concept_level'], row['domain'],
                row['source_database'], row['source_schema'], row['source_table'],
                row['table_fqn'], row['table_type'], row['row_count'], row['bytes'],
                row['clustering_key'], row['comment'], row['created_at_src'], row['last_altered_src'],
                row['owner'], row['is_transient'], row['is_managed_access'], row['is_active'],
                row['columns_json'], row['constraints_json'], row['sample_values_json'],
                row['crawl_source'], row['crawl_timestamp'], row['metadata_hash']
            ]).collect()

    else:
        for row in all_rows:
            existing = session.sql(f"""
                SELECT concept_id, metadata_hash
                FROM {target}
                WHERE concept_level = ?
                  AND source_database = ?
                  AND COALESCE(source_schema, '') = COALESCE(?, '')
                  AND COALESCE(source_table, '') = COALESCE(?, '')
            """, [
                row['concept_level'],
                row['source_database'],
                row['source_schema'] or '',
                row['source_table'] or ''
            ]).collect()

            if not existing:
                session.sql(f"""
                    INSERT INTO {target} (
                        concept_id, concept_level, domain,
                        source_database, source_schema, source_table,
                        table_fqn, table_type, row_count, bytes,
                        clustering_key, comment, created_at_src, last_altered_src,
                        owner, is_transient, is_managed_access, is_active,
                        columns_json, constraints_json, sample_values_json,
                        crawl_source, crawl_timestamp, metadata_hash
                    ) VALUES (
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        PARSE_JSON(?), PARSE_JSON(?), PARSE_JSON(?),
                        ?, ?, ?
                    )
                """, [
                    row['concept_id'], row['concept_level'], row['domain'],
                    row['source_database'], row['source_schema'], row['source_table'],
                    row['table_fqn'], row['table_type'], row['row_count'], row['bytes'],
                    row['clustering_key'], row['comment'], row['created_at_src'], row['last_altered_src'],
                    row['owner'], row['is_transient'], row['is_managed_access'], row['is_active'],
                    row['columns_json'], row['constraints_json'], row['sample_values_json'],
                    row['crawl_source'], row['crawl_timestamp'], row['metadata_hash']
                ]).collect()
            else:
                existing_hash = existing[0]['METADATA_HASH']
                if existing_hash != row['metadata_hash']:
                    existing_id = existing[0]['CONCEPT_ID']
                    session.sql(f"""
                        UPDATE {target}
                        SET table_type = ?,
                            row_count = ?,
                            bytes = ?,
                            clustering_key = ?,
                            comment = ?,
                            created_at_src = ?,
                            last_altered_src = ?,
                            owner = ?,
                            is_transient = ?,
                            is_managed_access = ?,
                            is_active = ?,
                            columns_json = PARSE_JSON(?),
                            constraints_json = PARSE_JSON(?),
                            crawl_source = ?,
                            crawl_timestamp = ?,
                            metadata_hash = ?
                        WHERE concept_id = ?
                    """, [
                        row['table_type'], row['row_count'], row['bytes'],
                        row['clustering_key'], row['comment'],
                        row['created_at_src'], row['last_altered_src'],
                        row['owner'], row['is_transient'], row['is_managed_access'], row['is_active'],
                        row['columns_json'], row['constraints_json'],
                        row['crawl_source'], row['crawl_timestamp'], row['metadata_hash'],
                        existing_id
                    ]).collect()

    ont_agent = get_config(session, domain_upper, 'ontology_agent')
    if ont_agent:
        ont_db = get_config(session, domain_upper, 'ontology_database')
        ont_schema = get_config(session, domain_upper, 'ontology_schema')
        if ont_db and ont_schema:
            try:
                ont_class_rows = session.sql(f"""
                    SELECT _source_table, class_name
                    FROM {ont_db}.{ont_schema}.ONT_CLASS
                    WHERE _source_table IS NOT NULL
                """).collect()

                crawled_hashes = {}
                for r in all_rows:
                    if r['concept_level'] == 'table' and r['table_fqn']:
                        crawled_hashes[r['table_fqn'].upper()] = r['metadata_hash']

                for ont_row in ont_class_rows:
                    src_table = ont_row['_SOURCE_TABLE']
                    if not src_table:
                        continue
                    src_upper = src_table.upper()
                    if src_upper in crawled_hashes:
                        new_hash = crawled_hashes[src_upper]
                        prev_rows = session.sql(f"""
                            SELECT metadata_hash
                            FROM {target}
                            WHERE table_fqn = ?
                              AND concept_level = 'table'
                        """, [src_upper]).collect()
                        if prev_rows:
                            prev_hash = prev_rows[0]['METADATA_HASH']
                            if prev_hash and prev_hash != new_hash:
                                drift_ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                                parts = src_upper.split('.')
                                obj_level = 'table' if len(parts) == 3 else ('schema' if len(parts) == 2 else 'database')
                                session.sql(f"""
                                    MERGE INTO {meta_db}.META.OBJECT_STATE AS tgt
                                    USING (SELECT ? AS object_fqn) AS src ON tgt.object_fqn = src.object_fqn
                                    WHEN MATCHED THEN UPDATE SET
                                        object_state = 'ONTOLOGY_DRIFT',
                                        previous_hash = tgt.metadata_hash,
                                        metadata_hash = ?,
                                        drift_detected_at = ?,
                                        drift_details = 'Column hash diverged from ONT_CLASS mapping after CRAWL_DOMAIN',
                                        updated_at = ?
                                    WHEN NOT MATCHED THEN INSERT (
                                        object_fqn, object_level, domain, object_state,
                                        concept_id, metadata_hash, previous_hash,
                                        drift_detected_at, drift_details, updated_at
                                    ) VALUES (
                                        ?, ?, ?, 'ONTOLOGY_DRIFT',
                                        NULL, ?, ?,
                                        ?, 'Column hash diverged from ONT_CLASS mapping after CRAWL_DOMAIN', ?
                                    )
                                """, [
                                    src_upper,
                                    new_hash, drift_ts, drift_ts,
                                    src_upper, obj_level, domain_upper,
                                    new_hash, prev_hash, drift_ts, drift_ts
                                ]).collect()
            except Exception:
                pass

    session.sql(f"""
        UPDATE KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
        SET status = 'CRAWLED',
            updated_at = ?
        WHERE domain_name = ?
    """, [crawl_ts, domain_upper]).collect()

    return f"CRAWLED: {total_tables} tables, {total_schemas} schemas, {total_databases} databases. Source: ACCOUNT_USAGE."
$$;
"""
