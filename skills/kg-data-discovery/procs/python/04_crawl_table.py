CRAWL_TABLE_DDL = """
CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.CRAWL_TABLE(
    domain_name VARCHAR,
    table_fqn VARCHAR
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


def compute_hash(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def crawl_single_table(session: Session, domain_upper: str, meta_db: str,
                        db_name: str, schema_name: str, table_name: str,
                        crawl_ts: str) -> dict:
    cols = session.sql(f"""
        SELECT column_name, data_type, is_nullable, column_default, comment, ordinal_position
        FROM {db_name}.INFORMATION_SCHEMA.COLUMNS
        WHERE table_schema = ? AND table_name = ?
        ORDER BY ordinal_position
    """, [schema_name, table_name]).collect()

    constraints = session.sql(f"""
        SELECT kcu.constraint_name, tc.constraint_type, kcu.column_name
        FROM {db_name}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
        JOIN {db_name}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
          ON kcu.constraint_name = tc.constraint_name
         AND kcu.table_schema = tc.table_schema
         AND kcu.table_name = tc.table_name
        WHERE kcu.table_schema = ? AND kcu.table_name = ?
    """, [schema_name, table_name]).collect()

    table_meta_rows = session.sql(f"""
        SELECT table_type, row_count, bytes, clustering_key, comment,
               created, last_altered, table_owner
        FROM {db_name}.INFORMATION_SCHEMA.TABLES
        WHERE table_schema = ? AND table_name = ?
    """, [schema_name, table_name]).collect()

    columns_json_list = []
    for c in cols:
        columns_json_list.append({
            'name': c['COLUMN_NAME'],
            'type': c['DATA_TYPE'],
            'nullable': c['IS_NULLABLE'],
            'comment': c['COMMENT'],
            'ordinal': c['ORDINAL_POSITION']
        })

    constraints_by_name = {}
    for cn in constraints:
        cname = cn['CONSTRAINT_NAME']
        if cname not in constraints_by_name:
            constraints_by_name[cname] = {
                'name': cname,
                'type': cn['CONSTRAINT_TYPE'],
                'columns': [],
                'ref_table': None,
                'ref_cols': []
            }
        constraints_by_name[cname]['columns'].append(cn['COLUMN_NAME'])
    constraints_json_list = list(constraints_by_name.values())

    sample_values = {}
    string_types = {'TEXT', 'VARCHAR', 'STRING', 'CHAR', 'CHARACTER', 'NCHAR', 'NVARCHAR', 'NVARCHAR2'}
    table_fqn_full = f"{db_name}.{schema_name}.{table_name}"
    for c in cols:
        if c['DATA_TYPE'].upper() in string_types:
            try:
                samples = session.sql(f"""
                    SELECT DISTINCT {c['COLUMN_NAME']}
                    FROM {table_fqn_full}
                    WHERE {c['COLUMN_NAME']} IS NOT NULL
                    LIMIT 20
                """).collect()
                vals = [r[0] for r in samples if r[0] is not None]
                if vals:
                    sample_values[c['COLUMN_NAME']] = vals
            except Exception:
                pass

    columns_json_str = json.dumps(columns_json_list, default=str)
    constraints_json_str = json.dumps(constraints_json_list, default=str)
    sample_values_json_str = json.dumps(sample_values, default=str) if sample_values else None
    meta_hash = compute_hash(columns_json_str)

    table_type = None
    row_count = None
    bytes_val = None
    clustering_key = None
    comment_val = None
    created_at_src = None
    last_altered_src = None
    owner = None
    if table_meta_rows:
        tm = table_meta_rows[0]
        table_type = tm['TABLE_TYPE']
        row_count = tm['ROW_COUNT']
        bytes_val = tm['BYTES']
        clustering_key = tm['CLUSTERING_KEY']
        comment_val = tm['COMMENT']
        created_at_src = str(tm['CREATED']) if tm['CREATED'] else None
        last_altered_src = str(tm['LAST_ALTERED']) if tm['LAST_ALTERED'] else None
        owner = tm['TABLE_OWNER']

    return {
        'concept_id': str(uuid.uuid4()),
        'concept_level': 'table',
        'domain': domain_upper,
        'source_database': db_name,
        'source_schema': schema_name,
        'source_table': table_name,
        'table_fqn': table_fqn_full,
        'table_type': table_type,
        'row_count': row_count,
        'bytes': bytes_val,
        'clustering_key': clustering_key,
        'comment': comment_val,
        'created_at_src': created_at_src,
        'last_altered_src': last_altered_src,
        'owner': owner,
        'is_transient': False,
        'is_managed_access': False,
        'is_active': True,
        'columns_json': columns_json_str,
        'constraints_json': constraints_json_str,
        'sample_values_json': sample_values_json_str,
        'crawl_source': 'INFORMATION_SCHEMA',
        'crawl_timestamp': crawl_ts,
        'metadata_hash': meta_hash,
        'col_count': len(columns_json_list),
        'constraint_count': len(constraints_json_list)
    }


def upsert_raw_concept(session: Session, target: str, row: dict) -> None:
    existing = session.sql(f"""
        SELECT concept_id
        FROM {target}
        WHERE concept_level = 'table'
          AND source_database = ?
          AND COALESCE(source_schema, '') = COALESCE(?, '')
          AND COALESCE(source_table, '') = COALESCE(?, '')
    """, [row['source_database'], row['source_schema'] or '', row['source_table'] or '']).collect()

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
                is_active = ?,
                columns_json = PARSE_JSON(?),
                constraints_json = PARSE_JSON(?),
                sample_values_json = PARSE_JSON(?),
                crawl_source = ?,
                crawl_timestamp = ?,
                metadata_hash = ?
            WHERE concept_id = ?
        """, [
            row['table_type'], row['row_count'], row['bytes'],
            row['clustering_key'], row['comment'],
            row['created_at_src'], row['last_altered_src'],
            row['owner'], row['is_active'],
            row['columns_json'], row['constraints_json'], row['sample_values_json'],
            row['crawl_source'], row['crawl_timestamp'], row['metadata_hash'],
            existing_id
        ]).collect()


