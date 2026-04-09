import json


def get_config(session, domain_name, key):
    db = domain_name.upper() + '_META'
    rows = session.sql(
        f"SELECT config_value FROM {db}.META.DOMAIN_CONFIG WHERE config_key = ?", [key]
    ).collect()
    if rows:
        val = rows[0][0]
        return json.loads(val) if val else None
    return None


def detect_column_role(col_name: str, col_type: str) -> str:
    name = col_name.upper()
    if name.endswith('_ID') or name == 'ID':
        return 'foreign_key'
    if name.endswith(('_DATE', '_AT', '_TS', '_TIME')):
        return 'dimension'
    if any(name.startswith(p) for p in ('AMOUNT', 'TOTAL_', 'SUM_', 'COUNT_', 'REVENUE', 'PRICE')):
        return 'metric'
    if any(name.endswith(s) for s in ('_AMOUNT', '_TOTAL', '_COUNT', '_REVENUE', '_PRICE')):
        return 'metric'
    if any(name.startswith(p) for p in ('IS_', 'HAS_', 'FLAG_')):
        return 'dimension'
    if name in ('STATUS', 'TYPE', 'CATEGORY', 'CODE', 'STATE', 'TIER', 'LEVEL'):
        return 'dimension'
    if name in ('NAME', 'DESCRIPTION', 'TITLE', 'LABEL'):
        return 'dimension'
    return 'attribute'


def build_tables_yaml(raw_row, description, ont_props):
    cols = json.loads(raw_row['COLUMNS_JSON']) if raw_row['COLUMNS_JSON'] else []
    prop_desc = {r['NAME']: r['DESCRIPTION'] for r in ont_props} if ont_props else {}
    col_lines = []
    for col in cols:
        role = detect_column_role(col['name'], col.get('type', ''))
        col_desc = prop_desc.get(col['name'].upper(), '')
        line = f"  - name: {col['name']}\n    type: {col.get('type', 'VARCHAR')}\n    role: {role}"
        if col_desc:
            line += f"\n    description: {col_desc}"
        col_lines.append(line)
    table_fqn = f"{raw_row['SOURCE_DATABASE']}.{raw_row['SOURCE_SCHEMA']}.{raw_row['SOURCE_TABLE']}"
    yaml_str = f"table: {table_fqn}\ndescription: {description}\ncolumns:\n" + "\n".join(col_lines)
    return yaml_str


def build_search_content(raw_row, description):
    cols = json.loads(raw_row['COLUMNS_JSON']) if raw_row['COLUMNS_JSON'] else []
    col_names = " ".join([c['name'] for c in cols])
    return (
        f"{raw_row['SOURCE_TABLE']} {raw_row['SOURCE_SCHEMA']} "
        f"{raw_row['SOURCE_DATABASE']} {description} {col_names}"
    )


