### PHASE 3: UC360 Data (If Available)

```sql
SELECT 
    uc.account_name, uc.uc_id, uc.uc_number, uc.uc_name,
    uc.uc_acv, uc.uc_stage, uc.uc_decision_date,
    uc.uc_meddpicc_champion as uc_champion,
    uc.se_name as uc_se_owner,
    uc.uc_se_comments, uc.uc_next_step, 
    uc.uc_risk_level, uc.uc_risk_description,
    uc.uc_workloads, uc.uc_technical_campaign, uc.uc_status,
    uc.uc_meddpicc_economic_buyer, uc.owner_name,
    uai.ai_analysis, uai.se_notes_summary
FROM temp.irina.uc_analysis_view uc
LEFT JOIN temp.irina.uc_ai_analysis uai ON uc.uc_id = uai.uc_id
WHERE UPPER(uc.account_name) LIKE UPPER('%{ACCOUNT_NAME}%')
ORDER BY uc.uc_last_modified_date DESC
LIMIT 100;
```

---

### PHASE 4: Snow Owl Documents

```sql
SELECT DOCUMENT_TYPE, DOCUMENT_NUMBER, LEFT(CONTENT, 10000) as CONTENT
FROM TEMP.SNOW_OWL_DATA.CUSTOMER_DOCUMENTS 
WHERE CUSTOMER_NAME = '{ACCOUNT_NAME}'
ORDER BY CAST(DOCUMENT_NUMBER AS INT);
```

**Priority Document Types:**
1. Customer_Stakeholder_Map - Org structure and key contacts
2. Customer_Org_Chart - Hierarchical view
3. Internal_Champions_Radar - Champions and detractors
4. Industry_Analysis - Market context
5. Competitor_Landscape - Competitive positioning
6. Board_Priorities - Executive priorities
7. AI_Strategy - Technology direction
8. Executive_Research - Leadership backgrounds
9. Risk_Signals_Transformation_Triggers - Warning signs
10. Technology_Stack - Current architecture

---

### PHASE 5: Web Research (Comprehensive)

Execute these searches in parallel:

#### 5.1: Annual Report / 10-K
```
WebSearch: "{ACCOUNT_NAME}" annual report 2025 investor relations 10-K
```
Extract:
- Revenue and growth metrics
- Strategic priorities
- Technology investments
- Risk factors

#### 5.2: Earnings Calls
```
WebSearch: "{ACCOUNT_NAME}" earnings call transcript Q4 2025 Q3 2025
```
Extract:
- CEO/CFO quotes on strategy
- Technology initiatives mentioned
- Competitive commentary
- Growth plans

#### 5.3: Press Releases & News
```
WebSearch: "{ACCOUNT_NAME}" press release technology data AI transformation 2025 2026
```
Extract:
- Technology partnerships announced
- Digital transformation initiatives
- Data platform investments

#### 5.4: LinkedIn - Executive Team
```
WebSearch: site:linkedin.com "{ACCOUNT_NAME}" Chief Data Officer VP Data Engineering Head of Analytics
```
Extract:
- Key data/analytics executives
- Reporting structure
- Career backgrounds
- Recent posts about data strategy

#### 5.5: LinkedIn - Company Updates
```
WebSearch: site:linkedin.com "{ACCOUNT_NAME}" company Snowflake data cloud
```
Extract:
- Company mentions of Snowflake
- Data-related initiatives
- Employee growth in data roles

#### 5.6: Job Postings - Data/Analytics Roles (CRITICAL)

**PURPOSE**: Job postings reveal where the customer is heading strategically and what technology challenges they face. This is a key indicator of future Snowflake opportunities.

Execute multiple job posting searches:

```
WebSearch: site:linkedin.com/jobs "{ACCOUNT_NAME}" data engineer Snowflake SQL cloud
WebSearch: site:linkedin.com/jobs "{ACCOUNT_NAME}" data scientist machine learning AI analytics
WebSearch: site:linkedin.com/jobs "{ACCOUNT_NAME}" data architect cloud platform migration
WebSearch: site:greenhouse.io OR site:lever.co "{ACCOUNT_NAME}" data engineering analytics
WebSearch: "{ACCOUNT_NAME}" careers data platform engineer cloud warehouse 2025 2026
```

