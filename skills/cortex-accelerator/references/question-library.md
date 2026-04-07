# Question Library

Targeted question templates for Phase 4. Use only for gaps still open after BI
tool intake. Max 15 questions per session. Always show evidence, offer choices,
state the consequence of skipping.

## Question Structure

Every question follows this pattern:
```
CONTEXT:     Here's what we observed (evidence)
HYPOTHESIS:  Here's what we think it means
CONSEQUENCE: Here's what happens if we're wrong or you skip
QUESTION:    Confirm / correct / choose
```

---

## Q-TYPE 1: Domain Classification

Use when tables cluster ambiguously across multiple domains.

```
We see these tables queried together frequently but they don't map
cleanly to any domain we identified:

  [TABLE_A], [TABLE_B], [TABLE_C], [TABLE_D]

  Example query: SELECT a.rep_id, SUM(b.quota_target)
                 FROM [TABLE_A] a JOIN [TABLE_B] b ON a.id = b.ref_id

Hypothesis: These look like Sales Operations / compensation data.
Consequence: If wrong, they'll pollute an unrelated semantic view
  or be excluded entirely.

Which domain do these belong to?
  [ Sales Operations ]  [ Finance ]  [ HR ]  [ Marketing ]
  [ Split across domains — I'll specify ]  [ Exclude — they're staging ]
```

---

## Q-TYPE 2: Entity Golden Record

Use when multiple tables appear to contain the same entity.

```
We found [N] tables that appear to contain [entity] data:

  [TABLE_1]  ([ROW_COUNT_1] rows, [USER_COUNT_1] users querying it)
  [TABLE_2]  ([ROW_COUNT_2] rows, [USER_COUNT_2] users querying it)
  [TABLE_3]  ([ROW_COUNT_3] rows, [USER_COUNT_3] users querying it)

Hypothesis: [TABLE_1] is your system of record (most users, lowest error rate).
Consequence: If wrong, entity joins will resolve to the wrong table
  and cross-domain joins may silently return incorrect results.

Which is the authoritative [entity] record?
  [ TABLE_1 ]  [ TABLE_2 ]  [ TABLE_3 ]
  [ They represent different things — I'll explain ]
  [ We have an MDM mapping table — I'll point you at it ]
```

---

## Q-TYPE 3: Metric Disambiguation

Use when numeric columns used in aggregations have cryptic names.

```
Column [COLUMN_NAME] in [TABLE_NAME] appears in SUM() [N] times
across [Q] queries over the last 30 days. Example:

  SELECT region, SUM([COLUMN_NAME]) as total
  FROM [TABLE_NAME]
  GROUP BY region

Hypothesis: This is a [revenue / amount / cost] measure.
Consequence: If wrong, users will see "[COLUMN_NAME]" as a dimension
  label, or the metric will be misclassified.

What does [COLUMN_NAME] represent?
  [ Net revenue (after discounts/refunds) ]
  [ Gross revenue (before deductions) ]
  [ Cost or expense — not revenue ]
  [ Order/transaction amount ]
  [ A flag or indicator (numeric but not a true measure) ]
  [ Something else — I'll describe it ]
```

---

## Q-TYPE 4: Canonical Key

Use when the same entity is referenced by different column names across tables.

```
We see "[ENTITY]" referenced by [N] different column names:

  [TABLE_1].[COL_1]  (appears in [N1] queries)
  [TABLE_2].[COL_2]  (appears in [N2] queries)
  [TABLE_3].[COL_3]  (appears in [N3] queries)

Hypothesis: [COL_1] is canonical (most used).
Consequence: If no shared key exists, cross-domain [entity] questions
  will silently produce wrong joins or empty results.

How do these relate?
  [ [COL_1] is canonical — others map to it ]
  [ They're the same value, different column names ]
  [ We have a mapping/resolution table — I'll point you at it ]
  [ They refer to different populations of [entity] ]
```

---

## Q-TYPE 5: Temporal Definition

Use when the same metric can be calculated with multiple date columns.

```
"[METRIC] by [time period]" could use any of these date columns
in [TABLE_NAME]:

  [DATE_COL_1]  (used in [N1] queries as date filter)
  [DATE_COL_2]  (used in [N2] queries as date filter)
  [DATE_COL_3]  (used in [N3] queries as date filter)

We see all three used in date filters across your query history.
This means different users may be getting different numbers for
the same question depending on which date they filter by.

For the canonical "[METRIC] by [time period]" definition, which date wins?
  [ [DATE_COL_1] — when [event_1] ]
  [ [DATE_COL_2] — when [event_2] ]
  [ [DATE_COL_3] — when [event_3] ]
  [ It depends on domain — Finance uses X, Sales uses Y ]
```

---

## Q-TYPE 6: Staging Exclusion (confirm, don't ask)

Use for tables confidently identified as staging. Just confirm — don't make the
user identify them.

```
We're confident these tables should be excluded from the semantic layer.
They match staging patterns (naming, row churn, never joined to final outputs):

  [TABLE_1]  (matches pattern: %_TMP%)
  [TABLE_2]  (0 queries in last 30 days)
  [TABLE_3]  (matches pattern: %_STAGING%)
  ...

Excluding these removes [N] tables from the model.

  [ Yes — exclude all ]  [ Let me review the list before excluding ]
```

---

## Q-TYPE 7: Bridge vs Core Entity

Use when a table's role is ambiguous (mapping table vs real entity).

```
Table [TABLE_NAME] appears in [N] queries but has no documentation.
It joins [TABLE_A] → [TABLE_B] in [PCT]% of its query appearances.
It has [ROW_COUNT] rows.

Hypothesis: This is a bridge/mapping table (not a user-facing entity).
Consequence: If we treat it as a core entity, we'll expose a
  "[TABLE_NAME]" dimension that would confuse business users.

What is [TABLE_NAME]?
  [ A mapping/bridge table — don't surface it as an entity ]
  [ A core entity — users do query it directly ]
  [ A staging or temp table — exclude entirely ]
  [ An aggregate/summary table — use it as the semantic layer target ]
```

---

## Auto-Handle Rules (no question needed)

Apply these silently and notify user in the pre-build summary:

| Pattern | Action |
|---------|--------|
| Table name matches `%_TMP%`, `%_STAGING%`, `%_LOAD%`, `%_BACKUP%` | Exclude |
| Table has 0 queries in 30 days AND row_count < 1000 | Exclude as dormant |
| Column appears only in WHERE clauses, never in SELECT | Auto-classify as dimension filter |
| Column appears in COUNT(DISTINCT ...) only | Auto-classify as dimension |
| Column appears in SUM/AVG, is numeric, has >50 queries | Auto-classify as metric candidate |
| Table has ROW_COUNT = 0 | Exclude |
| Column appears in <3 queries total | Exclude with LOW_CONFIDENCE note |