def run_ontology_hook(session, domain_name, meta_db):
    ont_agent = get_config(session, domain_name, 'ontology_agent')
    if not ont_agent:
        return 0

    ont_db = get_config(session, domain_name, 'ontology_database')
    ont_schema = get_config(session, domain_name, 'ontology_schema')
    if not ont_db or not ont_schema:
        return 0

    try:
        check = session.sql(f"""
            SELECT COUNT(*) AS cnt
            FROM {ont_db}.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = '{ont_schema.upper()}' AND TABLE_NAME = 'ONT_CLASS'
        """).collect()
        if not check or check[0]['CNT'] == 0:
            return 0

        ont_class = session.sql(f"""
            SELECT _source_table, description, label
            FROM {ont_db}.{ont_schema}.ONT_CLASS
            WHERE _source_table IS NOT NULL AND description IS NOT NULL
        """).collect()

        ont_props = session.sql(f"""
            SELECT name, description
            FROM {ont_db}.{ont_schema}.ONT_SHARED_PROPERTY
            WHERE description IS NOT NULL
        """).collect()

        count = 0
        for row in ont_class:
            src_table = row['_SOURCE_TABLE']
            desc = row['DESCRIPTION']

            raw_rows = session.sql(f"""
                SELECT concept_id, source_database, source_schema, source_table, columns_json
                FROM {meta_db}.META.RAW_CONCEPTS
                WHERE source_table = ? AND concept_level = 'table'
            """, [src_table]).collect()

            for r in raw_rows:
                tables_yaml = build_tables_yaml(r, desc, ont_props)
                search_content = build_search_content(r, desc)
                session.sql(f"""
                    MERGE INTO {meta_db}.META.CONCEPTS c
                    USING (SELECT ? AS raw_id) s ON c.raw_concept_id = s.raw_id
                    WHEN MATCHED THEN UPDATE SET
                        description = ?,
                        search_content = ?,
                        tables_yaml = ?,
                        enrichment_source = 'ONT_CLASS',
                        enrichment_tier = 0,
                        enrichment_cost_usd = 0,
                        enrichment_timestamp = CURRENT_TIMESTAMP(),
                        enrichment_quality_score = 0.9,
                        updated_at = CURRENT_TIMESTAMP()
                    WHEN NOT MATCHED THEN INSERT (
                        raw_concept_id, concept_level, domain, source_database, source_schema,
                        source_table, table_fqn, description, search_content, tables_yaml,
                        enrichment_source, enrichment_tier, enrichment_cost_usd,
                        enrichment_quality_score, enrichment_timestamp, is_active, object_state
                    ) VALUES (?, 'table', ?, ?, ?, ?, ?,
                        ?, ?, ?, 'ONT_CLASS', 0, 0, 0.9, CURRENT_TIMESTAMP(), TRUE, 'KNOWN_CURRENT')
                """, [
                    r['CONCEPT_ID'],
                    desc, search_content, tables_yaml,
                    r['CONCEPT_ID'], domain_name.upper(),
                    r['SOURCE_DATABASE'], r['SOURCE_SCHEMA'], r['SOURCE_TABLE'],
                    f"{r['SOURCE_DATABASE']}.{r['SOURCE_SCHEMA']}.{r['SOURCE_TABLE']}",
                    desc, search_content, tables_yaml
                ]).collect()
                count += 1
        return count
    except Exception:
        return 0


def run_tier0(session, domain_name, meta_db):
    raw_rows = session.sql(f"""
        SELECT rc.concept_id, rc.concept_level, rc.source_database, rc.source_schema,
               rc.source_table, rc.table_fqn, rc.comment, rc.columns_json
        FROM {meta_db}.META.RAW_CONCEPTS rc
        LEFT JOIN {meta_db}.META.CONCEPTS c ON c.raw_concept_id = rc.concept_id
        WHERE c.raw_concept_id IS NULL
           OR rc.crawl_timestamp > c.enrichment_timestamp
    """).collect()

    count = 0
    for r in raw_rows:
        level = r['CONCEPT_LEVEL']
        comment = r['COMMENT'] or ''

        if level == 'table':
            cols = json.loads(r['COLUMNS_JSON']) if r['COLUMNS_JSON'] else []
            col_names = " ".join([c['name'] for c in cols])

            col_yaml_lines = []
            for col in cols:
                role = detect_column_role(col['name'], col.get('type', ''))
                col_yaml_lines.append(
                    f"  - name: {col['name']}\n    type: {col.get('type', 'VARCHAR')}\n    role: {role}"
                )

            table_fqn = r['TABLE_FQN'] or (
                f"{r['SOURCE_DATABASE']}.{r['SOURCE_SCHEMA']}.{r['SOURCE_TABLE']}"
            )
            description = comment if comment else r['SOURCE_TABLE']
            tables_yaml = (
                f"table: {table_fqn}\ndescription: {description}\ncolumns:\n"
                + "\n".join(col_yaml_lines)
            )
            search_content = (
                f"{r['SOURCE_TABLE']} {r['SOURCE_SCHEMA']} "
                f"{r['SOURCE_DATABASE']} {description} {col_names}"
            )
            quality = 0.4 if comment else 0.25

        elif level == 'schema':
            description = comment if comment else f"{r['SOURCE_SCHEMA']} schema in {r['SOURCE_DATABASE']}"
            search_content = f"{r['SOURCE_SCHEMA']} {r['SOURCE_DATABASE']} {description}"
            tables_yaml = None
            quality = 0.4 if comment else 0.25

        else:
            description = comment if comment else f"{r['SOURCE_DATABASE']} database"
            search_content = f"{r['SOURCE_DATABASE']} {description}"
            tables_yaml = None
            quality = 0.4 if comment else 0.25

        session.sql(f"""
            MERGE INTO {meta_db}.META.CONCEPTS c
            USING (SELECT ? AS raw_id) s ON c.raw_concept_id = s.raw_id
            WHEN MATCHED THEN UPDATE SET
                description = ?,
                search_content = ?,
                tables_yaml = ?,
                enrichment_source = 'HEURISTIC',
                enrichment_tier = 0,
                enrichment_cost_usd = 0,
                enrichment_timestamp = CURRENT_TIMESTAMP(),
                enrichment_quality_score = ?,
                updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                raw_concept_id, concept_level, domain, source_database, source_schema,
                source_table, table_fqn, description, search_content, tables_yaml,
                enrichment_source, enrichment_tier, enrichment_cost_usd,
                enrichment_quality_score, enrichment_timestamp, is_active, object_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, 'HEURISTIC', 0, 0, ?, CURRENT_TIMESTAMP(), TRUE, 'KNOWN_CURRENT')
        """, [
            r['CONCEPT_ID'],
            description, search_content, tables_yaml, quality,
            r['CONCEPT_ID'], level, domain_name.upper(),
            r['SOURCE_DATABASE'], r['SOURCE_SCHEMA'], r['SOURCE_TABLE'], r['TABLE_FQN'],
            description, search_content, tables_yaml, quality
        ]).collect()
        count += 1

    return count


