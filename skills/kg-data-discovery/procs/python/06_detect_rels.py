import json
from collections import defaultdict


def get_config(session, domain_name, key):
    db = domain_name.upper() + '_META'
    rows = session.sql(
        f"SELECT config_value FROM {db}.META.DOMAIN_CONFIG WHERE config_key = ?",
        [key]
    ).collect()
    if rows and rows[0][0]:
        return json.loads(rows[0][0])
    return None


def insert_relationship(session, meta_db, domain_name, source_concept_id, target_concept_id,
                        source_table, source_column, target_table, target_column,
                        rel_type, confidence, method):
    existing = session.sql(f"""
        SELECT COUNT(*) AS cnt FROM {meta_db}.META.RELATIONSHIPS
        WHERE source_concept_id = ? AND target_concept_id = ? AND relationship_type = ?
    """, [source_concept_id, target_concept_id, rel_type]).collect()

    if existing[0]['CNT'] == 0:
        session.sql(f"""
            INSERT INTO {meta_db}.META.RELATIONSHIPS (
                domain, source_concept_id, target_concept_id,
                source_table, source_column, target_table, target_column,
                relationship_type, confidence, detection_method, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE)
        """, [domain_name.upper(), source_concept_id, target_concept_id,
              source_table, source_column, target_table, target_column,
              rel_type, confidence, method]).collect()


