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
<<<<<<< HEAD
5. Initialize git in the project directory:
   ```bash
   git init
   git checkout -b main
   ```
6. Create GitHub repo (derive slug from goal: lowercase, hyphens, ≤ 30 chars):
   ```bash
   gh repo create sfc-gh-jfoley/<project-slug> --private \
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
=======
5. Load `agents/architect.agent.md` — hand control to the Architect
6. Architect runs the intake interview and begins Phase 1
>>>>>>> 3be9b73 (Config backup: 2026-04-27 10:41)

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

## Related Skills

- `cortex-agent-optimization` — for optimizing Snowflake Cortex Agents built by this framework
- `prompt-determinism-tester` — for validating prompts produced by this framework
- `cortex-accelerator` — for Snowflake-specific Cortex AI builds (SV + agent pipelines)
