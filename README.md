# TMT Skills Repository

A shared collection of [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) skills built by and for the TMT team. Install any skill by copying its folder into `~/.snowflake/cortex/skills/`.

---

## Skills Catalog

| Skill | Description |
|-------|-------------|
| **[agent-architect](skills/agent-architect)** | General-purpose multi-agent coding framework. Accepts any project brief (app, demo, Native App, pipeline) and decomposes into Architect/Security/Researcher/Worker/Tester roles with manifest-driven coordination. |
| **[agent-evaluation](skills/agent-evaluation)** | Evaluate Cortex Agents using native Snowflake Agent Evaluations. Build evaluation datasets, run evaluations, and analyze accuracy metrics (correctness, tool selection, tool execution, logical consistency). |
| **[agent-flag-tester](skills/agent-flag-tester)** | Standalone Cortex Agent flag comparison testing. Creates 3 agent variants (BASE, AGENTIC, FASTPATH_OFF), builds eval dataset with ground truth, fires EXECUTE_AI_EVALUATION runs, and recommends a winner. |
| **[artifact-drift-monitor](skills/artifact-drift-monitor)** | Scan ACCOUNT_USAGE query history and object definitions to detect drift between deployed Snowflake artifacts (semantic views, dynamic tables, agents, search services) and actual usage patterns. |
| **[bulk-rule-reviewer](skills/bulk-rule-reviewer)** | Execute agent-centric reviews on all rule files in a `rules/` directory and generate a prioritized improvement report. Supports FULL, FOCUSED, and STALENESS review modes. |
| **[coco-usage](skills/coco-usage)** | Query Cortex Code CLI credit and token usage from `SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY`. Use when: coco credits, coco spend, how much have I used, usage this week, top users, session spend, token breakdown. |
| **[cortex-accelerator](skills/cortex-accelerator)** | Guided discovery tool that validates business understanding before building Snowflake semantic views and Cortex Agents. Scans query history, schemas, and BI tools to detect gaps and conflicts, scores trust, and gates pipeline execution until a validated domain map is confirmed. |
| **[cortex-agent-flags](skills/cortex-agent-flags)** | Reference for Cortex Agent experimental flags and chart customization options. Search-first workflow checks Snowflake docs before falling back to cached reference. Covers EnableAgenticAnalyst, EnableVQRFastPath, EnableUnrestrictedChartTool, vega_template, viz_policies. |
| **[cortex-agent-optimization](skills/cortex-agent-optimization)** | Iterative optimization of Snowflake Cortex Agents using strict dev/test eval splits. Covers project setup, instruction editing, build/deploy, eval execution, failure analysis, and accept/reject decisions with auto-termination after 3 consecutive rejections. |
| **[doc-reviewer](skills/doc-reviewer)** | Review project documentation for accuracy, completeness, clarity, and structure. Verifies file references, tests commands, and validates links using a 6-dimension rubric. |
| **[kg-data-discovery](skills/kg-data-discovery)** | Knowledge Graph-powered data discovery using Cortex Search for dynamic schema assembly. Onboard data sources, enrich with cost-tiered AI functions, index as domain CSSs, and query data via natural language without pre-built semantic views. |
| **[memory-organizer](skills/memory-organizer)** | Organize and maintain the `/memories` directory for optimal retrieval. Audits, deduplicates, archives completed projects, and rebuilds the index. |
| **[plan-reviewer](skills/plan-reviewer)** | Review LLM-generated plans for autonomous agent executability using an 8-dimension rubric. Supports FULL, COMPARISON, and META-REVIEW modes. |
| **[prompt-determinism-tester](skills/prompt-determinism-tester)** | Test HOL/demo prompts for build determinism by swarming 3 independent Plan agents and comparing their execution plans. Reports convergence scores across 6 weighted dimensions. |
| **[query-cortex-agent](skills/query-cortex-agent)** | Query a Cortex Agent in a Snowflake account using SQL. Discovers available agents and invokes them via `DATA_AGENT_RUN` / `AGENT_RUN` functions. |
| **[release-change-monitor](skills/release-change-monitor)** | Monitor Snowflake release notes for behavior changes that could break data pipelines. Fetches BCR bundles, inventories pipelines, runs impact analysis, and generates remediation plans. |
| **[rule-creator](skills/rule-creator)** | Create production-ready v3.2 Cursor rule files with template generation, schema validation, and RULES_INDEX.md indexing. Supports Python, Snowflake, JavaScript, Shell, Docker, Golang domains. |
| **[rule-loader](skills/rule-loader)** | Load contextual coding rules from `~/.snowflake/cortex/rules/` for the current task. Always prompts before loading. |
| **[rule-reviewer](skills/rule-reviewer)** | Execute agent-centric rule reviews (FULL/FOCUSED/STALENESS) using a 6-dimension rubric. Evaluates whether autonomous agents can execute rules without judgment calls. |
| **[self-healing-pipeline](skills/self-healing-pipeline)** | Build, debug, and optimize self-healing data pipeline agents in Snowflake SQL using Cortex LLMs. Detects task/dynamic table failures, diagnoses root causes, generates and executes fixes with guardrails, and verifies downstream DAGs. |
| **[semantic-view-ddl](skills/semantic-view-ddl)** | Create Snowflake Semantic Views using native DDL syntax with AI-generated descriptions, iterative self-check, and verified query generation. Pure-SQL path -- no FastGen/YAML. |
| **[skill-tester](skills/skill-tester)** | Test CoCo skills end-to-end by running them with pre-defined fixture inputs and evaluating outputs against assertions. Spawns 3 parallel runs and reports pass/fail per assertion. |
| **[skill-timing](skills/skill-timing)** | Measure skill execution time with microsecond precision. Tracks checkpoints, token usage, cost estimation, anomaly detection, and cross-model performance comparison. |
| **[snowflake-ml-container-runtime](skills/snowflake-ml-container-runtime)** | Build ML training notebooks for Snowflake Container Runtime. Supports XGBoost, sklearn, LightGBM, PyTorch workflows with DataConnector and Model Registry integration. |
| **[snowhouse-demo-scaffold](skills/snowhouse-demo-scaffold)** | Discover a customer's actual Snowflake table schemas via Snowhouse and generate CREATE TABLE + INSERT DDL with synthetic data for customer-specific demos. |
| **[sql-table-extractor](skills/sql-table-extractor)** | Extract tables and columns referenced in SQL queries with Snowflake-specific syntax support. Useful for building table lineage, discovering schema usage, and semantic model preparation. |
| **[vqr-semantic-view-generator](skills/vqr-semantic-view-generator)** | Generate Snowflake Semantic View YAML files from extracted table/column manifests grouped by domain. Pairs with sql-table-extractor for end-to-end VQR-to-semantic-view workflows. |

