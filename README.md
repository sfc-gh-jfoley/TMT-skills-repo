# TMT Skills Repository

A shared collection of [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) skills built by and for the TMT team. Install any skill by copying its folder into `~/.snowflake/cortex/skills/`.

---

## Skills Catalog

| Skill | Description |
|-------|-------------|
| **[a360-coco-skill](skills/a360-coco-skill)** | Account 360 analysis -- answer questions about Snowflake customer accounts (health, credits, consumption, support cases, opportunities, revenue, product adoption). |
| **[agent-evaluation](skills/agent-evaluation)** | Evaluate Cortex Agents using native Snowflake Agent Evaluations. Build evaluation datasets, run evaluations, and analyze accuracy metrics (correctness, tool selection, tool execution, logical consistency). |
| **[bulk-rule-reviewer](skills/bulk-rule-reviewer)** | Execute agent-centric reviews on all rule files in a `rules/` directory and generate a prioritized improvement report. Supports FULL, FOCUSED, and STALENESS review modes. |
| **[doc-reviewer](skills/doc-reviewer)** | Review project documentation for accuracy, completeness, clarity, and structure. Verifies file references, tests commands, and validates links using a 6-dimension rubric. |
| **[expert-se-router](skills/expert-se-router)** | Expert SE toolkit router -- detects user intent and routes to the appropriate sub-skill (Account 360, User Analytics, or Snowflake Intelligence Accelerator). |
| **[memory-organizer](skills/memory-organizer)** | Organize and maintain the `/memories` directory for optimal retrieval. Audits, deduplicates, archives completed projects, and rebuilds the index. |
| **[plan-reviewer](skills/plan-reviewer)** | Review LLM-generated plans for autonomous agent executability using an 8-dimension rubric. Supports FULL, COMPARISON, and META-REVIEW modes. |
| **[query-cortex-agent](skills/query-cortex-agent)** | Query a Cortex Agent in a Snowflake account using SQL. Discovers available agents and invokes them via `DATA_AGENT_RUN` / `AGENT_RUN` functions. |
| **[rule-creator](skills/rule-creator)** | Create production-ready v3.2 Cursor rule files with template generation, schema validation, and RULES_INDEX.md indexing. Supports Python, Snowflake, JavaScript, Shell, Docker, Golang domains. |
| **[rule-loader](skills/rule-loader)** | Load contextual coding rules from `~/.snowflake/cortex/rules/` for the current task. Always prompts before loading. |
| **[rule-reviewer](skills/rule-reviewer)** | Execute agent-centric rule reviews (FULL/FOCUSED/STALENESS) using a 6-dimension rubric. Evaluates whether autonomous agents can execute rules without judgment calls. |
| **[skill-timing](skills/skill-timing)** | Measure skill execution time with microsecond precision. Tracks checkpoints, token usage, cost estimation, anomaly detection, and cross-model performance comparison. |
| **[snowflake-intelligence-accelerator-via-snowhouse](skills/snowflake-intelligence-accelerator-via-snowhouse)** | Build complete Snowflake Intelligence setups for customers using autonomous discovery from Snowhouse metadata. Discovers BI warehouses, clusters into business domains, and generates deployment scripts. |
| **[snowflake-ml-container-runtime](skills/snowflake-ml-container-runtime)** | Build ML training notebooks for Snowflake Container Runtime. Supports XGBoost, sklearn, LightGBM, PyTorch workflows with DataConnector and Model Registry integration. |
| **[snowflake-user-analytics-coco-skill](skills/snowflake-user-analytics-coco-skill)** | Deep-dive profiling of a specific user's query activity on a Snowflake account. Produces markdown reports with Mermaid diagrams and Chart.js charts covering compute patterns, tools, connectors, and optimization opportunities. |
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

---

## Contributions Log

Track what each contributor has added or changed. **Add your entry when you contribute.**

| Date | Contributor | Skill(s) | Change |
|------|-------------|-----------|--------|
| 2026-03-09 | @jfoley | All 17 skills | Initial upload of full skills collection |
| | | | |

---

## License

Internal use -- Snowflake TMT team.
