ONBOARD_WIZARD_DDL = """
CREATE OR REPLACE PROCEDURE KG_CONTROL.PUBLIC.ONBOARD_WIZARD(
    action VARCHAR,
    step   NUMBER
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'main'
AS
$$
import json
from datetime import datetime, timezone
from snowflake.snowpark import Session

SESSION_ID = 'WIZARD_CURRENT'


def call_proc(session: Session, proc_call: str):
    try:
        rows = session.sql(proc_call).collect()
        return rows[0][0] if rows else 'ok'
    except Exception as e:
        return f'ERROR: {str(e)}'


def load_wizard_state(session: Session):
    try:
        rows = session.sql(f"""
            SELECT current_step, domain_name, status, step_results
            FROM KG_CONTROL.PUBLIC.WIZARD_STATE
            WHERE session_id = '{SESSION_ID}'
            LIMIT 1
        """).collect()
        if rows:
            raw = rows[0]['STEP_RESULTS']
            if raw is None:
                results = {}
            elif isinstance(raw, (dict, list)):
                results = raw
            else:
                try:
                    results = json.loads(raw)
                except Exception:
                    results = {}
            return {
                'current_step': rows[0]['CURRENT_STEP'],
                'domain_name':  rows[0]['DOMAIN_NAME'],
                'status':       rows[0]['STATUS'],
                'step_results': results,
            }
    except Exception:
        pass
    return None


def save_wizard_state(session: Session, step: int, domain_name, step_results: dict,
                      status: str = 'IN_PROGRESS'):
    results_json = json.dumps(step_results)
    completed_clause = ', completed_at = CURRENT_TIMESTAMP()' if status == 'COMPLETE' else ''
    session.sql(f"""
        MERGE INTO KG_CONTROL.PUBLIC.WIZARD_STATE t
        USING (SELECT 1 AS dummy) s ON t.session_id = '{SESSION_ID}'
        WHEN MATCHED THEN UPDATE SET
            current_step = ?,
            domain_name  = ?,
            step_results = PARSE_JSON(?),
            status       = ?,
            updated_at   = CURRENT_TIMESTAMP(){completed_clause}
        WHEN NOT MATCHED THEN INSERT (
            session_id, current_step, domain_name, step_results, status
        ) VALUES (
            '{SESSION_ID}', ?, ?, PARSE_JSON(?), ?
        )
    """, [step, domain_name, results_json, status,
          step, domain_name, results_json, status]).collect()


def init_wizard(session: Session):
    session.sql(f"DELETE FROM KG_CONTROL.PUBLIC.WIZARD_STATE WHERE session_id = '{SESSION_ID}'").collect()
    save_wizard_state(session, 0, None, {}, 'IN_PROGRESS')


def reset_wizard(session: Session):
    session.sql('DELETE FROM KG_CONTROL.PUBLIC.WIZARD_STATE').collect()


def build_status_response(session: Session, state):
    if not state:
        return {
            'status':  'NOT_STARTED',
            'message': "No wizard session found. Call ONBOARD_WIZARD('START', NULL) to begin.",
            'step':    -1,
        }
    step    = state.get('current_step', 0)
    domain  = state.get('domain_name')
    results = state.get('step_results', {})
    completed = [k for k, v in results.items() if isinstance(v, dict) and v.get('status') == 'COMPLETE']
    return {
        'session_id':      SESSION_ID,
        'current_step':    step,
        'domain_name':     domain,
        'wizard_status':   state.get('status', 'IN_PROGRESS'),
        'completed_steps': completed,
        'message':         f'Step {step}/9 in progress. Domain: {domain or "not yet chosen"}.',
        'next_hint':       f"Call ONBOARD_WIZARD('NEXT', {step}) to continue.",
    }


def execute_step(session: Session, step_num: int, state):
    state        = state or {}
    domain       = state.get('domain_name')
    step_results = state.get('step_results', {})

    # ------------------------------------------------------------------
    # Step 0: Welcome + prerequisites check
    # ------------------------------------------------------------------
    if step_num == 0:
        checks = []

        try:
            rows  = session.sql('SELECT CURRENT_WAREHOUSE()').collect()
            wh    = rows[0][0] if rows else None
            wh_ok = bool(wh)
            checks.append({'check': 'warehouse', 'ok': wh_ok,
                           'value': wh or 'NONE — use USE WAREHOUSE <name> before proceeding'})
        except Exception as e:
            checks.append({'check': 'warehouse', 'ok': False, 'value': str(e)})

        try:
            rows    = session.sql('SELECT CURRENT_ROLE()').collect()
            role    = rows[0][0] if rows else None
            role_ok = bool(role)
            checks.append({'check': 'role', 'ok': role_ok, 'value': role or 'unknown'})
        except Exception as e:
            checks.append({'check': 'role', 'ok': False, 'value': str(e)})

        try:
            session.sql('SELECT COUNT(*) FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES LIMIT 1').collect()
            checks.append({'check': 'ACCOUNT_USAGE_access', 'ok': True, 'value': 'accessible'})
        except Exception as e:
            checks.append({'check': 'ACCOUNT_USAGE_access', 'ok': False,
                           'value': f'ERROR: {str(e)} — grant IMPORTED PRIVILEGES on SNOWFLAKE to your role'})

        all_ok = all(c['ok'] for c in checks)
        step_results['step_0'] = {
            'status': 'COMPLETE' if all_ok else 'WARNING',
            'ts':     datetime.now(timezone.utc).isoformat(),
        }
        save_wizard_state(session, 0, domain, step_results, 'IN_PROGRESS')

        check_lines = '\n'.join(
            f"  {'OK  ' if c['ok'] else 'FAIL'}: {c['check']} = {c['value']}"
            for c in checks
        )
        return {
            'step':   0,
            'title':  'Welcome to KG Data Discovery',
            'status': 'COMPLETE' if all_ok else 'WARNING',
            'message': (
                'KG Data Discovery builds a knowledge graph of your Snowflake data by:\n'
                '  1. Crawling schemas via ACCOUNT_USAGE (bulk) or INFORMATION_SCHEMA (targeted)\n'
                '  2. Enriching table/column metadata with AI (optional, configurable tier 0–3)\n'
                '  3. Detecting relationships via FK constraints and naming patterns\n'
                '  4. Creating a Cortex Search Service for natural language data discovery\n\n'
                'Prerequisites:\n'
                '  — ACCOUNT_USAGE access (IMPORTED PRIVILEGES ON SNOWFLAKE granted to your role)\n'
                '  — SYSADMIN or CREATE DATABASE + CREATE SCHEMA privilege\n'
                '  — CORTEX_USER role (for AI enrichment, tiers 1–3 only)\n'
                '  — An active warehouse\n\n'
                'Prerequisite checks:\n' + check_lines
            ),
            'prereq_checks': checks,
            'all_prereqs_met': all_ok,
            'result': {'checks': checks},
            'next_hint': (
                "Call ONBOARD_WIZARD('NEXT', 0) to discover candidate domains."
                if all_ok else
                "Fix the FAIL items above, then call ONBOARD_WIZARD('NEXT', 0)."
            ),
            'prev_hint': None,
        }

    # ------------------------------------------------------------------
    # Step 1: Discover domains
    # ------------------------------------------------------------------
    elif step_num == 1:
        domains = []
        error   = None
        try:
            session.sql("CALL KG_CONTROL.PUBLIC.DISCOVER_DOMAINS('SHALLOW', 7)").collect()
            rows = session.sql('SELECT * FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) LIMIT 10').collect()
            for r in rows:
                domains.append({
                    'domain_name':          r[0]  or '',
                    'source_databases':     r[1]  or '',
                    'table_count':          r[2]  or 0,
                    'schema_count':         r[3]  or 0,
                    'query_volume':         r[4]  or 0,
                    'distinct_users':       r[5]  or 0,
                    'priority_tier':        r[8]  or '',
                    'graduation_candidate': bool(r[9]) if r[9] is not None else False,
                    'recommendation':       r[10] or '',
                })
        except Exception as e:
            error = str(e)

        top5 = domains[:5]
        step_results['step_1'] = {
            'status':       'COMPLETE' if not error else 'ERROR',
            'domains_found': len(domains),
            'ts':           datetime.now(timezone.utc).isoformat(),
        }
        save_wizard_state(session, 1, domain, step_results, 'IN_PROGRESS')

        domain_lines = '\n'.join(
            f"  {i+1}. {d['domain_name']:<20} tables={d['table_count']:<5} "
            f"tier={d['priority_tier']:<10} grad={d['graduation_candidate']}"
            for i, d in enumerate(top5)
        ) if top5 else '  (none found — verify ACCOUNT_USAGE access)'

        return {
            'step':   1,
            'title':  'Discover Domains',
            'status': 'COMPLETE' if not error else 'ERROR',
            'message': f'Found {len(domains)} candidate domain(s). Top 5:\n{domain_lines}',
            'result': {'domains': top5, 'total_found': len(domains), 'error': error},
            'next_hint': (
                'Choose a domain from the list above.\n'
                'Set it in wizard state, then call NEXT:\n\n'
                "  UPDATE KG_CONTROL.PUBLIC.WIZARD_STATE\n"
                "    SET domain_name = 'YOUR_DOMAIN_NAME'\n"
                "  WHERE session_id = 'WIZARD_CURRENT';\n\n"
                "  CALL KG_CONTROL.PUBLIC.ONBOARD_WIZARD('NEXT', 1);"
            ),
            'prev_hint': "Call ONBOARD_WIZARD('PREV', 0) to revisit prerequisites.",
        }

    # ------------------------------------------------------------------
    # Step 2: Choose domain + BOOTSTRAP_KG_META
    # ------------------------------------------------------------------
    elif step_num == 2:
        if not domain:
            step_results['step_2'] = {'status': 'AWAITING_INPUT', 'ts': datetime.now(timezone.utc).isoformat()}
            save_wizard_state(session, 2, domain, step_results, 'IN_PROGRESS')
            return {
                'step':   2,
                'title':  'Choose Domain',
                'status': 'AWAITING_INPUT',
                'message': (
                    'No domain name set in wizard state.\n'
                    'Update the state with your chosen domain, then call NEXT again:\n\n'
                    "  UPDATE KG_CONTROL.PUBLIC.WIZARD_STATE\n"
                    "    SET domain_name = 'YOUR_DOMAIN_NAME'\n"
                    "  WHERE session_id = 'WIZARD_CURRENT';\n\n"
                    "  CALL KG_CONTROL.PUBLIC.ONBOARD_WIZARD('NEXT', 2);\n\n"
                    "  Example: SET domain_name = 'FINANCE'\n"
                    "  This creates FINANCE_META database with all KG tables."
                ),
                'result': {},
                'next_hint': "Set domain_name in WIZARD_STATE, then call ONBOARD_WIZARD('NEXT', 2).",
                'prev_hint': "Call ONBOARD_WIZARD('PREV', 1) to review discovered domains.",
            }

        domain_upper       = domain.upper()
        already_registered = False
        try:
            reg = session.sql(
                'SELECT domain_name FROM KG_CONTROL.PUBLIC.DOMAIN_REGISTRY WHERE domain_name = ?',
                [domain_upper]
            ).collect()
            already_registered = len(reg) > 0
        except Exception:
            pass

        if already_registered:
            bootstrap_result = f'SKIPPED: {domain_upper} already registered in DOMAIN_REGISTRY.'
        else:
            bootstrap_result = call_proc(session, f"CALL KG_CONTROL.PUBLIC.BOOTSTRAP_KG_META('{domain_upper}')")

        is_error = isinstance(bootstrap_result, str) and bootstrap_result.startswith('ERROR:')
        step_results['step_2'] = {
            'status':    'ERROR' if is_error else 'COMPLETE',
            'domain':    domain_upper,
            'bootstrap': bootstrap_result,
            'ts':        datetime.now(timezone.utc).isoformat(),
        }
        save_wizard_state(session, 2, domain_upper, step_results, 'IN_PROGRESS')

        return {
            'step':   2,
            'title':  'Choose Domain',
            'status': 'ERROR' if is_error else 'COMPLETE',
            'message': (
                f'Domain:                {domain_upper}\n'
                f'BOOTSTRAP_KG_META:     {bootstrap_result}\n'
                f'Already registered:   {already_registered}'
            ),
            'result': {
                'domain':              domain_upper,
                'bootstrap_result':    bootstrap_result,
                'already_registered':  already_registered,
            },
            'next_hint': f"Call ONBOARD_WIZARD('NEXT', 2) to configure source databases for {domain_upper}.",
            'prev_hint': "Call ONBOARD_WIZARD('PREV', 1) to go back to domain discovery.",
        }

    # ------------------------------------------------------------------
    # Step 3: Configure domain (source_databases + CONFIGURE_DOMAIN)
    # ------------------------------------------------------------------
    elif step_num == 3:
        if not domain:
            return {
                'step': 3, 'title': 'Configure Domain', 'status': 'ERROR',
                'message': 'No domain set. Go back to step 2.', 'result': {},
            }

        domain_upper = domain.upper()
        meta_db      = domain_upper + '_META'

        src_dbs_raw = None
        try:
            cfg = session.sql(
                f"SELECT config_value FROM {meta_db}.META.DOMAIN_CONFIG WHERE config_key = 'source_databases'"
            ).collect()
            if cfg:
                raw = cfg[0][0]
                if isinstance(raw, list):
                    src_dbs_raw = raw
                else:
                    try:
                        src_dbs_raw = json.loads(raw) if raw else []
                    except Exception:
                        src_dbs_raw = []
        except Exception:
            src_dbs_raw = []

        if not src_dbs_raw:
            available_dbs = []
            try:
                rows = session.sql(f"""
                    SELECT database_name
                    FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES
                    WHERE database_name NOT IN ('SNOWFLAKE', 'SNOWFLAKE_SAMPLE_DATA',
                                                'KG_CONTROL', '{meta_db}')
                      AND deleted IS NULL
                    ORDER BY database_name
                    LIMIT 20
                """).collect()
                available_dbs = [r[0] for r in rows]
            except Exception:
                pass

            step_results['step_3'] = {'status': 'AWAITING_INPUT', 'ts': datetime.now(timezone.utc).isoformat()}
            save_wizard_state(session, 3, domain_upper, step_results, 'IN_PROGRESS')

            db_list_example = ', '.join(f"'{d}'" for d in available_dbs[:5]) if available_dbs else "'YOUR_DB'"
            return {
                'step':   3,
                'title':  'Configure Domain',
                'status': 'AWAITING_INPUT',
                'message': (
                    f'Configure source databases for domain {domain_upper}.\n\n'
                    f'Available databases (sample): {", ".join(available_dbs[:10]) if available_dbs else "see SNOWFLAKE.ACCOUNT_USAGE.DATABASES"}\n\n'
                    f'Run CONFIGURE_DOMAIN with your chosen databases:\n\n'
                    f"  CALL KG_CONTROL.PUBLIC.CONFIGURE_DOMAIN(\n"
                    f"    '{domain_upper}',\n"
                    f"    ARRAY_CONSTRUCT({db_list_example}),\n"
                    f"    NULL\n"
                    f"  );\n\n"
                    f"  Then call ONBOARD_WIZARD('NEXT', 3).\n\n"
                    f"  Optional config_overrides: PARSE_JSON('{{\"enrichment_max_tier\": 2}}')"
                ),
                'result': {'available_databases': available_dbs},
                'next_hint': (
                    f"Call CONFIGURE_DOMAIN('{domain_upper}', ARRAY_CONSTRUCT(...), NULL), "
                    "then ONBOARD_WIZARD('NEXT', 3)."
                ),
                'prev_hint': "Call ONBOARD_WIZARD('PREV', 2) to go back.",
            }

        db_array = ', '.join(f"'{d}'" for d in src_dbs_raw)
        configure_result = call_proc(
            session,
            f"CALL KG_CONTROL.PUBLIC.CONFIGURE_DOMAIN('{domain_upper}', ARRAY_CONSTRUCT({db_array}), NULL)"
        )
        is_error = isinstance(configure_result, str) and configure_result.startswith('ERROR:')
        step_results['step_3'] = {
            'status':           'ERROR' if is_error else 'COMPLETE',
            'configure_result': configure_result,
            'source_databases': src_dbs_raw,
            'ts':               datetime.now(timezone.utc).isoformat(),
        }
        save_wizard_state(session, 3, domain_upper, step_results, 'IN_PROGRESS')

        return {
            'step':   3,
            'title':  'Configure Domain',
            'status': 'ERROR' if is_error else 'COMPLETE',
            'message': (
                f'CONFIGURE_DOMAIN result: {configure_result}\n'
                f'Source databases: {src_dbs_raw}'
            ),
            'result': {'configure_result': configure_result, 'source_databases': src_dbs_raw},
            'next_hint': f"Call ONBOARD_WIZARD('NEXT', 3) to crawl {domain_upper} (full crawl from ACCOUNT_USAGE).",
            'prev_hint': "Call ONBOARD_WIZARD('PREV', 2) to go back.",
        }

    # ------------------------------------------------------------------
    # Step 4: Crawl domain (FULL)
    # ------------------------------------------------------------------
    elif step_num == 4:
        if not domain:
            return {
                'step': 4, 'title': 'Crawl Domain', 'status': 'ERROR',
                'message': 'No domain set. Go back to step 2.', 'result': {},
            }

        domain_upper = domain.upper()
        meta_db      = domain_upper + '_META'

        crawl_result = call_proc(session, f"CALL KG_CONTROL.PUBLIC.CRAWL_DOMAIN('{domain_upper}', 'FULL')")

        table_count  = 0
        schema_count = 0
        try:
            stats = session.sql(f"""
                SELECT concept_level, COUNT(*) AS cnt
                FROM {meta_db}.META.RAW_CONCEPTS
                GROUP BY concept_level
            """).collect()
            for r in stats:
                if r[0] == 'table':
                    table_count = r[1]
                elif r[0] == 'schema':
                    schema_count = r[1]
        except Exception:
            pass

        is_error = isinstance(crawl_result, str) and crawl_result.startswith('ERROR:')
        step_results['step_4'] = {
            'status':       'ERROR' if is_error else 'COMPLETE',
            'crawl_result': crawl_result,
            'table_count':  table_count,
            'schema_count': schema_count,
            'ts':           datetime.now(timezone.utc).isoformat(),
        }
        save_wizard_state(session, 4, domain_upper, step_results, 'IN_PROGRESS')

        return {
            'step':   4,
            'title':  'Crawl Domain',
            'status': 'ERROR' if is_error else 'COMPLETE',
            'message': (
                f'CRAWL_DOMAIN(FULL) result: {crawl_result}\n'
                f'RAW_CONCEPTS — tables: {table_count}, schemas: {schema_count}'
            ),
            'result': {
                'crawl_result':  crawl_result,
                'table_count':   table_count,
                'schema_count':  schema_count,
            },
            'next_hint': f"Call ONBOARD_WIZARD('NEXT', 4) to enrich {domain_upper} (you will choose enrichment tier).",
            'prev_hint': "Call ONBOARD_WIZARD('PREV', 3) to go back to configuration.",
        }

    # ------------------------------------------------------------------
    # Step 5: Enrich domain
    # ------------------------------------------------------------------
    elif step_num == 5:
        if not domain:
            return {
                'step': 5, 'title': 'Enrich Domain', 'status': 'ERROR',
                'message': 'No domain set. Go back to step 2.', 'result': {},
            }

        domain_upper = domain.upper()
        meta_db      = domain_upper + '_META'
        tier_raw     = step_results.get('step_5_tier')

        if tier_raw is None:
            step_results['step_5'] = {'status': 'AWAITING_INPUT', 'ts': datetime.now(timezone.utc).isoformat()}
            save_wizard_state(session, 5, domain_upper, step_results, 'IN_PROGRESS')
            return {
                'step':   5,
                'title':  'Enrich Domain',
                'status': 'AWAITING_INPUT',
                'message': (
                    'Choose an enrichment tier (0–3):\n\n'
                    '  0 = FREE      — heuristics only, zero AI cost, always available\n'
                    '  1 = CLASSIFY  — AI_CLASSIFY for ambiguous column roles (~$0.001/table)\n'
                    '  2 = EXTRACT   — AI_EXTRACT for undocumented table descriptions (~$0.005/table)\n'
                    '  3 = COMPLETE  — Full AI pipeline with COMPLETE for VARIANT/complex (~$0.02/table)\n\n'
                    'Set your chosen tier and then proceed:\n\n'
                    '  UPDATE KG_CONTROL.PUBLIC.WIZARD_STATE\n'
                    "    SET step_results = OBJECT_INSERT(step_results, 'step_5_tier', 1, TRUE)\n"
                    "  WHERE session_id = 'WIZARD_CURRENT';\n\n"
                    "  CALL KG_CONTROL.PUBLIC.ONBOARD_WIZARD('NEXT', 5);\n\n"
                    '  (Replace 1 with your chosen tier 0–3)\n'
                    '  Recommended: tier 1 or 2 for best search quality without high cost.'
                ),
                'result': {'tier_options': [0, 1, 2, 3]},
                'next_hint': "Set step_5_tier in step_results (OBJECT_INSERT), then call ONBOARD_WIZARD('NEXT', 5).",
                'prev_hint': "Call ONBOARD_WIZARD('PREV', 4) to go back to crawl.",
            }

        max_tier      = int(tier_raw)
        enrich_result = call_proc(session, f"CALL KG_CONTROL.PUBLIC.ENRICH_DOMAIN('{domain_upper}', {max_tier})")

        concept_count = 0
        try:
            stats = session.sql(
                f'SELECT COUNT(*) FROM {meta_db}.META.CONCEPTS WHERE is_active = TRUE'
            ).collect()
            concept_count = stats[0][0] if stats else 0
        except Exception:
            pass

        is_error = isinstance(enrich_result, str) and enrich_result.startswith('ERROR:')
        step_results['step_5'] = {
            'status':        'ERROR' if is_error else 'COMPLETE',
            'enrich_result': enrich_result,
            'max_tier':      max_tier,
            'concept_count': concept_count,
            'ts':            datetime.now(timezone.utc).isoformat(),
        }
        save_wizard_state(session, 5, domain_upper, step_results, 'IN_PROGRESS')

        return {
            'step':   5,
            'title':  'Enrich Domain',
            'status': 'ERROR' if is_error else 'COMPLETE',
            'message': (
                f'ENRICH_DOMAIN(tier={max_tier}) result: {enrich_result}\n'
                f'Concepts created/updated: {concept_count}'
            ),
            'result': {
                'enrich_result': enrich_result,
                'concept_count': concept_count,
                'max_tier':      max_tier,
            },
            'next_hint': f"Call ONBOARD_WIZARD('NEXT', 5) to detect relationships in {domain_upper}.",
            'prev_hint': "Call ONBOARD_WIZARD('PREV', 4) to go back to crawl.",
        }

    # ------------------------------------------------------------------
    # Step 6: Detect relationships
    # ------------------------------------------------------------------
    elif step_num == 6:
        if not domain:
            return {
                'step': 6, 'title': 'Detect Relationships', 'status': 'ERROR',
                'message': 'No domain set. Go back to step 2.', 'result': {},
            }

        domain_upper = domain.upper()
        meta_db      = domain_upper + '_META'

        rels_result = call_proc(session, f"CALL KG_CONTROL.PUBLIC.DETECT_RELATIONSHIPS('{domain_upper}')")

        rel_count     = 0
        type_breakdown = {}
        try:
            stats = session.sql(f"""
                SELECT relationship_type, COUNT(*) AS cnt
                FROM {meta_db}.META.RELATIONSHIPS
                WHERE is_active = TRUE
                GROUP BY relationship_type
            """).collect()
            for r in stats:
                type_breakdown[r[0]] = r[1]
                rel_count += r[1]
        except Exception:
            pass

        is_error = isinstance(rels_result, str) and rels_result.startswith('ERROR:')
        step_results['step_6'] = {
            'status':             'ERROR' if is_error else 'COMPLETE',
            'rels_result':        rels_result,
            'relationship_count': rel_count,
            'type_breakdown':     type_breakdown,
            'ts':                 datetime.now(timezone.utc).isoformat(),
        }
        save_wizard_state(session, 6, domain_upper, step_results, 'IN_PROGRESS')

        breakdown_str = ', '.join(f"{t}={n}" for t, n in type_breakdown.items()) or 'none'
        return {
            'step':   6,
            'title':  'Detect Relationships',
            'status': 'ERROR' if is_error else 'COMPLETE',
            'message': (
                f'DETECT_RELATIONSHIPS result: {rels_result}\n'
                f'Relationships found: {rel_count} ({breakdown_str})'
            ),
            'result': {
                'rels_result':        rels_result,
                'relationship_count': rel_count,
                'type_breakdown':     type_breakdown,
            },
            'next_hint': (
                f"Call ONBOARD_WIZARD('NEXT', 6) to run REFRESH_DOMAIN and create the "
                f"Cortex Search Service for {domain_upper}."
            ),
            'prev_hint': "Call ONBOARD_WIZARD('PREV', 5) to go back to enrichment.",
        }

    # ------------------------------------------------------------------
    # Step 7: Refresh domain + create Cortex Search Service
    # ------------------------------------------------------------------
    elif step_num == 7:
        if not domain:
            return {
                'step': 7, 'title': 'Refresh & Index', 'status': 'ERROR',
                'message': 'No domain set. Go back to step 2.', 'result': {},
            }

        domain_upper = domain.upper()
        max_tier     = step_results.get('step_5', {}).get('max_tier', 0)
        meta_db      = domain_upper + '_META'
        css_fqn      = f'{meta_db}.META.{domain_upper}_SEARCH'

        refresh_result = call_proc(
            session,
            f"CALL KG_CONTROL.PUBLIC.REFRESH_DOMAIN('{domain_upper}', {max_tier})"
        )

        css_ok = False
        try:
            css_rows = session.sql(
                f"SHOW CORTEX SEARCH SERVICES LIKE '{domain_upper}_SEARCH' IN SCHEMA {meta_db}.META"
            ).collect()
            css_ok = len(css_rows) > 0
        except Exception:
            pass

        is_error = isinstance(refresh_result, str) and refresh_result.startswith('ERROR:')
        step_results['step_7'] = {
            'status':         'ERROR' if is_error else 'COMPLETE',
            'refresh_result': refresh_result,
            'css_fqn':        css_fqn,
            'css_alive':      css_ok,
            'ts':             datetime.now(timezone.utc).isoformat(),
        }
        save_wizard_state(session, 7, domain_upper, step_results, 'IN_PROGRESS')

        return {
            'step':   7,
            'title':  'Refresh & Index',
            'status': 'ERROR' if is_error else 'COMPLETE',
            'message': (
                f'REFRESH_DOMAIN result: {refresh_result}\n'
                f'Cortex Search Service: {css_fqn}\n'
                f'CSS confirmed live:    {css_ok}\n\n'
                'Note: The CSS may take 1–5 minutes to backfill on first creation.'
            ),
            'result': {
                'refresh_result': refresh_result,
                'css_fqn':        css_fqn,
                'css_alive':      css_ok,
            },
            'next_hint': f"Call ONBOARD_WIZARD('NEXT', 7) to run a test search against {domain_upper}.",
            'prev_hint': "Call ONBOARD_WIZARD('PREV', 6) to go back to relationship detection.",
        }

    # ------------------------------------------------------------------
    # Step 8: Validate — test search against CSS
    # ------------------------------------------------------------------
    elif step_num == 8:
        if not domain:
            return {
                'step': 8, 'title': 'Test Search', 'status': 'ERROR',
                'message': 'No domain set. Go back to step 2.', 'result': {},
            }

        domain_upper  = domain.upper()
        meta_db       = domain_upper + '_META'
        css_fqn       = f'{meta_db}.META.{domain_upper}_SEARCH'
        sample_results = []
        search_error   = None

        try:
            rows = session.sql(f"""
                SELECT search_content
                FROM TABLE(
                    SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
                        '{css_fqn}',
                        OBJECT_CONSTRUCT(
                            'query',   'data tables customer orders transactions',
                            'columns', ARRAY_CONSTRUCT('search_content'),
                            'limit',   3
                        )
                    )
                )
            """).collect()
            for r in rows:
                content = r[0] if r[0] else ''
                sample_results.append(content[:400] + ('...' if len(content) > 400 else ''))
        except Exception as e:
            search_error = str(e)

        if not sample_results and not search_error:
            search_error = (
                'No results returned — CSS may still be initializing '
                '(typically takes 1–5 minutes after first CREATE).'
            )

        step_status = 'WARNING' if (search_error and not sample_results) else 'COMPLETE'
        step_results['step_8'] = {
            'status':       step_status,
            'sample_count': len(sample_results),
            'error':        search_error,
            'ts':           datetime.now(timezone.utc).isoformat(),
        }
        save_wizard_state(session, 8, domain_upper, step_results, 'IN_PROGRESS')

        result_block = ''
        if sample_results:
            result_block = '\n\nSample results:\n' + '\n\n'.join(
                f'  [{i+1}] {r}' for i, r in enumerate(sample_results)
            )

        message = (
            f'Search service:  {css_fqn}\n'
            f'Test query:      "data tables customer orders transactions"\n'
            f'Results returned: {len(sample_results)}'
            + result_block
        )
        if search_error:
            message += f'\n\nNote: {search_error}'

        return {
            'step':   8,
            'title':  'Test Search',
            'status': step_status,
            'message': message,
            'result': {
                'css_fqn':        css_fqn,
                'sample_results': sample_results,
                'error':          search_error,
            },
            'next_hint': f"Call ONBOARD_WIZARD('NEXT', 8) to view the completion summary for {domain_upper}.",
            'prev_hint': "Call ONBOARD_WIZARD('PREV', 7) to re-run refresh/index.",
        }

    # ------------------------------------------------------------------
    # Step 9: Complete — summary + graduation check
    # ------------------------------------------------------------------
    elif step_num == 9:
        if not domain:
            return {
                'step': 9, 'title': 'Complete', 'status': 'ERROR',
                'message': 'No domain set. Go back to step 2.', 'result': {},
            }

        domain_upper = domain.upper()
        meta_db      = domain_upper + '_META'
        stats        = {}

        try:
            r = session.sql(
                f"SELECT COUNT(*) FROM {meta_db}.META.RAW_CONCEPTS WHERE concept_level = 'table'"
            ).collect()
            stats['raw_tables'] = r[0][0] if r else 0
        except Exception:
            stats['raw_tables'] = 0

        try:
            r = session.sql(
                f'SELECT COUNT(*) FROM {meta_db}.META.CONCEPTS WHERE is_active = TRUE'
            ).collect()
            stats['concepts'] = r[0][0] if r else 0
        except Exception:
            stats['concepts'] = 0

        try:
            r = session.sql(
                f'SELECT COUNT(*) FROM {meta_db}.META.RELATIONSHIPS WHERE is_active = TRUE'
            ).collect()
            stats['relationships'] = r[0][0] if r else 0
        except Exception:
            stats['relationships'] = 0

        registry_status = 'UNKNOWN'
        grad_candidate  = False
        try:
            reg = session.sql(
                'SELECT status, graduation_candidate FROM KG_CONTROL.PUBLIC.DOMAIN_REGISTRY '
                'WHERE domain_name = ?',
                [domain_upper]
            ).collect()
            if reg:
                registry_status = reg[0]['STATUS']
                grad_candidate  = bool(reg[0]['GRADUATION_CANDIDATE'])
        except Exception:
            pass

        css_fqn  = f'{meta_db}.META.{domain_upper}_SEARCH'
        max_tier = step_results.get('step_5', {}).get('max_tier', 0)

        step_results['step_9'] = {'status': 'COMPLETE', 'ts': datetime.now(timezone.utc).isoformat()}
        save_wizard_state(session, 9, domain_upper, step_results, 'COMPLETE')

        grad_section = ''
        if grad_candidate:
            grad_section = (
                '\nGRADUATION CANDIDATE:\n'
                f'  {domain_upper} qualifies for the full ontology stack '
                '(sufficient FKs, table count, query volume, and stable schema).\n'
                '  Use the ontology-stack-builder skill to unlock the GRADUATED state,\n'
                '  ONT_CLASS tables, and the KG Router for natural language SQL generation.\n'
            )

        recommended = [
            f"CALL KG_CONTROL.PUBLIC.DISCOVER_DOMAINS('DEEP', 90);  -- find more domains",
            f"CALL KG_CONTROL.PUBLIC.CRAWL_TABLE('{domain_upper}', 'DB.SCHEMA.TABLE');  -- targeted single-table refresh",
            f"CALL KG_CONTROL.PUBLIC.RUN_WATCH('{domain_upper}');  -- monitor for schema drift / shadow tables",
            f"CALL KG_CONTROL.PUBLIC.REFRESH_DOMAIN('{domain_upper}', {max_tier});  -- scheduled full refresh",
            f"CALL KG_CONTROL.PUBLIC.REBUILD_CSS('{domain_upper}');  -- CSS-only rebuild (no re-crawl)",
        ]

        return {
            'step':   9,
            'title':  'Onboarding Complete',
            'status': 'COMPLETE',
            'message': (
                f'Domain {domain_upper} is fully indexed and ready for natural language discovery!\n\n'
                f'Summary:\n'
                f'  Raw tables crawled:   {stats["raw_tables"]}\n'
                f'  Concepts indexed:     {stats["concepts"]}\n'
                f'  Relationships found:  {stats["relationships"]}\n'
                f'  Domain status:        {registry_status}\n'
                f'  Search service:       {css_fqn}\n'
                f'  Enrichment tier:      {max_tier}\n'
                f'{grad_section}\n'
                f'Recommended next steps:\n' +
                '\n'.join(f'  {q}' for q in recommended)
            ),
            'result': {
                'domain':               domain_upper,
                'stats':                stats,
                'registry_status':      registry_status,
                'css_fqn':              css_fqn,
                'graduation_candidate': grad_candidate,
                'recommended_queries':  recommended,
            },
            'next_hint': 'Onboarding complete! Use the kg-data-discovery skill to start querying your domain.',
            'prev_hint': "Call ONBOARD_WIZARD('PREV', 8) to re-run the test search.",
        }

    return {
        'step':    step_num,
        'title':   f'Step {step_num}',
        'status':  'ERROR',
        'message': f'Unknown step: {step_num}. Valid steps are 0–9.',
        'result':  {},
    }


def main(session: Session, action: str, step):
    action = (action or 'STATUS').upper()
    state  = load_wizard_state(session)

    if action == 'STATUS':
        return build_status_response(session, state)

    elif action == 'RESET':
        reset_wizard(session)
        return {
            'status':  'ok',
            'message': "Wizard reset. Call ONBOARD_WIZARD('START', NULL) to begin.",
            'step':    -1,
        }

    elif action == 'START':
        init_wizard(session)
        state = load_wizard_state(session)
        return execute_step(session, 0, state)

    elif action == 'NEXT':
        current_step = state.get('current_step', 0) if state else 0
        next_step    = int(step) if step is not None else current_step + 1
        if next_step > 9:
            return {
                'status':  'complete',
                'message': 'All steps finished! Domain is fully indexed and serving search queries.',
                'step':    9,
            }
        return execute_step(session, next_step, state)

    elif action == 'PREV':
        current_step = state.get('current_step', 0) if state else 0
        prev_step    = max(0, int(step) if step is not None else current_step - 1)
        return execute_step(session, prev_step, state)

    return {
        'status':  'error',
        'message': f"Unknown action: {action}. Valid actions: START, NEXT, PREV, STATUS, RESET",
    }
$$;
"""