def main(session: Session, domain_name: str, table_fqn: str) -> str:
    domain_upper = domain_name.upper()
    meta_db = domain_upper + '_META'
    target = f"{meta_db}.META.RAW_CONCEPTS"
    crawl_ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    parts = table_fqn.upper().split('.')
    if len(parts) != 3:
        return f"ERROR: table_fqn must be DB.SCHEMA.TABLE, got: {table_fqn}"
    db_name, schema_name, table_name = parts[0], parts[1], parts[2]

    row = crawl_single_table(session, domain_upper, meta_db, db_name, schema_name, table_name, crawl_ts)
    upsert_raw_concept(session, target, row)

    return (f"CRAWLED: {db_name}.{schema_name}.{table_name} — "
            f"{row['col_count']} columns, {row['constraint_count']} constraints. "
            f"Source: INFORMATION_SCHEMA.")
$$;
"""


CRAWL_SCHEMA_DDL = """
CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.CRAWL_SCHEMA(
    domain_name VARCHAR,
    schema_fqn VARCHAR
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


def compute_hash(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def crawl_single_table(session: Session, domain_upper: str,
                        db_name: str, schema_name: str, table_name: str,
                        crawl_ts: str) -> dict:
    cols = session.sql(f"""
        SELECT column_name, data_type, is_nullable, column_default, comment, ordinal_position
        FROM {db_name}.INFORMATION_SCHEMA.COLUMNS
        WHERE table_schema = ? AND table_name = ?
        ORDER BY ordinal_position
    """, [schema_name, table_name]).collect()

    constraints = session.sql(f"""
        SELECT kcu.constraint_name, tc.constraint_type, kcu.column_name
        FROM {db_name}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
        JOIN {db_name}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
          ON kcu.constraint_name = tc.constraint_name
         AND kcu.table_schema = tc.table_schema
         AND kcu.table_name = tc.table_name
        WHERE kcu.table_schema = ? AND kcu.table_name = ?
    """, [schema_name, table_name]).collect()

    table_meta_rows = session.sql(f"""
        SELECT table_type, row_count, bytes, clustering_key, comment,
               created, last_altered, table_owner
        FROM {db_name}.INFORMATION_SCHEMA.TABLES
        WHERE table_schema = ? AND table_name = ?
    """, [schema_name, table_name]).collect()

    columns_json_list = []
    for c in cols:
        columns_json_list.append({
            'name': c['COLUMN_NAME'],
            'type': c['DATA_TYPE'],
            'nullable': c['IS_NULLABLE'],
            'comment': c['COMMENT'],
            'ordinal': c['ORDINAL_POSITION']
        })

    constraints_by_name = {}
    for cn in constraints:
        cname = cn['CONSTRAINT_NAME']
        if cname not in constraints_by_name:
            constraints_by_name[cname] = {
                'name': cname,
                'type': cn['CONSTRAINT_TYPE'],
                'columns': [],
                'ref_table': None,
                'ref_cols': []
            }
        constraints_by_name[cname]['columns'].append(cn['COLUMN_NAME'])
    constraints_json_list = list(constraints_by_name.values())

    sample_values = {}
    string_types = {'TEXT', 'VARCHAR', 'STRING', 'CHAR', 'CHARACTER', 'NCHAR', 'NVARCHAR', 'NVARCHAR2'}
    table_fqn_full = f"{db_name}.{schema_name}.{table_name}"
    for c in cols:
        if c['DATA_TYPE'].upper() in string_types:
            try:
                samples = session.sql(f"""
                    SELECT DISTINCT {c['COLUMN_NAME']}
                    FROM {table_fqn_full}
                    WHERE {c['COLUMN_NAME']} IS NOT NULL
                    LIMIT 20
                """).collect()
                vals = [r[0] for r in samples if r[0] is not None]
                if vals:
                    sample_values[c['COLUMN_NAME']] = vals
            except Exception:
                pass

    columns_json_str = json.dumps(columns_json_list, default=str)
    constraints_json_str = json.dumps(constraints_json_list, default=str)
    sample_values_json_str = json.dumps(sample_values, default=str) if sample_values else None
    meta_hash = compute_hash(columns_json_str)

    table_type = None
    row_count = None
    bytes_val = None
    clustering_key = None
    comment_val = None
    created_at_src = None
    last_altered_src = None
    owner = None
    if table_meta_rows:
        tm = table_meta_rows[0]
        table_type = tm['TABLE_TYPE']
        row_count = tm['ROW_COUNT']
        bytes_val = tm['BYTES']
        clustering_key = tm['CLUSTERING_KEY']
        comment_val = tm['COMMENT']
        created_at_src = str(tm['CREATED']) if tm['CREATED'] else None
        last_altered_src = str(tm['LAST_ALTERED']) if tm['LAST_ALTERED'] else None
        owner = tm['TABLE_OWNER']

    return {
        'concept_id': str(uuid.uuid4()),
        'concept_level': 'table',
        'domain': domain_upper,
        'source_database': db_name,
        'source_schema': schema_name,
        'source_table': table_name,
        'table_fqn': table_fqn_full,
        'table_type': table_type,
        'row_count': row_count,
        'bytes': bytes_val,
        'clustering_key': clustering_key,
        'comment': comment_val,
        'created_at_src': created_at_src,
        'last_altered_src': last_altered_src,
        'owner': owner,
        'is_transient': False,
        'is_managed_access': False,
        'is_active': True,
        'columns_json': columns_json_str,
        'constraints_json': constraints_json_str,
        'sample_values_json': sample_values_json_str,
        'crawl_source': 'INFORMATION_SCHEMA',
        'crawl_timestamp': crawl_ts,
        'metadata_hash': meta_hash,
        'col_count': len(columns_json_list)
    }


def upsert_raw_concept(session: Session, target: str, row: dict) -> None:
    existing = session.sql(f"""
        SELECT concept_id
        FROM {target}
        WHERE concept_level = 'table'
          AND source_database = ?
          AND COALESCE(source_schema, '') = COALESCE(?, '')
          AND COALESCE(source_table, '') = COALESCE(?, '')
    """, [row['source_database'], row['source_schema'] or '', row['source_table'] or '']).collect()

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
                is_active = ?,
                columns_json = PARSE_JSON(?),
                constraints_json = PARSE_JSON(?),
                sample_values_json = PARSE_JSON(?),
                crawl_source = ?,
                crawl_timestamp = ?,
                metadata_hash = ?
            WHERE concept_id = ?
        """, [
            row['table_type'], row['row_count'], row['bytes'],
            row['clustering_key'], row['comment'],
            row['created_at_src'], row['last_altered_src'],
            row['owner'], row['is_active'],
            row['columns_json'], row['constraints_json'], row['sample_values_json'],
            row['crawl_source'], row['crawl_timestamp'], row['metadata_hash'],
            existing_id
        ]).collect()


def main(session: Session, domain_name: str, schema_fqn: str) -> str:
    domain_upper = domain_name.upper()
    meta_db = domain_upper + '_META'
    target = f"{meta_db}.META.RAW_CONCEPTS"
    crawl_ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    parts = schema_fqn.upper().split('.')
    if len(parts) != 2:
        return f"ERROR: schema_fqn must be DB.SCHEMA, got: {schema_fqn}"
    db_name, schema_name = parts[0], parts[1]

    table_list = session.sql(f"""
        SELECT table_name
        FROM {db_name}.INFORMATION_SCHEMA.TABLES
        WHERE table_schema = ?
          AND table_type IN ('BASE TABLE', 'VIEW', 'EXTERNAL TABLE')
        ORDER BY table_name
    """, [schema_name]).collect()

    total_tables = 0
    total_cols = 0

    for t in table_list:
        table_name = t['TABLE_NAME'].upper()
        try:
            row = crawl_single_table(session, domain_upper, db_name, schema_name, table_name, crawl_ts)
            upsert_raw_concept(session, target, row)
            total_tables += 1
            total_cols += row['col_count']
        except Exception:
            pass

    return (f"CRAWLED: {db_name}.{schema_name} — "
            f"{total_tables} tables, {total_cols} columns. "
            f"Source: INFORMATION_SCHEMA.")
$$;
"""