def run_tier1(session, meta_db, domain_name):
    try:
        classify_sql = f"""
            SELECT concept_id,
                SNOWFLAKE.CORTEX.CLASSIFY_TEXT(
                    'Table: ' || source_table || ' in schema ' || source_schema ||
                    '. Columns: ' || IFNULL(description, source_table),
                    ARRAY_CONSTRUCT(
                        'fact_table', 'dimension_table', 'bridge_table', 'staging_table',
                        'reference_table', 'audit_table', 'configuration_table'
                    )
                )['label']::VARCHAR AS table_purpose
            FROM {meta_db}.META.CONCEPTS
            WHERE enrichment_source = 'HEURISTIC'
              AND enrichment_quality_score < 0.5
              AND concept_level = 'table'
            LIMIT 25
        """
        rows = session.sql(classify_sql).collect()
        count = 0
        for r in rows:
            purpose = r['TABLE_PURPOSE'] or 'unknown'
            session.sql(f"""
                UPDATE {meta_db}.META.CONCEPTS
                SET description = IFNULL(description, source_table) || ' [' || ? || ']',
                    enrichment_tier = 1,
                    enrichment_source = 'AI_CLASSIFY',
                    enrichment_quality_score = 0.6,
                    enrichment_timestamp = CURRENT_TIMESTAMP(),
                    updated_at = CURRENT_TIMESTAMP()
                WHERE concept_id = ?
            """, [purpose, r['CONCEPT_ID']]).collect()
            count += 1
        return count, 0.0
    except Exception:
        return 0, 0.0


