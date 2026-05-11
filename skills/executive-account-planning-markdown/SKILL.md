---
name: executive-account-planning-markdown
description: "Generate comprehensive annual account planning Markdown documents for Snowflake executives. Dynamically determines fiscal years based on current date (Snowflake FY runs Feb-Jan). Pulls data from Raven, UC360, Snow Owl, web research (LinkedIn, job postings, earnings calls, 10-Ks, press releases), Raven GTM Assistant, and similar customer use cases. Outputs comprehensive Markdown writeup with full research findings. Triggers: account plan, annual planning, executive account review, account strategy, run this analysis."
---

# Executive Account Planning Skill

Generate comprehensive annual account planning deliverables for Snowflake executives.

**Connection**: `snowhouse` | **Role**: `SALES_RAVEN_RO_RL`

---

## CRITICAL: Fiscal Year Calculation

**Snowflake Fiscal Year runs February 1 through January 31.**

| Calendar Date | Current FY | Lookback FY | Planning FY |
|---------------|-----------|-------------|-------------|
| Feb 2026 - Jan 2027 | FY27 | FY26 | FY27 |
| Feb 2025 - Jan 2026 | FY26 | FY25 | FY26 |
| Feb 2024 - Jan 2025 | FY25 | FY24 | FY25 |

**ALWAYS calculate fiscal years dynamically at execution time:**

```python
from datetime import datetime

today = datetime.now()
current_month = today.month
current_year = today.year

# Snowflake FY starts in February
# If we're in Jan, we're still in the previous FY
if current_month == 1:
    CURRENT_FY = current_year  # e.g., Jan 2026 = FY26
    LOOKBACK_FY = current_year - 1  # FY25
    PLANNING_FY = current_year  # Planning for FY26
else:
    CURRENT_FY = current_year + 1  # e.g., Feb 2026 = FY27
    LOOKBACK_FY = current_year  # FY26
    PLANNING_FY = current_year + 1  # Planning for FY27

# Date ranges for queries
LOOKBACK_START = f"{LOOKBACK_FY - 1}-02-01"  # e.g., 2025-02-01 for FY26
LOOKBACK_END = f"{LOOKBACK_FY}-01-31"  # e.g., 2026-01-31 for FY26
PRIOR_YEAR_START = f"{LOOKBACK_FY - 2}-02-01"  # e.g., 2024-02-01 for FY25
PRIOR_YEAR_END = f"{LOOKBACK_FY - 1}-01-31"  # e.g., 2025-01-31 for FY25

print(f"Current Date: {today.strftime('%Y-%m-%d')}")
print(f"Lookback Year: FY{LOOKBACK_FY} ({LOOKBACK_START} to {LOOKBACK_END})")
print(f"Planning Year: FY{PLANNING_FY}")
```

**Use these variables throughout all queries and outputs instead of hardcoded FY26/FY27.**

---

## Output Requirements

**MANDATORY**: This skill produces a comprehensive Markdown writeup for every account plan.

**Output**: Markdown Writeup (.md) - Comprehensive research document with full analysis, citations, and deep-dive findings

**NOTE**: PowerPoint generation is handled by a separate skill. This skill focuses on gathering all data and producing the detailed Markdown analysis document.

The Markdown writeup captures detailed research including:
- Full web research findings with source URLs and quotes
- Complete use case inventory with all MEDDPICC details
- Detailed stakeholder profiles from LinkedIn research
- Job posting analysis with technology stack implications
- Similar customer use case comparisons with transferable insights
- Comprehensive competitive landscape analysis
- Full earnings call and 10-K excerpts with strategic implications

---

## CRITICAL: DO NOT SKIP ANY REQUIRED CONTENT

**THE FOLLOWING CHECKLIST IS MANDATORY. DO NOT SKIP ANY ITEM.**

If data is not available for any item:
1. First, conduct additional research (web search, alternative Raven queries) to find the information
2. If still not available after exhaustive research, explicitly state in both the slide AND the markdown:
   - "**[DATA NOT AVAILABLE]**: {item name} - Unable to find data after searching {sources attempted}. Recommend {action to obtain this data}."
3. NEVER silently omit a required section

### FY{LOOKBACK_FY} Final Numbers (REQUIRED - DO NOT SKIP)

