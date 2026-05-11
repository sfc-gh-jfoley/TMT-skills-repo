### PHASE 6: Analysis & Synthesis

#### Step 6.1: Calculate Lookback FY Performance (DYNAMIC)

**Use the fiscal year variables calculated at the start of execution.**

From consumption and TACV queries:
- **Lookback FY Consumption**: Sum from Step 2.5 (LOOKBACK_FY_REVENUE)
- **Prior FY Consumption**: Sum from Step 2.5 (PRIOR_FY_REVENUE)
- **YOY Growth %**: ((Lookback FY - Prior FY) / Prior FY) * 100
- **Lookback FY TACV Won**: From Step 2.10 (filter by FISCAL_YEAR = LOOKBACK_FY)
- **Prior FY TACV Won**: From Step 2.10 (filter by FISCAL_YEAR = LOOKBACK_FY - 1)
- **TACV Growth %**: ((Lookback FY - Prior FY) / Prior FY) * 100

#### Step 6.2: Deep White Space Analysis

**Snowflake Complete Capability Matrix:**

| Category | Use Case | Features | Customer Has? | Priority |
|----------|----------|----------|---------------|----------|
| **AI/ML** | Conversational AI | Cortex Search, Cortex Analyst, Copilot | | |
| **AI/ML** | Machine Learning | ML Functions, Snowpark ML, SPCS | | |
| **AI/ML** | Agents & Orchestration | Agents API, SI Agent Orchestration | | |
| **AI/ML** | Unstructured Data | Document AI, Cortex LLM, SPCS GPU | | |
| **Analytics** | Applied Analytics | Dynamic Tables, Materialized Views, Time Series, GEO | | |
| **Analytics** | Business Intelligence | Streamlit, Snowsight Dashboard | | |
| **Analytics** | Lakehouse | Iceberg Tables, Open Catalog | | |
| **Apps** | External Collaboration | Data Clean Room, External Sharing | | |
| **Apps** | Marketplace | Data Products, Native Apps | | |
| **Apps** | Build | Hybrid Tables, Unistore | | |
| **Data Eng** | Ingestion | Snowpipe, Snowpipe Streaming, Openflow, Connectors | | |
| **Data Eng** | Transformation | Tasks, Streams, Dynamic Tables, dbt | | |
| **Data Eng** | Iceberg | Iceberg DML, Iceberg Catalog | | |
| **Platform** | Governance | Trust Center, Classification, Lineage, DQ | | |
| **Platform** | Observability | Alerts, Logging, Event Tables | | |
| **Platform** | Cost | Query Costing, Warehouse Utilization | | |

**White Space Identification:**
1. Compare A360 feature adoption against matrix
2. Identify competitive displacement opportunities from use case incumbents
3. Map to customer pain points from MEDDPICC
4. Align with industry-specific use cases (M&E matrix above)
5. Prioritize by: business value, technical fit, competitive pressure

#### Step 6.3: SWOT Analysis

Generate from collected data:

**STRENGTHS** (from Raven + UC360):
- Production use cases generating revenue
- Strong partner integrations (credits > 1000)
- Active feature adoption
- Executive sponsorship indicators
- Multi-year renewal secured

**WEAKNESSES** (from pain points + risks):
- MEDDPICC documented pain points
- Use case risks flagged (HIGH/MEDIUM)
- Stakeholder engagement gaps
- Technical blockers identified
- Competitive displacement risk

**OPPORTUNITIES** (from white space + web):
- White space feature gaps
- Strategic priorities from earnings calls
- Industry trends matching Snowflake capabilities
- New stakeholders from LinkedIn
- Job postings indicating growth

**THREATS** (from competitors + market):
- Incumbent vendors in use cases
- Competitive mentions in opportunities
- Technology disruption risks
- Budget pressures from earnings calls
- Organizational changes

#### Step 6.4: Traffic Light Assessment

**START (Green):**
- New features from white space analysis
- New stakeholders from LinkedIn/Snow Owl
- Use cases aligned to strategic priorities
- Competitive displacement opportunities

**STOP (Red):**
- Approaches with low MEDDPICC scores
- Features with no adoption after 6+ months
- Stakeholders showing no engagement
- Use cases marked as risks

**CONTINUE (Yellow):**
- Production use cases with growth
- Strong partner relationships
- Engaged champions from Snow Owl
- Successful engagement patterns

#### Step 6.5: White Whale Use Case Selection

Identify ONE high-value opportunity based on:
1. Highest ACV potential from pipeline/white space
2. Alignment to customer strategic priorities
3. Clear champion and economic buyer
4. Technical feasibility
5. Competitive urgency

Document:
- **WHO**: Target stakeholder, BU, title, engagement history
- **WHAT**: Specific use case, features, technical scope
- **WHY**: Business value, strategic alignment, pain point addressed
- **HOW**: Implementation approach, timeline, resources needed
- **SUPPORT NEEDED**: Executive engagement, PS&T, partners, specialists

#### Step 6.6: Org Chart & Relationship Mapping

Build from Snow Owl + LinkedIn + Web:

**Structure by Business Unit:**
- Extract BU names from use cases and stakeholders
- Map stakeholders to each BU
- Identify decision makers vs influencers

**Engagement Flags:**
- Strong (Green): Active champion, recent engagement, positive sentiment
- Medium (Yellow): Some engagement, neutral sentiment
- Weak (Red): No engagement, unknown, or negative indicators

**Key Relationship Targets:**
- Priority stakeholders to engage
- Internal resources to involve (executives, specialists)
- Engagement timeline by quarter

---