def main(session, domain_name: str) -> str:
    meta_db = domain_name.upper() + '_META'
    counts = {'FK': 0, 'INFERRED_FK': 0, 'SHARED_KEY': 0, 'SEMANTIC': 0, 'ONTOLOGY': 0}

    # Step 1: Declared FK constraints
    constraint_rows = session.sql(f"""
        SELECT
            rc.concept_id,
            rc.table_fqn AS source_table,
            rc.source_database,
            rc.source_schema,
            rc.source_table AS source_table_name,
            c.concept_id AS target_concept_id,
            c.table_fqn AS target_table,
            f.value:column_name::VARCHAR AS source_column,
            f.value:ref_table::VARCHAR AS ref_table_name,
            f.value:ref_columns[0]::VARCHAR AS target_column
        FROM {meta_db}.META.RAW_CONCEPTS rc,
             LATERAL FLATTEN(input => rc.constraints_json) f
        JOIN {meta_db}.META.RAW_CONCEPTS c
            ON UPPER(c.source_table) = UPPER(f.value:ref_table::VARCHAR)
            AND c.source_database = rc.source_database
        WHERE f.value:type::VARCHAR = 'FOREIGN KEY'
          AND rc.concept_level = 'table'
          AND c.concept_level = 'table'
    """).collect()

    for row in constraint_rows:
        insert_relationship(
            session, meta_db, domain_name,
            source_concept_id=row['CONCEPT_ID'],
            target_concept_id=row['TARGET_CONCEPT_ID'],
            source_table=row['SOURCE_TABLE'],
            source_column=row['SOURCE_COLUMN'] or '',
            target_table=row['TARGET_TABLE'],
            target_column=row['TARGET_COLUMN'] or '',
            rel_type='FK',
            confidence=1.0,
            method='CONSTRAINT'
        )
        counts['FK'] += 1

    # Step 2: Name-pattern inferred FKs
    all_tables = session.sql(f"""
        SELECT concept_id, table_fqn, source_table, source_schema, source_database,
               columns_json
        FROM {meta_db}.META.RAW_CONCEPTS
        WHERE concept_level = 'table' AND columns_json IS NOT NULL
    """).collect()

    table_lookup = {}
    for t in all_tables:
        table_lookup[t['SOURCE_TABLE'].upper()] = t

    for tbl in all_tables:
        cols = json.loads(tbl['COLUMNS_JSON']) if tbl['COLUMNS_JSON'] else []
        for col in cols:
            col_name = col['name'].upper()
            if col_name.endswith('_ID') and col_name != 'ID':
                candidate = col_name[:-3]

                matched = None
                if candidate in table_lookup:
                    matched = table_lookup[candidate]
                elif candidate + 'S' in table_lookup:
                    matched = table_lookup[candidate + 'S']
                elif candidate.endswith('S') and candidate[:-1] in table_lookup:
                    matched = table_lookup[candidate[:-1]]

                if matched and matched['TABLE_FQN'] != tbl['TABLE_FQN']:
                    insert_relationship(
                        session, meta_db, domain_name,
                        source_concept_id=tbl['CONCEPT_ID'],
                        target_concept_id=matched['CONCEPT_ID'],
                        source_table=tbl['TABLE_FQN'],
                        source_column=col['name'],
                        target_table=matched['TABLE_FQN'],
                        target_column='ID',
                        rel_type='INFERRED_FK',
                        confidence=0.85,
                        method='NAME_MATCH'
                    )
                    counts['INFERRED_FK'] += 1

    # Step 3: Shared key detection
    col_map = defaultdict(list)
    for tbl in all_tables:
        cols = json.loads(tbl['COLUMNS_JSON']) if tbl['COLUMNS_JSON'] else []
        for col in cols:
            key = (col['name'].upper(), col.get('type', '').upper().split('(')[0])
            if not col['name'].upper().endswith('_ID') and col['name'].upper() != 'ID':
                col_map[key].append((tbl['CONCEPT_ID'], tbl['TABLE_FQN'], col['name']))

    for (col_name, col_type), occurrences in col_map.items():
        if len(occurrences) >= 2:
            schemas = set(o[1].split('.')[1] for o in occurrences)
            if len(schemas) <= 2:
                for i in range(len(occurrences)):
                    for j in range(i + 1, len(occurrences)):
                        insert_relationship(
                            session, meta_db, domain_name,
                            source_concept_id=occurrences[i][0],
                            target_concept_id=occurrences[j][0],
                            source_table=occurrences[i][1],
                            source_column=occurrences[i][2],
                            target_table=occurrences[j][1],
                            target_column=occurrences[j][2],
                            rel_type='SHARED_KEY',
                            confidence=0.7,
                            method='NAME_MATCH'
                        )
                        counts['SHARED_KEY'] += 1

    # Step 4: Ontology hook
    ont_agent = get_config(session, domain_name, 'ontology_agent')
    ont_db = get_config(session, domain_name, 'ontology_database')
    ont_schema = get_config(session, domain_name, 'ontology_schema')

    if ont_agent and ont_db and ont_schema:
        try:
            rel_defs = session.sql(f"""
                SELECT r.name, r.description,
                       r._source_table AS source_table,
                       r._src_column AS source_column,
                       r._dst_column AS target_column,
                       r.range_class,
                       rc_src.concept_id AS source_concept_id,
                       rc_src.table_fqn AS source_table_fqn,
                       rc_tgt.concept_id AS target_concept_id,
                       rc_tgt.table_fqn AS target_table_fqn
                FROM {ont_db}.{ont_schema}.ONT_RELATION_DEF r
                JOIN {meta_db}.META.RAW_CONCEPTS rc_src
                    ON UPPER(rc_src.source_table) = UPPER(r._source_table)
                JOIN {meta_db}.META.RAW_CONCEPTS rc_tgt
                    ON UPPER(rc_tgt.source_table) = UPPER(r._dst_column)
                WHERE r._source_table IS NOT NULL AND r._src_column IS NOT NULL
            """).collect()

            for r in rel_defs:
                insert_relationship(
                    session, meta_db, domain_name,
                    source_concept_id=r['SOURCE_CONCEPT_ID'],
                    target_concept_id=r['TARGET_CONCEPT_ID'],
                    source_table=r['SOURCE_TABLE_FQN'],
                    source_column=r['SOURCE_COLUMN'] or '',
                    target_table=r['TARGET_TABLE_FQN'],
                    target_column=r['TARGET_COLUMN'] or '',
                    rel_type='ONTOLOGY',
                    confidence=1.0,
                    method='ONT_REL_DEF'
                )
                counts['ONTOLOGY'] += 1
        except Exception:
            pass

    total = sum(counts.values())
    parts = ", ".join(f"{v} {k}" for k, v in counts.items() if v > 0)
    return f"DETECTED: {total} relationships ({parts})."
