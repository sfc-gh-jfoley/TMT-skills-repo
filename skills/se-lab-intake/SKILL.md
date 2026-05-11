# Skill: se-lab-intake

Pre-lab intake skill for SEs. Gathers everything lab-builder needs before a single
file gets written. Output is a structured intake document that feeds directly into
`lab-builder` as its starting context.

**Use this skill BEFORE `lab-builder`.** It is the intake gate.

**Trigger phrases:**
- "start a lab for [company]"
- "intake for [company] lab"
- "I have a lab request from [company]"
- "[company], [feature], [time]" — Quick Mode
- "invoke skill se-lab-intake"

---

## Quick Mode — SE Is On a Call

When the SE types `[company], [feature], [time]` (e.g., `Verizon, Dynamic Tables, 3 hours`):

1. **Immediately output 3 lab options** (same format as lab-builder Quick Mode)
2. Run the **company research** phase in parallel (web search, industry context)
3. Ask only the **blocking questions** — things that prevent building if unknown

Do NOT run the full intake questionnaire during a live call.
Collect blocking answers, then do the rest async.

---

## Phase 1 — Company Research (run immediately, in parallel with options)

As soon as you have a company name, research:

### 1.1 Web search targets
```
"[Company] Snowflake" — any public case study or partnership
"[Company] data engineering" — known data stack
"[Company] [industry] challenges" — pain points for domain tailoring
"[Company] annual report" OR "[Company] investor day" — strategic data priorities
```

### 1.2 Industry context
Map the company to an industry domain. Use this to:
- Suggest synthetic data tables that feel real (see domain table in FRAMEWORK.md)
- Propose a hero question grounded in their actual business
- Identify which Snowflake features are most relevant to their industry

### 1.3 Research output block (include in intake doc)

```markdown
## Company Research: [Company Name]

**Industry:** [Telecom / Healthcare / Retail / Financial / etc.]
**Known data stack:** [any public info on tools/platforms they use]
**Snowflake relationship:** [case study? partner? prospect?]
**Key business problems (public):**
- [pain point 1 from public sources]
- [pain point 2]
**Suggested domain for synthetic data:** [specific — not generic. e.g. "5G tower metrics, subscriber throughput, CDR events" not just "IoT"]
**Suggested hero question options:**
- "[Business question 1 — from their actual domain]"
- "[Business question 2 — alternative angle]"
**Sources:** [URLs or "inferred from industry knowledge"]
```

---

## Phase 2 — Blocking Questions (must answer before building)

These are the inputs lab-builder cannot infer. Ask these directly — over Slack, email,
or on the call. Get answers before invoking lab-builder.

Present as a short checklist, not an interview:

```
Lab Intake: [Company] — [Feature]
SE: [SE name]  ·  Date: [date]

REQUIRED (blocking — can't build without these):

[ ] 1. What's the time available?
        □ 1 hour    □ 90 min    □ Half day (3 hr)    □ Full day    □ Multi-day

[ ] 2. Who is in the room?
        □ Data Engineers    □ Analysts    □ Business Users    □ Mixed
        Count: ___ participants

[ ] 3. Account type — which of these describes their Snowflake environment?
        □ Sandbox account (isolated, lab-only)
        □ DEV/lower environment (shared dev, not production)
        □ Production account with HOL schema isolated
        Note: The account EXISTS — we are provisioning within it, not creating it.

[ ] 4. Isolation pattern — DB or schema per participant?
        □ Schema-per-user (shared DB, each participant gets their own schema)
        □ Database-per-user (each participant gets their own pre-created DB)
        ⚠️  COMPANY/DBA DECIDES THIS — not the SE. Confirm with their DBA.

[ ] 5. Is the Cortex Code CLI already installed for participants?
        □ Yes — CLI is pre-installed and configured on participant machines
        □ No — participants need to install before the lab (adds ~20 min pre-work)
        □ Partially — some have it, some don't
        Note: If YES, Module 00 setup time drops from 25 min to 10 min.

[ ] 6. DBA contact: ___________________
        This person runs facilitator_setup.sql and creates participant users.
        SE verifies their work with grant_audit.sql before sending pre-work.

GOOD TO HAVE (ask if time permits, SE can research otherwise):

[ ] 7. What business question should participants be able to answer at the end?
        (Hero question — from discovery call. If blank, SE proposes from research.)

[ ] 8. Any Snowflake features they've already used?
        (Calibrates what to skip vs. what to show as new)

[ ] 9. Any specific data domain preferences?
        (e.g., "Use our network telemetry model" vs "generic is fine")
```

---

## Phase 3 — CLI Status Impact

This changes Module 00 materially. Record the answer from Question 5 and apply:

| CLI status | Module 00 structure | Duration |
|-----------|--------------------|---------| 
| **Pre-installed + configured** | Skip install steps. Go straight to connection test + data load. | ~10 min |
| **Not installed** | Full install + connection config + VPN warning + data load. | ~25 min |
| **Partially installed** | Keep install steps but mark as "skip if already done." | ~20 min |

