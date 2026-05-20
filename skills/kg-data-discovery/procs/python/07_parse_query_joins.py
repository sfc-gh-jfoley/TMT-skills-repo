import json
import re


def extract_join_pairs(sql_text: str) -> list:
    """Extract ordered table pairs that appear together in JOIN clauses."""
    sql = ' '.join(sql_text.upper().split())

    # Match FROM/JOIN <table_ref> [AS alias]
    table_pattern = re.compile(
        r'(?:FROM|JOIN)\s+'
        r'([A-Z0-9_$]+(?:\.[A-Z0-9_$]+){0,2})'
        r'(?:\s+(?:AS\s+)?[A-Z0-9_$]+)?',
        re.IGNORECASE
    )

    tables = []
    skip = {'SELECT', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'LIMIT', 'WITH', 'ON', 'SET'}
    for m in table_pattern.finditer(sql):
        tbl = m.group(1).strip()
        if tbl not in skip and not tbl.isdigit():
            tables.append(tbl)

    # Deduplicate preserving order
    seen = set()
    unique = []
    for t in tables:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    # All unordered pairs
    pairs = []
    for i in range(len(unique)):
        for j in range(i + 1, len(unique)):
            pairs.append((unique[i], unique[j]))
    return pairs


def resolve_to_concept(name: str, indexed_map: dict) -> str | None:
    """Try to match a table name string to a concept FQN in indexed_map."""
    upper = name.upper()
    # Direct FQN match
    if upper in indexed_map:
        return upper
    # Partial match by table name only — only if unambiguous
    tbl_part = upper.split('.')[-1]
    candidates = [fqn for fqn in indexed_map if fqn.split('.')[-1] == tbl_part]
    if len(candidates) == 1:
        return candidates[0]
    return None


def main(session, domain_name: str, lookback_days: int, min_occurrences: int) -> str:
    """
    Parse QUERY_HISTORY for JOIN patterns and insert/update RELATIONSHIPS
    with type=QUERY_JOIN and confidence=0.90.

    Args:
        domain_name:      Domain to operate on (e.g. 'SALESFORCE').
        lookback_days:    How far back to scan QUERY_HISTORY (default 30).
        min_occurrences:  Minimum query frequency to include a pattern (default 2).
    """
    meta_db = domain_name.upper() + '_META'

    # Collect source databases from CONCEPTS
    db_rows = session.sql(f"""
        SELECT DISTINCT UPPER(source_database) AS db
        FROM {meta_db}.META.CONCEPTS
        WHERE concept_level = 'table' AND is_active = TRUE
    """).collect()
    source_dbs = [r['DB'] for r in db_rows]

    if not source_dbs:
        return (
            f"QUERY_JOIN: No indexed tables found for {domain_name.upper()}. "
            f"Run CRAWL + ENRICH first."
        )

    # Build indexed concept map: FQN → concept_id
    indexed = session.sql(f"""
        SELECT UPPER(table_fqn) AS fqn, concept_id
        FROM {meta_db}.META.CONCEPTS
        WHERE concept_level = 'table' AND is_active = TRUE
    """).collect()
    indexed_map = {r['FQN']: r['CONCEPT_ID'] for r in indexed}

    if not indexed_map:
        return f"QUERY_JOIN: CONCEPTS table is empty for {domain_name.upper()}."

    # Pull deduplicated JOIN queries referencing source DBs
    db_filter = ' OR '.join(
        [f"UPPER(QUERY_TEXT) LIKE '%{db}%'" for db in source_dbs]
    )
    try:
        qh_rows = session.sql(f"""
            SELECT
                QUERY_PARAMETERIZED_HASH,
                ANY_VALUE(QUERY_TEXT) AS query_text,
                COUNT(*) AS occurrence_count
            FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
            WHERE EXECUTION_STATUS = 'SUCCESS'
              AND QUERY_TYPE = 'SELECT'
              AND START_TIME >= DATEADD('day', -{lookback_days}, CURRENT_TIMESTAMP())
              AND UPPER(QUERY_TEXT) REGEXP '.*\\bJOIN\\b.*'
              AND ({db_filter})
            GROUP BY QUERY_PARAMETERIZED_HASH
            HAVING occurrence_count >= {min_occurrences}
            LIMIT 5000
        """).collect()
    except Exception as e:
        return f"QUERY_JOIN: Failed to query QUERY_HISTORY: {e}"

    if not qh_rows:
        return (
            f"QUERY_JOIN: No qualifying JOIN queries found for "
            f"{domain_name.upper()} in last {lookback_days} days."
        )

    # Tally pair co-occurrences weighted by query frequency
    pair_counts: dict = {}
    for row in qh_rows:
        sql_text = row['QUERY_TEXT'] or ''
        occ = int(row['OCCURRENCE_COUNT'] or 1)
        for src_raw, tgt_raw in extract_join_pairs(sql_text):
            key = tuple(sorted([src_raw, tgt_raw]))
            pair_counts[key] = pair_counts.get(key, 0) + occ

    if not pair_counts:
        return (
            f"QUERY_JOIN: No JOIN pairs extracted from "
            f"{len(qh_rows)} queries for {domain_name.upper()}."
        )

    inserted = 0
    skipped = 0

    for (a_raw, b_raw), count in pair_counts.items():
        src_fqn = resolve_to_concept(a_raw, indexed_map)
        tgt_fqn = resolve_to_concept(b_raw, indexed_map)

        if not src_fqn or not tgt_fqn or src_fqn == tgt_fqn:
            skipped += 1
            continue

        src_concept_id = indexed_map[src_fqn]
        tgt_concept_id = indexed_map[tgt_fqn]

        # confidence: 0.90 base, up to 0.95 for very frequent pairs
        confidence = round(min(0.90 + (count / 1000) * 0.05, 0.95), 4)

        try:
            session.sql(f"""
                MERGE INTO {meta_db}.META.RELATIONSHIPS r
                USING (SELECT
                    '{src_concept_id}' AS src_id,
                    '{tgt_concept_id}' AS tgt_id
                ) s
                ON r.source_concept_id = s.src_id
                AND r.target_concept_id = s.tgt_id
                AND r.relationship_type = 'QUERY_JOIN'
                WHEN MATCHED THEN UPDATE SET
                    confidence = GREATEST(r.confidence, {confidence}),
                    is_active = TRUE
                WHEN NOT MATCHED THEN INSERT (
                    domain,
                    source_concept_id, target_concept_id,
                    source_table, source_column,
                    target_table, target_column,
                    relationship_type, confidence,
                    detection_method, is_active
                ) VALUES (
                    '{domain_name.upper()}',
                    '{src_concept_id}', '{tgt_concept_id}',
                    '{src_fqn}', 'UNKNOWN',
                    '{tgt_fqn}', 'UNKNOWN',
                    'QUERY_JOIN', {confidence},
                    'QUERY_HISTORY', TRUE
                )
            """).collect()
            inserted += 1
        except Exception:
            skipped += 1

    return (
        f"QUERY_JOIN: {domain_name.upper()} — "
        f"{inserted} join pairs upserted, {skipped} skipped "
        f"({len(qh_rows)} query patterns analyzed, "
        f"{len(pair_counts)} unique pairs found)."
    )