| Item | Required? | Data Source | Fallback if Missing |
|------|-----------|-------------|---------------------|
| Consumption total | **MANDATORY** | A360_DAILY_ACCOUNT_PRODUCT_CATEGORY_REVENUE_VIEW | State "No consumption data" |
| Consumption growth % YOY | **MANDATORY** | Calculate from above | State "Cannot calculate - prior year missing" |
| TACV total | **MANDATORY** | SDA_OPPORTUNITY_VIEW | State "No TACV data" |
| TACV growth % YOY | **MANDATORY** | Calculate from above | State "Cannot calculate - prior year missing" |
| High-level commentary on the year | **MANDATORY** | Synthesize from all data | AI-generate summary of available data |
| Key wins and accomplishments | **MANDATORY** | Use cases, opportunities | List production use cases as wins |
| SWOT Analysis (4-quadrant visual) | **MANDATORY** | Synthesize from all data | Generate based on available signals |
| Traffic Light: Start, Stop, Continue | **MANDATORY** | Synthesize from all data | Generate recommendations from data |

### FY{PLANNING_FY} Plan (REQUIRED - DO NOT SKIP)

| Item | Required? | Data Source | Fallback if Missing |
|------|-----------|-------------|---------------------|
| Consumption & TACV goals | **MANDATORY** | User input or calculate 15-25% growth | State assumed growth rate |
| Renewal strategy/plan | **MANDATORY** | SDA_OPPORTUNITY_VIEW renewals | State "No renewals in FY{PLANNING_FY}" if none |
| Key Customer Strategies (annual report sourced) | **MANDATORY** | Web: 10-K, earnings | Search multiple sources |
| Priorities | **MANDATORY** | Earnings calls, press releases | Synthesize from available data |
| Identified challenges/needs | **MANDATORY** | MEDDPICC pain, web research | List all documented pain points |
| White Whale Use Case | **MANDATORY** | Pipeline + white space analysis | Identify highest ACV opportunity |
| - Who (target stakeholder) | **MANDATORY** | Snow Owl, LinkedIn | State "Champion TBD" |
| - What (use case details) | **MANDATORY** | Use case data | Describe from pipeline |
| - Why (business value) | **MANDATORY** | MEDDPICC metrics | State value proposition |
| - How (approach) | **MANDATORY** | Synthesize | Recommend approach |
| - Support needed | **MANDATORY** | Analysis | List resources needed |
| Secondary Use Cases (up to 2) | **MANDATORY** | Pipeline analysis | Pick top 2 by ACV |
| **Org Chart / Relationship Mapping** | **MANDATORY** | Snow Owl, LinkedIn | Build from available data |
| - Org chart by BU/team | **MANDATORY** | Stakeholder map | Web research if missing |
| - Engagement flags (strong/medium/weak) | **MANDATORY** | Engagement history | Default to "Unknown" with note |
| - Key relationship targets | **MANDATORY** | Analysis | Identify from roles |
| - How/when to engage | **MANDATORY** | Planning | Recommend timeline |
| - Who to involve internally | **MANDATORY** | Account team | List SF resources |
| **Strategy for Leveraging (ALL SUB-ITEMS REQUIRED):** | | | |
| - PS&T strategy | **MANDATORY** | Services data | Recommend engagement |
| - Partners (2-3 strategic) | **MANDATORY** | PARTNER_CONNECTIONS_VIEW | List top partners by credits |
| - Partner focus areas | **MANDATORY** | Analysis | Map to use cases |
| - FMM/ABM/SDR strategy | **MANDATORY** | Persona analysis | Recommend targets |
| - Key personas to target | **MANDATORY** | LinkedIn, org chart | List by title |
| - BUs to target | **MANDATORY** | Use case mapping | Prioritize by opportunity |
| - BVE strategy | **MANDATORY** | VALUE_ENGINEERING_ENGAGEMENT_TYPE | Recommend ROI analysis |
| Critical meeting/event priorities | **MANDATORY** | Planning | |
| - CEC | **MANDATORY** | Recommend timing | Q-level suggestion |
| - Snowcamps | **MANDATORY** | Recommend timing | Q-level suggestion |
| - Monthly/Quarterly reviews | **MANDATORY** | NEXT_QBR_DATE_C | Schedule recommendation |
| - Specific timing, who, what | **MANDATORY** | Planning | Detail each event |
| Current State Architecture | **MANDATORY** | TECH_STACK, partners | Diagram from available data |
| Future State Architecture | **MANDATORY** | White space analysis | Show proposed additions |