---

## Installation

Copy any skill folder into your local Cortex Code skills directory:

```bash
cp -R skills/<skill-name> ~/.snowflake/cortex/skills/
```

Restart Cortex Code or start a new session -- the skill will be available immediately.

---

## How to Contribute

We welcome contributions from anyone on the team. Here's how to add or improve skills:

### Adding a New Skill

1. **Fork or clone** this repository.
2. **Create your skill folder** under `skills/`:
   ```
   skills/my-new-skill/
   └── SKILL.md          # Required -- the skill definition
   └── README.md         # Optional -- detailed docs
   └── scripts/          # Optional -- helper scripts
   └── examples/         # Optional -- usage examples
   ```
3. **Write your `SKILL.md`** with a YAML front-matter header:
   ```yaml
   ---
   name: my-new-skill
   description: "Short description of what the skill does and when to use it."
   ---
   ```
4. **Update this README** -- add a row to the Skills Catalog table above.
5. **Add your name** to the Contributions Log below.
6. **Open a pull request** with a clear description of the skill and its use case.

### Improving an Existing Skill

1. Make your changes in the skill folder.
2. Update the Skills Catalog description if the skill's scope changed.
3. Add a note to the Contributions Log.
4. Open a pull request.

### Skill File Structure

| File | Required | Purpose |
|------|----------|---------|
| `SKILL.md` | Yes | Core skill definition that Cortex Code loads |
| `README.md` | No | Extended documentation, architecture notes |
| `scripts/` | No | Helper scripts (Python, bash, etc.) |
| `examples/` | No | Example inputs/outputs |
| `tests/` | No | Test cases for the skill |
| `workflows/` | No | Multi-step workflow definitions |
| `rubrics/` | No | Scoring rubrics (for reviewer skills) |

### Guidelines

- Keep `SKILL.md` self-contained -- Cortex Code reads this file directly.
- Include trigger keywords in the `description` field so the skill is discoverable.
- Test your skill locally before submitting (`cp` it into `~/.snowflake/cortex/skills/` and try it).
- Avoid committing secrets, `.env` files, or large binary assets.
- **Do NOT include Snowhouse references** (e.g., `snowhouse_import.*`, `SNOWHOUSE_IMPORT.*`, Snowhouse connections).
- **Do NOT include internal schemas or UDFs** (e.g., `TEMP.VSHIV.*`, internal stages, internal Salesforce/SFDC data).
- **Do NOT include customer names, account IDs, or any customer-identifiable information.**
- If your skill needs internal data sources, keep it in a private repo instead.

---

## Contributions Log

Track what each contributor has added or changed. **Add your entry when you contribute.**

| Date | Contributor | Skill(s) | Change |
|------|-------------|-----------|--------|
| 2026-03-09 | @jfoley | 13 skills | Initial upload of skills collection (excluded internal-only skills) |
| 2026-04-07 | @jfoley | coco-usage, cortex-accelerator, cortex-agent-optimization, self-healing-pipeline | Add 4 new skills; update agent-evaluation, memory-organizer, rule-creator |
| 2026-05-06 | @jfoley | agent-architect, agent-flag-tester, artifact-drift-monitor, cortex-agent-flags, kg-data-discovery, prompt-determinism-tester, release-change-monitor, semantic-view-ddl, skill-tester, snowhouse-demo-scaffold | Add 10 skills to catalog; sync README with repo contents |

---

## License

Internal use -- Snowflake TMT team.
