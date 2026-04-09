# Snowhouse Artifact Generation

Generate a deployment-ready artifact pack from 15–20 high-signal Snowhouse databases.

## Inputs
- ranked databases from `scripts/rank_snowhouse_databases.sql`
- selected database list

## Outputs
- `artifacts/database_candidates.json`
- `artifacts/schema_inventory.json`
- `artifacts/join_candidates.json`
- `artifacts/semantic_view_scaffolds/`
- `artifacts/kg_nodes_edges/`
- `artifacts/vqr_seeds.json`

## Steps
1. Run `rank_snowhouse_databases.sql` in Snowhouse.
2. Copy the top 15–20 rows into `artifacts/database_candidates.json`.
3. For each selected database, collect schema/table/column inventory.
4. Infer join candidates from repeated column names and query activity.
5. Generate semantic-view scaffolds and KG node/edge manifests.
6. Use those artifacts later in the deployment account.

## Notes
- This process is read-only in Snowhouse.
- It does not modify ontology.
- Artifacts are intended for later deployment/testing in another account.