def run_tier2(session, meta_db, domain_name):
    try:
        extract_sql = f"""
            SELECT c.concept_id,
                AI_EXTRACT(
                    'Table name: ' || c.source_table ||
                    ' Schema: ' || c.source_schema ||
                    ' Columns: ' || IFNULL(c.description, c.source_table),
                    OBJECT_CONSTRUCT(
                        'purpose', 'string',
                        'business_context', 'string',
                        'key_entities', 'string'
                    )
                ) AS extracted
            FROM {meta_db}.META.CONCEPTS c
            WHERE c.enrichment_tier < 2
              AND c.concept_level = 'table'
              AND c.enrichment_quality_score < 0.6
            LIMIT 20
        """
        rows = session.sql(extract_sql).collect()
        count = 0
        for r in rows:
            extracted = r['EXTRACTED']
            if extracted:
                try:
                    ext = json.loads(extracted) if isinstance(extracted, str) else extracted
                    purpose = ext.get('purpose', '') or ''
                    biz_ctx = ext.get('business_context', '') or ''
                    new_desc = ' '.join(filter(None, [purpose, biz_ctx])) or None
                except Exception:
                    new_desc = None

                if new_desc:
                    session.sql(f"""
                        UPDATE {meta_db}.META.CONCEPTS
                        SET description = ?,
                            enrichment_tier = 2,
                            enrichment_source = 'AI_EXTRACT',
                            enrichment_quality_score = 0.75,
                            enrichment_timestamp = CURRENT_TIMESTAMP(),
                            updated_at = CURRENT_TIMESTAMP()
                        WHERE concept_id = ?
                    """, [new_desc, r['CONCEPT_ID']]).collect()
                    count += 1
        return count, 0.0
    except Exception:
        return 0, 0.0


def run_tier3(session, meta_db, domain_name):
    try:
        complete_sql = f"""
            SELECT c.concept_id, c.source_table, c.source_schema, c.description,
                SNOWFLAKE.CORTEX.COMPLETE(
                    'claude-3-5-sonnet',
                    ARRAY_CONSTRUCT(OBJECT_CONSTRUCT(
                        'role', 'user',
                        'content', 'Write a 2-sentence business description for a Snowflake table named "' ||
                            c.source_table || '" in schema "' || c.source_schema || '". ' ||
                            'Known columns: ' || IFNULL(c.description, 'unknown') || '. ' ||
                            'Focus on what business questions this table answers.'
                    ))
                ):choices[0]:message:content::VARCHAR AS ai_description
            FROM {meta_db}.META.CONCEPTS c
            WHERE c.enrichment_tier < 3
              AND c.concept_level = 'table'
              AND c.enrichment_quality_score < 0.75
            LIMIT 10
        """
        rows = session.sql(complete_sql).collect()
        count = 0
        cost = 0.0
        for r in rows:
            ai_desc = r['AI_DESCRIPTION']
            if ai_desc:
                session.sql(f"""
                    UPDATE {meta_db}.META.CONCEPTS
                    SET description = ?,
                        enrichment_tier = 3,
                        enrichment_source = 'AI_COMPLETE',
                        enrichment_quality_score = 0.85,
                        enrichment_cost_usd = enrichment_cost_usd + 0.001,
                        enrichment_timestamp = CURRENT_TIMESTAMP(),
                        updated_at = CURRENT_TIMESTAMP()
                    WHERE concept_id = ?
                """, [ai_desc, r['CONCEPT_ID']]).collect()
                count += 1
                cost += 0.001
        return count, cost
    except Exception:
        return 0, 0.0


def main(session, domain_name: str, max_tier: int) -> str:
    meta_db = domain_name.upper() + '_META'

    ont_count = run_ontology_hook(session, domain_name, meta_db)

    t0 = run_tier0(session, domain_name, meta_db)

    t1, cost1 = 0, 0.0
    if max_tier >= 1:
        t1, cost1 = run_tier1(session, meta_db, domain_name)

    t2, cost2 = 0, 0.0
    if max_tier >= 2:
        t2, cost2 = run_tier2(session, meta_db, domain_name)

    t3, cost3 = 0, 0.0
    if max_tier >= 3:
        t3, cost3 = run_tier3(session, meta_db, domain_name)

    total_cost = cost1 + cost2 + cost3
    total = t0 + t1 + t2 + t3 + ont_count

    session.sql(f"""
        UPDATE KG_CONTROL.PUBLIC.DOMAIN_REGISTRY
        SET status = 'ENRICHED', updated_at = CURRENT_TIMESTAMP()
        WHERE domain_name = ?
    """, [domain_name.upper()]).collect()

    return (
        f"ENRICHED: {domain_name.upper()} \u2014 {total} concepts. "
        f"Tiers: 0={t0}, 1={t1}, 2={t2}, 3={t3}. "
        f"Est. cost: ${total_cost:.4f}."
    )