**Extract and Analyze:**
- **Technology Stack Requirements**: What tools are listed? (Snowflake, Databricks, Spark, dbt, Airflow, etc.)
- **Team Growth Signals**: How many data roles are open? What seniority levels?
- **Strategic Direction Indicators**: Are they hiring for AI/ML? Cloud migration? Real-time streaming?
- **Skill Gaps**: What skills are they struggling to find? (Could indicate pain points)
- **Competitor Mentions**: Are they requiring Databricks, BigQuery, or Redshift experience?
- **Snowflake Opportunities**: Jobs mentioning Snowflake = expansion opportunity. Jobs NOT mentioning Snowflake but seeking cloud data skills = net new opportunity.

**Job Posting Analysis Framework:**

| Signal | Implication | Snowflake Action |
|--------|-------------|------------------|
| Multiple "Data Engineer" postings | Team expansion, platform scaling | Capacity planning, PS&T engagement |
| "Cloud Migration" mentioned | Legacy platform displacement | Migration MAP credits, competitive positioning |
| "Machine Learning Engineer" roles | AI/ML investment | Cortex, Snowpark ML positioning |
| "Data Architect" hiring | Platform modernization | Architecture workshop, future state design |
| "Real-time" or "Streaming" keywords | Event-driven needs | Snowpipe Streaming, Dynamic Tables |
| "Databricks" requirement | Competitive threat | DCR differentiation, Iceberg interoperability |
| "Data Governance" roles | Compliance/security focus | Trust Center, Classification, Governance features |

**Document in Word Report:**
- List all relevant job postings found with URLs and dates
- Summarize technology stack requirements across all postings
- Identify hiring trends and what they mean for Snowflake strategy
- Map job requirements to Snowflake capabilities and white space

#### 5.7: Glassdoor/Industry News
```
WebSearch: "{ACCOUNT_NAME}" data platform technology stack Glassdoor reviews
WebSearch: "{ACCOUNT_NAME}" engineering culture data team reviews
```
Extract:
- Employee sentiment on data tools
- Technology direction indicators
- Engineering culture and team dynamics
- Pain points mentioned by employees

---

### PHASE 5.5: Similar Customer Use Case Research (CRITICAL)

**PURPOSE**: Identify successful use cases at other Snowflake customers in the same industry/vertical that could be applicable to the target account. This provides proven playbooks and reference stories.

#### Step 5.5.1: Identify Similar Customers

Query for other customers in the same industry/subindustry:

```sql
SELECT DISTINCT 
    a.SALESFORCE_ACCOUNT_ID,
    a.NAME,
    a.INDUSTRY,
    a.SUBINDUSTRY,
    a.ANNUAL_REVENUE,
    d.ACCOUNT_TIER,
    d.TYPE,
    d.SUB_TYPE
FROM SALES.RAVEN.ACCOUNT a
LEFT JOIN SALES.RAVEN.D_SALESFORCE_ACCOUNT_CUSTOMERS d 
    ON a.SALESFORCE_ACCOUNT_ID = d.SALESFORCE_ACCOUNT_ID
WHERE a.INDUSTRY = '{TARGET_ACCOUNT_INDUSTRY}'
  AND a.SALESFORCE_ACCOUNT_ID != '{TARGET_SALESFORCE_ACCOUNT_ID}'
  AND d.TYPE = 'Customer'
ORDER BY a.ANNUAL_REVENUE DESC NULLS LAST
LIMIT 20;
```

#### Step 5.5.2: Find Successful Use Cases at Similar Customers

Query for PRODUCTION use cases at similar industry customers:

