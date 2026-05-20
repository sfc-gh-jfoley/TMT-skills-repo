---
name: agent-architect
description: >
  General-purpose multi-agent coding framework. Accepts any project brief —
  iPhone app, demo, Native App, data pipeline, web app, anything — and
  orchestrates a full team to research, plan, build, review, and test it.
  The Architect determines team count, researchers gather context in parallel,
  workers claim tasks via checkout, a Security Architect gates every task,
  and independent testers verify each deliverable.
  Triggers: architect project, build project, assign teams, spin up a team,
  I want to build, create a project team, agent architect, offshore team,
  multi-agent build, coordinate agents, spawn teams.
---

# Agent Architect Framework

## What This Is

A coding project OS for CoCo. You describe what you want built. The framework does the rest:

1. **Researcher agents** gather context in parallel (codebase, docs, patterns, APIs)
2. **Architect** synthesizes research → determines team count → decomposes into tasks
3. **Worker agents** claim tasks via checkout (git-like locking) → build
4. **Security Architect** gates every completed task before it can ship
5. **Tester agents** independently verify every deliverable

No two agents step on each other. All coordination flows through `project-manifest.json`.

## When to Use

- Any project with ≥ 3 independent workstreams
- Projects requiring parallel execution (frontend + backend + infra, etc.)
- Anywhere you'd normally coordinate offshore teams
- When you want security review baked in at the task level, not as an afterthought

## How to Invoke

Just describe what you want built:

```
"I want to build an iPhone app that tracks my Snowflake usage"
"Build me a React dashboard for the cortex-dashboard project"
"I need a Snowflake Native App for KG discovery with hub/spoke deployment"
"Create a demo for AT&T IoT with 6 CoCo prompts"
```

The Architect picks it up from there.

## Framework Files

| File | Role |
|---|---|
| `agents/architect.agent.md` | Project Architect — planning, team sizing, global review |
| `agents/security.agent.md` | Security Architect — blocking per-task security gate |
| `agents/researcher.agent.md` | Researcher — parallel context gathering, read-only |
| `agents/worker.agent.md` | Worker — task checkout, execution, checkin |
| `agents/tester.agent.md` | Tester — independent deliverable verification |
| `templates/project-manifest.json` | Cross-talk state bus |
| `templates/task-checkout.json` | Task checkout format |
| `templates/test-report.json` | Test report format |

## Project Lifecycle

```
INTAKE → RESEARCH → PLAN → EXECUTE → REVIEW → TEST → SHIP
   ↑          ↑        ↑       ↑          ↑        ↑      ↑
  User    Researchers  Arch  Workers    SecArch  Testers  Arch
```

## Startup

When this skill is invoked:

1. Create the project working directory: `.agent-project/` in the current working dir
2. Copy `templates/project-manifest.json` → `.agent-project/manifest.json`
3. Copy `templates/task-checkout.json` → `.agent-project/checkout-format.json`
4. Copy `templates/test-report.json` → `.agent-project/test-report-format.json`
5. Initialize git in the project directory:
   ```bash
   git init
   git checkout -b main
   ```
6. Create GitHub repo (derive slug from goal: lowercase, hyphens, ≤ 30 chars):
   ```bash
   gh repo create ${GH_ORG}/<project-slug> --private \
     --description "<project_brief.goal>"
   ```
7. Write initial commit + push:
   ```bash
   git add .agent-project/manifest.json
   git commit -m "init: <project-slug> via agent-architect"
   git remote add origin <repo-url-from-step-6>
   git push -u origin main
   ```
8. Write `manifest.git.remote` (repo URL) and `manifest.git.repo_name` (slug)
9. Load `agents/architect.agent.md` — hand control to the Architect
10. Architect runs the intake interview and begins Phase 1

## Cross-Talk Protocol

All agents communicate exclusively through `.agent-project/manifest.json`:

- **Researchers** → write `manifest.research[topic]`
- **Architect** → writes `manifest.arch_plan`, `manifest.teams`, `manifest.tasks`
- **Workers** → write `manifest.checkedout[task_id]` before touching files
- **SecArch** → writes `manifest.security_reviews[task_id]`
- **Testers** → write `manifest.test_results[deliverable_id]`

Agents poll the manifest for state changes. Direct agent-to-agent messaging is NOT used.

## Team Sizing (Architect decides)

