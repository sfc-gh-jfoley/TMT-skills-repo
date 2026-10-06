# TMT Skills Repository

A [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) skill and plugin collection built by the TMT team.

## Install

```bash
cortex plugin install sfc-gh-jfoley/TMT-skills-repo
```

## Single Skill / Plugin Install

```bash
# A standalone skill
cp -R skills/<skill-name> ~/.snowflake/cortex/skills/

# A plugin (with sub-skills)
cp -R plugins/<plugin-name> ~/.snowflake/cortex/plugins/
```

## Update

```bash
cortex plugin update tmt-skills-repo
```

---

## Plugins

### cortex-agent-toolkit

Full lifecycle toolkit for Snowflake Cortex Agents: create, evaluate, optimize, query, and manage experimental flags.

| Sub-skill | Description |
|-----------|-------------|
| `agent-ddl` | Create/edit agents via SQL DDL with 17-rule spec validation and multi-agent routing |
| `agent-evaluation` | Evaluate agents using native Snowflake Agent Evaluations |
| `agent-flags-reference` | Experimental flags reference with search-first doc lookup |
| `agent-gepa-optimizer` | Population-based evolutionary optimization of agent instructions |
| `agent-instruction-optimizer` | DSPy MIPROv2 optimizer for agent instructions |
| `agent-optimizer` | Iterative optimization using dev/test eval splits |
| `agent-model-tester` | Standalone model variant comparison testing |
| `agent-query` | Query agents via DATA_AGENT_RUN / AGENT_RUN SQL |
| `agent-analytical-search` | Configure Cortex Search tools for corpus-wide analytical search |
| `agent-feedback-analyzer` | Diagnostic triage of CoWork pilot user feedback |

### semantic-view-toolkit

Full lifecycle toolkit for Snowflake Semantic Views: discover, create, evaluate, optimize, audit, and manage VQRs.

| Sub-skill | Description |
|-----------|-------------|
| `sv-ddl` | Create semantic views via DDL |
| `sv-discovery` | Discover optimal domain groupings from account usage |
| `sv-evaluation` | Evaluate semantic view quality |
| `sv-audit` | Audit semantic views against query patterns |
| `sv-iterative-optimizer` | Iterative optimization of semantic views |
| `sv-gepa-optimizer` | Population-based evolutionary SV optimization |
| `sv-rearchitect` | Rearchitect semantic views for better coverage |
| `sv-coverage-checker` | Check semantic view coverage gaps |
| `sv-materialize` | Materialize semantic view results |
| `sv-watch` | Monitor semantic view drift |
| `sv-snippet-suggester` | Suggest VQR snippets |
| `vqr-generator` | Generate verified query representations |
| `vqr-curator` | Curate and manage VQRs |

### coco-meta

Quality and meta toolkit for Cortex Code skills and workflows.

| Sub-skill | Description |
|-----------|-------------|
| `prompt-determinism-tester` | Swarm-test HOL/demo prompts for build determinism |
| `skill-tester` | End-to-end skill testing with fixture inputs and assertions |
| `skill-timing` | Measure skill execution time and performance |
| `plan-reviewer` | Review LLM-generated plans for executability |
| `doc-reviewer` | Review documentation for accuracy, completeness, and clarity |

---

## Standalone Skills

| Skill | Description |
|-------|-------------|
| `agent-architect` | Multi-agent project framework — research, plan, build, security-gate, and test |
| `lab-builder` | Build hands-on workshop labs for customers and SEs |
| `snowhouse-demo-scaffold` | Build Snowflake Intelligence setups via Snowhouse metadata discovery |