---

## Intelligence Sources

- **Raven** (direct SQL queries)
- **Raven GTM Assistant** (agent API for enriched analysis)
- **UC360** (use case health and AI analysis)
- **Snow Owl** (customer documents and stakeholder maps)
- **Web Research** (see comprehensive list below)
- **Similar Customer Use Cases** (successful use cases from same industry/vertical)
- **M&E Industry Intelligence** (use case and persona mapping)

---

## Anti-Hallucination Protocol

**CRITICAL RULES:**
- ONLY include data explicitly found in Raven/UC360/Snow Owl queries or verified web sources
- If a field is NULL/empty, state "No data available" - NEVER infer
- For each data point, cite the source table/column or URL
- ALL SQL queries are READ-ONLY (SELECT only)
- Web-sourced content must cite the URL
- LinkedIn/job posting data must be dated and sourced

---

**Load** `references/web-research-sources.md` for all web search categories and M&E industry intelligence matrix.

---

## Session Prerequisites

Before any operation:

1. **Set Snowflake Role:**
```sql
USE ROLE SALES_RAVEN_RO_RL;
```

2. **Load Reference Files** (on demand per phase):
- `references/web-research-sources.md` - Web search categories + M&E matrix
- `references/data-collection-queries.md` - Phase 2 SQL queries
- `references/external-data-collection.md` - UC360, Snow Owl, web research, similar customers
- `references/analysis-synthesis.md` - Phase 6 analysis framework
- `references/markdown-template.md` - Phase 7 output template
- `references/mermaid-diagrams-inline.md` - Phase 7.5 diagram generation

---

## Workflow

### PHASE 1: Account & User Identification

#### Step 1.1: Identify User (if provided)

If user identifies themselves (e.g., "I am Alexandra Painter"):

```sql
SELECT 
    EMPLOYEE_ID,
    EMPLOYEE_NAME,
    BUSINESS_TITLE,
    MANAGER_NAME,
    PRIMARY_WORK_EMAIL,
    DEPARTMENT,
    COST_CENTER_NAME
FROM SALES.RAVEN.RAVEN_EMPLOYEE 
WHERE UPPER(EMPLOYEE_NAME) LIKE UPPER('%{USER_NAME}%')
LIMIT 5;
```

Find accounts owned by or associated with this user:
```sql
SELECT 
    a.SALESFORCE_ACCOUNT_ID,
    a.NAME,
    a.INDUSTRY,
    a.ANNUAL_REVENUE,
    d.SALESFORCE_OWNER_NAME,
    d.LEAD_SALES_ENGINEER_NAME,
    d.SE_DIRECTOR_NAME,
    d.ACCOUNT_TIER
FROM SALES.RAVEN.ACCOUNT a
LEFT JOIN SALES.RAVEN.D_SALESFORCE_ACCOUNT_CUSTOMERS d 
    ON a.SALESFORCE_ACCOUNT_ID = d.SALESFORCE_ACCOUNT_ID
WHERE UPPER(d.SALESFORCE_OWNER_NAME) LIKE UPPER('%{USER_NAME}%')
   OR UPPER(d.LEAD_SALES_ENGINEER_NAME) LIKE UPPER('%{USER_NAME}%')
   OR UPPER(d.SALES_ENGINEER_ACCOUNT_TEAM) LIKE UPPER('%{USER_NAME}%')
ORDER BY a.ANNUAL_REVENUE DESC NULLS LAST
LIMIT 50;
```

#### Step 1.2: Identify Accounts

If account name(s) specified, search:
```sql
SELECT DISTINCT 
    a.SALESFORCE_ACCOUNT_ID,
    a.NAME,
    a.INDUSTRY,
    a.ANNUAL_REVENUE,
    d.SALESFORCE_OWNER_NAME,
    d.LEAD_SALES_ENGINEER_NAME,
    d.ACCOUNT_TIER,
    d.COUNTRY
FROM SALES.RAVEN.ACCOUNT a
LEFT JOIN SALES.RAVEN.D_SALESFORCE_ACCOUNT_CUSTOMERS d 
    ON a.SALESFORCE_ACCOUNT_ID = d.SALESFORCE_ACCOUNT_ID
WHERE LOWER(a.NAME) LIKE LOWER('%{ACCOUNT_NAME}%')
LIMIT 20;
```

If multiple matches, present list and ask user to confirm.

---

