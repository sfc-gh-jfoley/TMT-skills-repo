---
name: cortex-agent-ddl
description: Create, edit, and orchestrate Cortex Agents using pure SQL DDL — auto-generates tool descriptions from semantic view metadata, enforces 16-rule spec validation, supports multi-agent routing (master agent dispatches to sub-agents via UDF custom tools), and offers eval skill handoff. Use instead of the bundled cortex-agent skill when you want a reliable, HOL-friendly, self-checking creation path without Python scripts.
triggers:
  - create cortex agent
  - create agent ddl
  - agent ddl
  - build agent sql
  - edit agent spec
  - agent creation workflow
  - new cortex agent
  - agent from semantic view
  - multi-agent orchestration
  - agent routing
  - master agent
  - call agent from agent
  - route to sub-agents
  - multi-agent
---

# Cortex Agent DDL Skill

## When to use this skill

Use this skill instead of the bundled `cortex-agent` skill when:
- You want a **pure SQL path** — no Python, no `uv`, no workspace directories
- You need **tool descriptions auto-generated** from semantic view / CSS metadata
- You want a **self-check loop** that validates the spec against 16 rules before execution
- You're building an agent for a HOL, demo, or workshop (runs entirely in Snowsight)
- The bundled skill's REST API approach produced an agent that doesn't work well

**This skill creates and edits Cortex Agents using `CREATE AGENT FROM SPECIFICATION $$...$$` DDL only.**

---

## Workflow overview

```
Phase 1: Context           → NEW or EDIT?, name/placement, purpose, privilege pre-check
    ↓
Phase 2: Discover Tools    → SHOW SVs/CSS, DESCRIBE each, CORTEX.COMPLETE auto-descriptions
    ↓ [STOP: approve tool descriptions]
Phase 3: Instructions      → draft orchestration + response, 5 best-practices checks
    ↓ [STOP: approve instructions]
Phase 4: Assemble Spec     → full JSON: model, flags, execution_environment, budget, tools, profile
    ↓
Phase 5: Self-Check        → 16-rule validation; auto-fix FAILs, present WARNs
    ↓ [STOP: approve spec]
Phase 6: Execute & Verify  → CREATE AGENT → privilege grants → DESCRIBE → structural check
    ↓
Phase 7: Test & Harden     → DATA_AGENT_RUN smoke test → iterate → handoff to eval skills
```

**EDIT path**: Phase 1 detects EDIT intent → loads `edit/01_edit_flow.md` directly (4 steps, shorter).

**Mandatory stopping points**: after Phases 2, 3, 5, 6, 7.

---

## Quick start

To begin: **→ Load [phases/01_context.md](phases/01_context.md)**

---

## Phase reference

| Phase | File | Purpose |
|-------|------|---------|
| 1 | [phases/01_context.md](phases/01_context.md) | New vs edit, name/placement, privilege pre-check |
| 2 | [phases/02_discover_tools.md](phases/02_discover_tools.md) | Discover SVs/CSS + auto-generate tool descriptions |
| 3 | [phases/03_build_instructions.md](phases/03_build_instructions.md) | Draft orchestration instructions + BP checks |
| 4 | [phases/04_assemble_spec.md](phases/04_assemble_spec.md) | Assemble full spec JSON |
| 5 | [phases/05_self_check.md](phases/05_self_check.md) | 16-rule spec validation with auto-fix loop |
| 6 | [phases/06_execute_verify.md](phases/06_execute_verify.md) | Execute + grants + DESCRIBE + structural check |
| 7 | [phases/07_test_harden.md](phases/07_test_harden.md) | Smoke test + profile + eval skill handoff |
| EDIT | [edit/01_edit_flow.md](edit/01_edit_flow.md) | Load spec → diff → safety → patch → verify |

**Reference**: [reference/agent_spec_syntax.md](reference/agent_spec_syntax.md) — complete spec JSON, model names, tool types, flags, error cheat sheet

---

## Key design principles

1. **Self-checking at every phase**: Phase 5 runs 16 spec rules internally before showing JSON to the user. Phase 6 validates DESCRIBE output structurally. Nothing broken is executed.

2. **Iterative loop**: Phases 5-6 loop until passing. The agent fixes its own spec based on structured error output — no copy-paste debugging.

3. **Tool descriptions by default**: Phase 2 runs CORTEX.COMPLETE against DESCRIBE SEMANTIC VIEW output to generate rich tool descriptions following the best-practices template. This is the #1 quality factor for agents.

4. **Permissions first**: Phase 1 checks CREATE AGENT privilege. Phase 2 checks tool resource access. Phase 6 handles post-creation grants. No silent failures from missing privileges.

5. **Eval handoff built in**: Phase 7 writes `handoff.json` and offers to invoke `agent-flag-tester`, `cortex-agent-optimization`, or the bundled evaluate workflow.

6. **Edit safety**: The edit path loads the current spec, shows a diff of proposed changes, offers a production clone, and re-runs Phase 5 self-check before any ALTER.

---

## Critical spec rules (always active)

These rules are embedded in Phase 5's self-check. Reference [reference/agent_spec_syntax.md](reference/agent_spec_syntax.md) for the full spec.

| Rule | |
|------|-|
| `model.orchestration` must be set | Required — no default |
| `instructions.orchestration` must be non-empty | Agent is directionless without it |
| `execution_environment.warehouse` required | Missing → CREATE fails |
| Every `tools[].tool_spec.name` must match a key in `tool_resources` | Mismatch → tool unavailable at runtime |
| `cortex_analyst_text_to_sql` requires a real Semantic View FQN | Regular SQL views / tables silently fail |
| Tool descriptions must be >100 chars with boundary language | Short descriptions cause tool misselection |
| `sample_questions` belongs inside `instructions`, not at spec root | Common placement mistake |
| `CREATE OR REPLACE` wipes profile + resets ownership | Always restore after any OR REPLACE operation |

---

## Relationship to other skills

| Goal | Skill to use |
|------|-------------|
| New agent — pure SQL, HOL, auto-descriptions, self-check | **This skill** (cortex-agent-ddl) |
| Edit existing agent — load, diff, patch, verify | **This skill** (edit path) |
| Multi-agent routing — master agent dispatches to sub-agents | **This skill** (router path — Phase 1 Step 1.0.5 → Phase 2 Step 2.0) |
| Formal evaluation with ground-truth dataset | Bundled `cortex-agent` → evaluate/dataset sub-skills |
| Debug specific query or SI request ID | Bundled `cortex-agent` → debug sub-skill |
| 3-variant flag comparison (BASE/AGENTIC/FASTPATH_OFF) | `agent-flag-tester` personal skill |
| Iterative improvement loop with DEV/TEST split | `cortex-agent-optimization` personal skill |
| Experimental flags reference (EnableAgenticAnalyst etc.) | `cortex-agent-flags` personal skill |
