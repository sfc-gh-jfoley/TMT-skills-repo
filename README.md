# TMT Skills Repository

A [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) plugin with 29 skills built by and for the TMT team.

## Install (recommended)

```bash
cortex plugin install sfc-gh-jfoley/TMT-skills-repo
```

After install, skills are available as `$tmt-skills:<skill-name>`.

## Legacy Install (single skill)

If you only want one skill:

```bash
cp -R skills/<skill-name> ~/.snowflake/cortex/skills/
```

## Skills (29)

### Agent Lifecycle
| Skill | Description |
|-------|-------------|
| `cortex-agent-ddl` | Create/edit agents via SQL DDL with 16-rule spec validation |
| `agent-evaluation` | Evaluate agents using native Snowflake evaluations |
| `agent-flag-tester` | 3-variant flag comparison testing (BASE/AGENTIC/FASTPATH_OFF) |
| `cortex-agent-optimization` | Iterative optimization with dev/test eval splits |
| `cortex-agent-flags` | Experimental flags reference + auto-discovery |
| `query-cortex-agent` | Query agents via DATA_AGENT_RUN SQL |
| `agent-architect` | Multi-agent project framework |

### Ontology & Demo Pipeline
| Skill | Description |
|-------|-------------|
| `cortex-accelerator` | 7-phase guided discovery (entry point for ontology demos) |
| `kg-data-discovery` | KG-powered schema discovery via Cortex Search |
| `sql-table-extractor` | Extract tables/columns from SQL queries |
| `vqr-semantic-view-generator` | Generate Semantic View YAML |
| `ontology-stack-builder` | Build ONT_* views + agent deployment |
| `snowhouse-demo-scaffold` | Discover customer schemas via Snowhouse telemetry |

### Operations
| Skill | Description |
|-------|-------------|
| `release-change-monitor` | Track Snowflake release changes |
| `artifact-drift-monitor` | Detect drift in deployed artifacts |
| `self-healing-pipeline` | Auto-fix broken pipelines |

### Rule & Memory Governance
| Skill | Description |
|-------|-------------|
| `rule-creator` | Create production-ready rule files |
| `rule-reviewer` | Review rule quality |
| `rule-loader` | Load rules into sessions |
| `bulk-rule-reviewer` | Batch review all rules |
| `memory-organizer` | Organize/deduplicate memories |

### SE Workshops
| Skill | Description |
|-------|-------------|
| `se-lab-intake` | Pre-intake discovery + curriculum options |
| `executive-account-planning-markdown` | Account research for demo/lab prep |
| `snowflake-ml-container-runtime` | ML Jobs + Container Runtime reference |

### Dev & QA
| Skill | Description |
|-------|-------------|
| `skill-tester` | Test skills for correctness |
| `skill-timing` | Measure skill token/time efficiency |
| `prompt-determinism-tester` | Verify prompt reproducibility |
| `doc-reviewer` | Review documentation quality |
| `plan-reviewer` | Review implementation plan quality |

## Contributing

1. Fork this repository
2. Create your skill under `skills/<skill-name>/SKILL.md`
3. Open a pull request

## Update

```bash
cortex plugin update tmt-skills
```