### PHASE 2: Comprehensive Data Collection

**Load** `references/data-collection-queries.md`

Execute queries in parallel where possible. Run Step 2.1 first to get SALESFORCE_ACCOUNT_ID, then execute 2.2-2.23 in parallel. Includes Raven queries (account basics, team, use cases, pain points, consumption, features, partners, TACV, pipeline, renewals) and Account Manager Perspective enrichment queries (win/loss, velocity, champions, risk, services, competitive, tenure, feature adoption, strategy notes, Raven GTM Assistant API).

---

### PHASE 3-5.5: External Data Collection

**Load** `references/external-data-collection.md`

Covers UC360 data, Snow Owl documents (10 priority document types), comprehensive web research (10-K, earnings, press, LinkedIn, job postings, Glassdoor), and similar customer use case research with transferability assessment.

**Load** `references/web-research-sources.md` for the complete search query templates across all 6 categories.

---

### PHASE 6: Analysis & Synthesis

**Load** `references/analysis-synthesis.md`

Steps: (6.1) Calculate lookback FY performance, (6.2) Deep white space analysis against Snowflake capability matrix, (6.3) SWOT analysis, (6.4) Traffic Light assessment, (6.5) White Whale use case selection (WHO/WHAT/WHY/HOW/SUPPORT), (6.6) Org chart and relationship mapping.

---

### PHASE 7: Markdown Writeup Generation (MANDATORY)

**Load** `references/markdown-template.md`

Generate a single Markdown file with 14 sections: Executive Summary, FY Performance, Account Overview, Stakeholder Analysis, Use Case Inventory, Web Research Findings, Job Posting Analysis, Similar Customer Use Cases, White Space Analysis, Strategy & Goals, Engagement Strategy, Competitive Landscape, Risk Assessment, Data Sources & Citations.

Save as: `{ACCOUNT_NAME}_FY{PLANNING_FY}_Account_Plan_Research_{DATE}.md`

---

### PHASE 7.5: Mermaid Diagram Generation (OPTIONAL)

**Load** `references/mermaid-diagrams-inline.md`

Generate architecture diagrams, org charts, and timelines using Mermaid for embedding in the Markdown document. Includes HTML template, 5 diagram types (current state, future state, org chart, timeline, partner ecosystem), and PNG export script.

---

### PHASE 8: Present Results

Provide comprehensive summary:

```
Account Plan Generated Successfully

Files Created:
- Markdown: {md_output_path}

FY{LOOKBACK_FY} Performance Summary:
- Consumption: ${LOOKBACK_FY_CONSUMPTION:,.0f} ({YOY_GROWTH:+.1f}% YOY)
- TACV Won: ${LOOKBACK_FY_TACV:,.0f} ({TACV_GROWTH:+.1f}% YOY)
- Use Cases: {USE_CASE_COUNT} total, {PRODUCTION_COUNT} in production

FY{PLANNING_FY} Targets:
- Consumption Goal: ${PLANNING_FY_CONSUMPTION_GOAL:,.0f}
- White Whale: {WHITE_WHALE_NAME} - ${WHITE_WHALE_ACV:,.0f}

Content Completeness Check:
- [ ] All FY{LOOKBACK_FY} metrics included
- [ ] SWOT Analysis present
- [ ] Traffic Light present
- [ ] White Whale with WHO/WHAT/WHY/HOW/SUPPORT
- [ ] Secondary Use Cases (2)
- [ ] Org Chart with engagement flags
- [ ] All leverage strategies (PS&T, Partners, FMM, BVE)
- [ ] Critical meetings with timing
```

---

## Error Handling

| Issue | Resolution |
|-------|------------|
| No Raven data | Inform user, proceed with web research |
| No Snow Owl documents | Use LinkedIn/web for stakeholder data |
| No UC360 data | Use Raven SDA_USE_CASE_VIEW |
| Web search fails | Note limitation, proceed with available data |
| Empty query results | State "[DATA NOT AVAILABLE]", explain gap, suggest how to obtain |
| Missing checklist item | DO NOT SKIP - either find data or explicitly state unavailable |

---

## Output Summary

When complete, the skill produces:

| Output | Format | Purpose |
|--------|--------|---------|
| **Markdown Writeup** | .md | Deep research & analysis |

**NOTE**: PowerPoint generation is handled by a separate skill (`pptx`). This skill focuses on comprehensive data gathering and Markdown document generation.