| Project scope | Teams |
|---|---|
| < 5 tasks, single domain | 1 team |
| 5-15 tasks, 2-3 domains | 2-3 teams |
| Full-stack (UI + API + DB + infra) | 3-4 teams |
| Cross-account / multi-system | 4-5 teams |

## Security Gate Rules

- Every task must pass SecArch review before completion
- CRITICAL or HIGH findings → task rejected, returned to worker
- MAJOR_CHANGE (touches shared interfaces/DDL/schemas) → Architect must also review
- No batching: each task reviewed independently

## Retry & Escalation Rules

| Event | Max Retries | Escalation |
|---|---|---|
| SecArch REJECTED | 2 | After 2nd rejection → Architect escalates to user with full findings |
| Tester FAIL | 2 | After 2nd failure → Architect escalates to user with test report |
| Worker BLOCKED (dependency) | 0 | Architect re-spawns worker after dependency completes |
| Worker build loop (3 cycles) | 0 | Worker self-reports BLOCKED → Architect escalates to user |
| Stuck task (no progress > 1hr) | 1 | Architect reclaims + re-spawns with fresh context |

**Escalation format** (written to user or `.agent-project/escalation.md`):
```
ESCALATION: <task_id> — <title>
REASON: <SecArch rejected 2x | Tester failed 2x | Build loop stuck>
ATTEMPTS: <what was tried across retries>
FINDINGS: <cumulative findings from all attempts>
RECOMMENDATION: <Architect's assessment of what's wrong>
OPTIONS: 
  A) Descope this task (remove from plan)
  B) Provide guidance (Architect will relay to next Worker spawn)
  C) Manual intervention (user fixes directly)
```

## Headless / Offshore Team Configuration

For autonomous execution without user interaction during the build phase:

### Configuration in manifest.json

```json
{
  "execution_mode": {
    "type": "headless",
    "auto_approve_plan": false,
    "auto_merge_prs": false,
    "escalation_channel": "memory",
    "max_parallel_workers": 4,
    "retry_budget": 2,
    "halt_on": [
      "CRITICAL_security_finding",
      "max_retries_exceeded",
      "scope_creep_detected"
    ]
  }
}
```

### Configuration Options

| Field | Default | Description |
|---|---|---|
| `type` | `"interactive"` | `"interactive"` = ask user at each gate. `"headless"` = run autonomously after plan approval. |
| `auto_approve_plan` | `false` | If `true`, Architect skips user plan approval. **Dangerous** — only for well-understood, repeatable project types. |
| `auto_merge_prs` | `false` | If `true`, Architect merges PRs at SHIP without user confirmation. |
| `escalation_channel` | `"user"` | `"user"` = ask_user_question. `"memory"` = cortex ctx remember (for async review). `"file"` = write to escalation.md. |
| `max_parallel_workers` | `4` | Maximum concurrent Worker subagents. Higher = faster but more resource-intensive. |
| `retry_budget` | `2` | Global retry limit per task across all gate types. |
| `halt_on` | `[]` | Conditions that force the entire project to STOP. |

### Launching a Headless Project

From your primary CoCo session:

```
"Build me <project description>. Run it headless — I'll check back when it's done or if it gets stuck."
```

The Architect:
1. Runs intake (asks 5 questions unless brief is pre-populated)
2. Runs research phase
3. Presents plan for approval (unless `auto_approve_plan: true`)
4. After approval: executes autonomously
5. On completion: writes SHIP artifacts + memory
6. On halt: writes escalation.md + memory, STOPS

### Pre-Populating a Headless Brief

For repeatable project types, pre-write the manifest:

```json
{
  "project_brief": {
    "goal": "Build a Cortex Agent for <customer> with subscriber 360 semantic view",
    "success_criteria": "Agent answers 6 sample questions correctly via DATA_AGENT_RUN",
    "existing_assets": "Schema at customers/<slug>/schema_summary.md, DDL at demo_tables.sql",
    "constraints": ["Snowflake only", "claude-sonnet-4-5 model", "connection: default"],
    "priority": "ship_fast"
  },
  "execution_mode": {
    "type": "headless",
    "auto_approve_plan": true,
    "max_parallel_workers": 2
  }
}
```

Then invoke: `"Run agent-architect on <path> — manifest is pre-populated."`

## Related Skills

- `cortex-agent-optimization` — for optimizing Snowflake Cortex Agents built by this framework
- `prompt-determinism-tester` — for validating prompts produced by this framework
- `cortex-accelerator` — for Snowflake-specific Cortex AI builds (SV + agent pipelines)
