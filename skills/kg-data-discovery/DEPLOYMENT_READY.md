# Deployment Ready Checklist

This project is prepared for deployment in a later session to another Snowflake account.

## Scope boundary
- Ontology is read-only and unchanged.
- All new work is additive in `kg-data-discovery`.

## Files added/updated
### Updated
- `procs/sql/00_ddl.sql`
- `procs/sql/01_discover.sql`
- `procs/sql/07_refresh.sql`
- `procs/interfaces.md`
- `procs/sql/deploy.sql`

### Added
- `procs/sql/12_query_plane_ddl.sql`
- `procs/sql/13_verification_ddl.sql`
- `procs/sql/17_query_plane_proc_wrappers.sql`
- `procs/sql/18_promotion_loop.sql`
- `procs/sql/19_ops_runner.sql`
- `procs/python/10_detect_semantic_conflicts.py`
- `procs/python/11_verify_metric_bindings.py`
- `procs/python/12_resolve_query_context.py`
- `procs/python/13_build_transient_contract.py`
- `procs/python/14_validate_transient_contract.py`
- `procs/python/15_answer_query.py`
- `tests/query_plane_checkpoints.sql`
- `scripts/rank_snowhouse_databases.sql`
- `references/snowhouse_artifact_generation.md`

## Deployment order in target account
1. Deploy `procs/sql/00_ddl.sql`
2. Deploy `procs/sql/01_discover.sql`
3. Deploy Python procs for crawl/enrich/detect/watch/wizard
4. Deploy `procs/sql/07_refresh.sql`
5. Deploy `procs/sql/12_query_plane_ddl.sql` (replace `__DOMAIN_META_DB__`)
6. Deploy `procs/sql/13_verification_ddl.sql` (replace `__ONT_DB__`, `__ONT_SCHEMA__`)
7. Deploy `procs/sql/17_query_plane_proc_wrappers.sql`
8. Optionally deploy:
   - `procs/sql/18_promotion_loop.sql`
   - `procs/sql/19_ops_runner.sql`
9. Run `tests/query_plane_checkpoints.sql`

## Preconditions for deployment/testing
- target account has warehouse available
- role can create DB/schema/procs
- domain meta DB exists via `BOOTSTRAP_KG_META`
- ontology tables exist if verification procs will be tested
- at least one domain is crawled/enriched/active before query-plane testing

## Snowhouse artifact prep before deployment
1. Run `scripts/rank_snowhouse_databases.sql` in Snowhouse
2. Select 15–20 databases
3. Generate schema/join/semantic scaffold artifacts using `references/snowhouse_artifact_generation.md`
4. Carry those artifacts into the target deployment session

## Current proof level
- local file creation and file-level validation only
- no ontology changes made
- Snowflake runtime validation deferred to deployment session
