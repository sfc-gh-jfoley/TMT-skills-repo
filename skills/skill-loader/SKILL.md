---
name: skill-loader
description: "On-demand skill/plugin/rule loader. Keeps context minimal — loads only what's needed for the current task."
---

# Skill Loader

Load skills, plugins, and rules on-demand from `~/.snowflake/cortex/vault/`. 

## Workflow

1. Identify which skill the user needs from the registry below
2. Read the SKILL.md: `~/.snowflake/cortex/vault/{path}/SKILL.md`
3. Follow the loaded skill's instructions for the remainder of the task

If unsure which skill matches, ask the user.

---

## Registry

### Semantic Views & Analyst

| Skill | When to use | Path |
|-------|-------------|------|
| semantic-view-ddl | Build/edit semantic views (DDL path) | `skills/semantic-view-ddl/` |
| semantic-view-discovery | Find SV candidates from schema analysis | `skills/semantic-view-discovery/` |
| vqr-semantic-view-generator | Multi-domain SV from query history | `plugins/ontology-demo/skills/vqr-semantic-view-generator/` |

### Cortex Agents

| Skill | When to use | Path |
|-------|-------------|------|
| cortex-agent-ddl | Create/deploy Cortex Agents | `plugins/cortex-agent-toolkit/skills/cortex-agent-ddl/` |
| cortex-agent-flags | Agent experimental flags reference | `plugins/cortex-agent-toolkit/skills/cortex-agent-flags/` |
| cortex-agent-optimization | Iterative agent prompt optimization | `plugins/cortex-agent-toolkit/skills/cortex-agent-optimization/` |
| agent-evaluation | Run EXECUTE_AI_EVALUATION | `plugins/cortex-agent-toolkit/skills/agent-evaluation/` |
| agent-flag-tester | Compare agent flag variants (3-way) | `plugins/cortex-agent-toolkit/skills/agent-flag-tester/` |
| query-cortex-agent | Query an existing agent via SQL | `plugins/cortex-agent-toolkit/skills/query-cortex-agent/` |

### Knowledge Graph & Ontology

| Skill | When to use | Path |
|-------|-------------|------|
| cortex-accelerator | Guided discovery → agent build | `plugins/ontology-demo/skills/cortex-accelerator/` |
| kg-data-discovery | KG crawl/enrich/relationship detection | `plugins/ontology-demo/skills/kg-data-discovery/` |
| ontology-stack-builder | Build ontology-on-Snowflake | `plugins/ontology-demo/skills/ontology-stack-builder/` |

| sql-table-extractor | Extract table definitions from SQL | `plugins/ontology-demo/skills/sql-table-extractor/` |

### Ops & Monitoring

| Skill | When to use | Path |
|-------|-------------|------|
| artifact-drift-monitor | Check SV/DT/Agent drift | `plugins/ops-monitor/skills/artifact-drift-monitor/` |
| release-change-monitor | Monitor Snowflake release changes | `plugins/ops-monitor/skills/release-change-monitor/` |
| self-healing-pipeline | Auto-fix pipeline failures | `plugins/ops-monitor/skills/self-healing-pipeline/` |

### Rules & Governance

| Skill | When to use | Path |
|-------|-------------|------|
| rule-loader | Load coding rules for current task | `plugins/rule-governance/skills/rule-loader/` |
| rule-creator | Create new rules | `plugins/rule-governance/skills/rule-creator/` |
| rule-reviewer | Review a single rule quality | `plugins/rule-governance/skills/rule-reviewer/` |
| bulk-rule-reviewer | Batch review rules | `plugins/rule-governance/skills/bulk-rule-reviewer/` |
| memory-organizer | Clean/consolidate memories | `plugins/rule-governance/skills/memory-organizer/` |

### Meta & Quality

| Skill | When to use | Path |
|-------|-------------|------|
| doc-reviewer | Review documents for quality | `plugins/coco-meta/skills/doc-reviewer/` |
| plan-reviewer | Score implementation plans | `plugins/coco-meta/skills/plan-reviewer/` |
| prompt-determinism-tester | Test prompt consistency (3-agent) | `plugins/coco-meta/skills/prompt-determinism-tester/` |
| skill-tester | Test skills with fixtures | `plugins/coco-meta/skills/skill-tester/` |
| skill-timing | Measure skill execution time | `plugins/coco-meta/skills/skill-timing/` |

### Workshops & Demos

| Skill | When to use | Path |
|-------|-------------|------|
| lab-builder | Build HOL/workshop labs | `skills/lab-builder/` |
| se-lab-intake | SE lab intake questionnaire | `plugins/se-workshop/skills/se-lab-intake/` |
| executive-account-planning-markdown | Executive account plans | `plugins/se-workshop/skills/executive-account-planning-markdown/` |
| snowflake-ml-container-runtime | ML Container Runtime workshop | `plugins/se-workshop/skills/snowflake-ml-container-runtime/` |

### Project Architecture

| Skill | When to use | Path |
|-------|-------------|------|
| agent-architect | Multi-agent project builds (full framework) | `plugins/cortex-architect-builder/skills/agent-architect/` |

### Diagrams & Visuals

| Skill | When to use | Path |
|-------|-------------|------|
| architecture-diagram | Generate architecture/system/flow diagrams (Mermaid→Excalidraw→PNG) | `skills/architecture-diagram/` |
| snowflake-gslides | Create Google Slides decks | `skills/snowflake-gslides/` |

### Utilities

| Skill | When to use | Path |
|-------|-------------|------|
| coco-usage | CoCo token/credit consumption analysis | `skills/coco-usage/` |
| google-doc-formatter | Format markdown as Google Doc | `skills/google-doc-formatter/` |

---

## Loading Rules (coding standards)

For coding rules, first load rule-loader:
```
Read: ~/.snowflake/cortex/vault/plugins/rule-governance/skills/rule-loader/SKILL.md
```
Then follow its workflow to load specific rule files from `~/.snowflake/cortex/rules/`.

---

## Constraints

- **Load one skill at a time** — don't bulk-load
- **After loading**: follow that skill's instructions completely as if natively invoked
- **If the skill references sub-files** (phases/, references/, etc.): those are relative to the skill's vault directory
- **All vault paths are relative to** `~/.snowflake/cortex/vault/`