```sql
SELECT 
    a.NAME as SIMILAR_CUSTOMER,
    a.INDUSTRY,
    a.SUBINDUSTRY,
    uc.USE_CASE_NAME,
    uc.USE_CASE_DESCRIPTION,
    uc.USE_CASE_STAGE,
    uc.USE_CASE_STATUS,
    uc.USE_CASE_ACV,
    uc.WORKLOADS,
    uc.INDUSTRY_USE_CASE,
    uc.PARTNERS,
    uc.GO_LIVE_DATE,
    uc.MEDDPICC_IDENTIFY_PAIN,
    uc.MEDDPICC_METRICS
FROM SALES.RAVEN.ACCOUNT a
JOIN SALES.RAVEN.SDA_USE_CASE_VIEW uc 
    ON a.SALESFORCE_ACCOUNT_ID = uc.SALESFORCE_ACCOUNT_ID
WHERE a.INDUSTRY = '{TARGET_ACCOUNT_INDUSTRY}'
  AND a.SALESFORCE_ACCOUNT_ID != '{TARGET_SALESFORCE_ACCOUNT_ID}'
  AND uc.USE_CASE_STATUS = 'Production'
  AND uc.USE_CASE_ACV > 0
ORDER BY uc.USE_CASE_ACV DESC
LIMIT 50;
```

#### Step 5.5.3: Identify Transferable Use Cases

For each successful use case found at similar customers, evaluate:

**Transferability Criteria:**
1. **Problem Alignment**: Does target customer have similar pain points?
2. **Technical Fit**: Does target customer have required data sources?
3. **Business Value**: Would this use case address stated priorities?
4. **Competitive Urgency**: Is a competitor solving this problem today?
5. **Stakeholder Match**: Are there equivalent stakeholders at target?

**Use Case Comparison Matrix:**

| Similar Customer | Use Case | ACV | Pain Solved | Target Has Pain? | Recommendation |
|-----------------|----------|-----|-------------|------------------|----------------|
| {Company A} | {Use Case 1} | ${ACV} | {Pain} | Yes/No | High/Medium/Low |
| {Company B} | {Use Case 2} | ${ACV} | {Pain} | Yes/No | High/Medium/Low |

#### Step 5.5.4: Reference Story Compilation

For HIGH recommendation use cases, compile:

- **Customer Reference**: Company name, industry, size
- **Use Case Details**: What they built, what problem it solved
- **Business Value**: Metrics achieved, ROI demonstrated
- **Technical Stack**: Snowflake features used, partners involved
- **Timeline**: How long to implement, when went to production
- **Key Stakeholders**: Who championed it, who approved budget
- **Applicability to Target**: Why this is relevant, what to adapt

**Include in Word Document:**
- Full list of similar customer use cases analyzed
- Detailed comparison of each to target account
- Top 3-5 recommended use cases with full rationale
- Reference contact information (if available)
- Suggested approach for introducing these use cases

#### Step 5.5.5: Industry-Specific Successful Patterns

For Media & Entertainment specifically, search for proven patterns:

```sql
SELECT 
    a.NAME,
    a.SUBINDUSTRY,
    uc.USE_CASE_NAME,
    uc.WORKLOADS,
    uc.USE_CASE_ACV,
    uc.PARTNERS,
    uc.MEDDPICC_IDENTIFY_PAIN
FROM SALES.RAVEN.ACCOUNT a
JOIN SALES.RAVEN.SDA_USE_CASE_VIEW uc 
    ON a.SALESFORCE_ACCOUNT_ID = uc.SALESFORCE_ACCOUNT_ID
WHERE a.INDUSTRY = 'Media & Entertainment'
  AND uc.USE_CASE_STATUS = 'Production'
  AND uc.WORKLOADS LIKE '%{WORKLOAD_PATTERN}%'  -- e.g., 'Data Clean Room', 'AI', 'Streaming'
ORDER BY uc.USE_CASE_ACV DESC
LIMIT 20;
```

**Key M&E Use Case Patterns to Search:**
- Data Clean Room implementations (for AdSales)
- Streaming/CDN analytics (for Peacock-like services)
- Content analytics and recommendations (for Studios)
- Audience measurement and attribution (for Advertising)
- Real-time gaming analytics (for Game Publishers)
- Fan engagement and personalization (for Theme Parks)

---