**For enterprise team labs, CLI is typically pre-deployed.** The SE should confirm this
in intake, not assume. If it's pre-installed, the pre-work doc is much shorter — just
verify connection and confirm role access.

---

## Phase 4 — Generate the Intake Document

After collecting answers (blocking + research), generate a single markdown file:
`labs/<company-slug>-lab-intake.md`

This document is the **direct input to lab-builder**. The SE opens lab-builder and
pastes or references this file. Lab-builder reads it and skips Phase 0/0.5 (already done).

### Intake document format

```markdown
# Lab Intake: [Company Name] — [Feature] Lab
**SE:** [name]  ·  **Date:** [date]  ·  **Status:** Ready for lab-builder

---

## Session Parameters

| Field | Value |
|-------|-------|
| Company | [Company Name] |
| Feature | [Snowflake feature(s)] |
| Time available | [duration] |
| Session format | [N sessions × N hours] |
| Module count | [N modules] |
| Audience | [DE / Analyst / BU / Mixed] |
| Participant count | [N] |

---

## Account Configuration

| Field | Value |
|-------|-------|
| Account type | [Sandbox / DEV / Production-isolated] |
| Isolation pattern | [Schema-per-user / Database-per-user] |
| Isolation decided by | [DBA name / TBD] |
| CLI status | [Pre-installed / Needs install / Partial] |
| DBA contact | [name / email] |
| HOL role name | [HOL_ROLE or TBD — DBA confirms] |
| Warehouse | [COMPUTE_WH or as provided] |

---

## Company Research

**Industry:** [industry]
**Snowflake relationship:** [case study / partner / prospect / unknown]
**Key pain points (public):**
- [pain point 1]
- [pain point 2]

**Suggested synthetic data domain:** [specific — not generic]
*Example tables: [TABLE_1 (Ndesc), TABLE_2 (Ndesc), ...]*

**Hero question options:**
1. "[Best candidate from research]"
2. "[Alternative]"
**Selected hero question:** "[SE confirms this after discovery call]"

---

## Curriculum Plan (from Phase 0.5)

*Attach the confirmed option from the 3-option output, or write here:*

Session 1 (~[N] hours):
  Module 00 — Setup                                [N] min  [CLI: pre-installed / needs install]
  Module 01 — [title]                              [N] min
  Module 02 — [title + failure moment indicator]   [N] min  ← failure here
  Validate + Q&A                                   [N] min

Session 2 (~[N] hours):  [delete if single session]
  Module 03 — [title]                              [N] min
  Module 04 — [title / capstone]                   [N] min
  Final Validate + Wrap                            [N] min

Skipped modules: [list any standard modules omitted for time/audience]

---

## DBA Hand-Off Checklist

*SE sends this to the DBA contact after intake is complete:*

- [ ] Provision HOL_ROLE with grants per `facilitator_setup.sql`
- [ ] Create [N] participant users: [list or attach]
- [ ] Assign all users to HOL_ROLE
- [ ] Confirm warehouse [COMPUTE_WH] is running
- [ ] Confirm [account type] account is accessible at [URL]
- [ ] Isolation: [schema-per-user → GRANT CREATE SCHEMA ON DATABASE] / [db-per-user → create N databases]
- [ ] Cortex: GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE HOL_ROLE

*SE verifies with `grant_audit.sql` after DBA confirms.*

---

## Open Questions

*Things still needed before lab-builder can finish:*

- [ ] [Any unanswered intake question]
- [ ] [Hero question still TBD?]
- [ ] [DBA contact still unknown?]

---

## → Next Step

All blocking questions answered? Run:
\```
invoke skill lab-builder
\```
Reference this intake document. Lab-builder will skip Phase 0, 0.5, and Phase 1
questions that are already answered here.
```

---

## Phase 5 — Hand Off to lab-builder

When intake document is complete, tell the SE:

```
Intake complete for [Company] — [Feature] Lab.
Intake doc saved to: labs/[company-slug]-lab-intake.md

[N] open questions remaining: [list]
[or: All blocking questions answered — ready to build.]

To build the lab:
  invoke skill lab-builder

Lab-builder will read the intake doc and go straight to Phase 2 (Scaffold).
Estimated build time: ~30 minutes for a complete [N]-module lab.
```

---

## Key Rules (from framework and today's conversations)

1. **CLI pre-install**: Enterprise team labs typically have CLI pre-deployed. Confirm in intake — don't assume. Changes Module 00 duration significantly.

2. **Account exists**: The company has a sandbox or DEV account. We are provisioning within it, not creating it. "Account type" is about isolation level, not existence.

3. **Isolation is company's decision**: DB-per-user vs schema-per-user is decided by the company's DBA or security policy, not the SE. Intake records what they said — it does not recommend.

4. **DBA runs, SE verifies**: SE sends `facilitator_setup.sql` to DBA. SE runs `grant_audit.sql` to verify. SE does not run provisioning on customer accounts.

5. **Research makes labs land**: Generic synthetic data (just "DEVICES" or "ORDERS") is a missed opportunity. Research the company's domain and make the data feel like their world.

6. **Hero question from them, not us**: The best hero question comes from the company's own words during discovery — "We want to know X." That becomes the lab's final module target.
