# TMT Skills Repository

A [Cortex Code](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) skill collection built by the TMT team.

## Install

```bash
cortex plugin install sfc-gh-jfoley/TMT-skills-repo
```

After install, skills are available via the skill-loader registry.

## Single Skill Install

```bash
cp -R skills/<skill-name> ~/.snowflake/cortex/skills/
```

## Skills (28)

### Agent Lifecycle
| Skill | Description |
|-------|-------------|
| `cortex-agent-ddl` | Create/edit agents via SQL DDL with spec validation |
| `agent-evaluation` | Evaluate agents using native Snowflake evaluations |
| `agent-flag-tester` | 3-variant flag comparison testing |
| `cortex-agent-optimization` | Iterative agent optimization with dev/test eval splits |
| `cortex-agent-flags` | Experimental flags reference + auto-discovery |
| `query-cortex-agent` | Query agents via DATA_AGENT_RUN SQL |
| `agent-architect` | Multi-agent project framework |

### Semantic Views
| Skill | Description |
|-------|-------------|
| `semantic-view-ddl` | Generate semantic view DDL from source objects |
| `semantic-view-discovery` | Discover and explore existing semantic views |

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

### Productivity
| Skill | Description |
|-------|-------------|
| `architecture-diagram` | Generate architecture diagrams |
| `coco-usage` | Cortex Code usage patterns |
| `google-doc-formatter` | Format Google Docs |
| `lab-builder` | Build workshop labs |
| `snowflake-gslides` | Generate Google Slides |
| `skill-loader` | Skill registry and loader |

### Dev & QA
| Skill | Description |
|-------|-------------|
| `skill-tester` | Test skills for correctness |
| `skill-timing` | Measure skill token/time efficiency |
| `prompt-determinism-tester` | Verify prompt reproducibility |
| `doc-reviewer` | Review documentation quality |
| `plan-reviewer` | Review implementation plan quality |

## Update

```bash
cortex plugin update tmt-skills-repo
```
