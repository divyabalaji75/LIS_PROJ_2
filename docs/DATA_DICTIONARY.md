# Virginia LIS Analysis Data Dictionary

This dictionary documents the durable data used by the analysis. Raw LIS files remain the source of truth. Unless noted otherwise, `<year>` is the four-digit regular-session year and IDs are retained as text so leading zeroes are not lost.

## Data flow and grains

| Layer | Dataset | Grain | Business purpose |
|---|---|---|---|
| Raw | `data/raw/<year>/*` | As published by LIS | Immutable source evidence |
| Reference | `party_reference_<year>.csv` | One member per session | Auditable party assignment used for party comparisons |
| Canonical | `vote_fact_<year>.csv` | One legislator per LIS vote event | Recorded voting behavior and party-comparison flags |
| Canonical | `vote_bill_bridge_<year>.csv` | One retained LIS history record connecting a vote and bill | Preserves one-to-many vote/bill relationships and history evidence |
| Canonical | `bill_lookup_<year>.csv` | One bill | Bill description and primary patron |
| Canonical | `bill_topic_lookup_<year>.csv` | One bill-topic within one provenance tier | Auditable subject classification |
| Canonical | `member_vote_topic_<year>.csv` | One legislator-vote-subject | Topic analysis; a vote may appear under more than one subject |
| Supporting | Sponsor, committee, history, and statement tables | See sections below | Separate evidence layers that never determine topics |
| Analytical | Delegate and topic behavior tables | One legislator or legislator-topic | Dashboard-ready summaries derived from canonical tables |
| QA | `data/qa/topic_validation_audit_<year>.csv` | Mixed, identified by `audit_section` | Consolidated deterministic topic review |

## Official raw LIS sources

| File | Important source fields | Use |
|---|---|---|
| `BILLS.CSV` | `Bill_id`, `Bill_description`, patron, passage/action fields | Bill universe, description, patron, status evidence |
| `HISTORY.CSV` | `Bill_id`, `History_date`, `History_description`, `History_refid` | Bill timeline and vote-to-bill relationships |
| `VOTE.CSV` | LIS compact vote record | Official member vote codes by vote event |
| `Members.csv` | `MBR_HOU`, `MBR_MBRNO`, `MBR_NAME` | Official member roster and chamber |
| `CIBillSubjects.csv` | `Bill_Number`, `Subject_Name`, `Subject_Id` | Exact official LIS bill subjects |
| `CIParentChildSubjects.csv` | parent and child subject names/IDs | Resolves exact LIS subjects to broader parents |
| `Summaries.csv` | bill, document ID, summary type, summary text | Highest-maturity official summary used for fallback classification |
| `Sponsors.csv` | member, bill, patron type | Sponsorship and co-sponsorship layer |
| `Committees.csv` | chamber, committee name and ID | Committee reference |
| `CommitteeMembers.csv` | committee ID, member ID | Committee assignments |
| `VoteStatements.csv` | bill, history reference, date, member, recorded vote, statement | Context supplied after or around a recorded vote |

`VOTE.CSV` is a compact LIS-specific layout rather than an ordinary rectangular CSV with meaningful headers. `parse_vote_file` is the authoritative parser.

## `vote_fact_<year>.csv`

Grain: one legislator on one LIS vote event. Primary analytical key: `vote_id + member_id`.

| Field | Meaning |
|---|---|
| `year` | Session year |
| `vote_id` | LIS vote-event identifier |
| `member_id` | Internal LIS member identifier; used for joins, not displayed in leadership views |
| `vote` | Official vote code: `Y`, `N`, `A`, or `X` |
| `MBR_MBRNO` | Member number from `Members.csv` |
| `MBR_NAME` | Official/reconciled display name |
| `MBR_HOU` | Chamber supplied by the member source |
| `party` | Audited party assignment |
| `party_reference_name` | Name retained from the party reference |
| `member_found_in_members_csv` | Whether roster reconciliation succeeded directly |
| `member_id_prefix` | Prefix used as reconciliation evidence |
| `chamber_recovered_from_member_id` | True when chamber metadata required deterministic recovery |
| `name_recovered_from_party_reference` | True when the party reference supplied the name |
| `own_party_position` | Own party's strict `Y` or `N` majority for this vote; blank for a tie/unavailable position |
| `own_party_yes`, `own_party_no` | Directional vote counts used to establish that majority |
| `broke_with_party` | True only when a directional vote differs from a clear own-party majority |
| `other_party_position` | Comparison party's strict majority position |
| `other_party_yes`, `other_party_no` | Counts used to establish the comparison-party majority |
| `cross_party` | True when the member broke with their party and matched the other party's clear majority |

Important denominator rules: Yes rate uses only `Y` and `N`. Party-break rate uses directional rows with a clear own-party position. Cross-party rate additionally requires a clear other-party position.

## `vote_bill_bridge_<year>.csv`

Grain: retained LIS history evidence for a `vote_id + Bill_id` relationship. Multiple history rows are valid and are not collapsed in this canonical table.

| Field | Meaning |
|---|---|
| `vote_id` | Vote event parsed from LIS history evidence |
| `Bill_id` | Related bill |
| `History_date` | Date on the supporting history row |
| `History_description` | Official text supporting the relationship |

Downstream topic analysis deduplicates to `vote_id + Bill_id` only at the join step to prevent double-counting repeated history evidence.

## `bill_lookup_<year>.csv`

Grain: one bill.

| Field | Meaning |
|---|---|
| `Bill_id` | Official bill identifier |
| `Bill_description` | Official LIS description |
| `Patron_id` | Primary patron identifier from `BILLS.CSV` |
| `Patron_name` | Primary patron name |

## `bill_summary_lookup_<year>.csv`

Grain: one selected summary per bill when a supported summary exists.

| Field | Meaning |
|---|---|
| `Bill_id` | Bill identifier |
| `summary_doc_id` | LIS summary document identifier |
| `summary_type` | Official summary type |
| `summary_priority` | Deterministic maturity rank used for selection |
| `summary_text` | Selected text after HTML removal and normalization |
| `source_file` | Always identifies `Summaries.csv` |
| `source_row_number` | Original source row retained for audit |

Priority is: enacted with Governor's recommendation; passed; passed House/Senate at the same maturity; introduced.

## `lis_subject_hierarchy_<year>.csv`

Grain: one official parent-child subject relationship.

| Field | Meaning |
|---|---|
| `lis_parent_subject_id` | Parent subject ID |
| `lis_parent_subject` | Broader official LIS subject |
| `lis_subject_id` | Child subject ID |
| `lis_subject_name` | Exact child subject |

## `bill_topic_lookup_<year>.csv`

Grain: one analytical bill-topic row. A bill may have multiple topics, but all rows for a bill must use one provenance tier.

| Field | Meaning |
|---|---|
| `Bill_id` | Bill identifier |
| `topic_name` | Subject used in analysis; official parent when available, otherwise exact child or derived topic |
| `classification` | `Official LIS subject`, `Derived from LIS bill summary`, `Derived from LIS bill description`, or `Unclassified` |
| `lis_subject_name` | Exact official LIS subject; blank for derived/unclassified rows |
| `lis_parent_subject` | Broader official parent; blank when unavailable or not official |
| `source_file` | Official file supplying the classification evidence |
| `source_text_used` | Exact normalized source text used for classification |
| `rule_derived` | Whether a deterministic text rule produced the topic |
| `matched_rule` | Documented rule that matched; blank for official/unclassified rows |

## `member_vote_topic_<year>.csv`

Grain: one legislator-vote-subject row after joining the canonical vote, vote/bill bridge, and bill/topic tables.

| Field | Meaning |
|---|---|
| `year`, `vote_id`, `member_id`, `MBR_NAME`, `party`, `vote` | Canonical vote identity and official vote |
| `own_party_position`, `other_party_position` | Party majorities for the vote event |
| `broke_with_party`, `cross_party` | Behavioral flags copied from `vote_fact` |
| `topic_name`, `classification` | Analytical subject and provenance |
| `eligible_cross_party` | Directional vote with both party positions available |

Do not sum this table across subjects to estimate unique votes. A vote connected to multiple topics is intentionally represented more than once.

## Legislator behavior outputs

### `delegate_behavior_<year>.csv`

Grain: one legislator.

| Field | Meaning |
|---|---|
| `member_id`, `MBR_NAME`, `party` | Legislator identity |
| `directional_votes` | Official `Y`/`N` records |
| `eligible_cross_party_votes` | Rows with clear own- and other-party positions |
| `party_breaks` | Directional votes against a clear own-party majority |
| `cross_party_votes` | Party breaks matching the other party's clear majority |
| `cross_party_pct` | `cross_party_votes / eligible_cross_party_votes * 100` |
| `party_break_pct` | Party breaks divided by eligible own-party comparisons |

### `delegate_topic_behavior_<year>.csv`

Grain: one legislator-topic-provenance combination.

| Field | Meaning |
|---|---|
| `member_id`, `MBR_NAME`, `party` | Legislator identity |
| `topic_name`, `classification` | Subject and provenance |
| `topic_vote_events` | Legislator-vote-subject rows |
| `eligible_topic_events` | Rows eligible for cross-party comparison |
| `party_break_events`, `cross_party_events` | Behavioral counts within the subject |
| `cross_party_pct` | Subject-specific cross-party rate |

## Sponsorship outputs

These tables remain part of the reproducible analytical backend. They are not displayed on the simplified leadership dashboard.

### `sponsor_fact_<year>.csv`

Grain: one sponsor-bill record.

| Field | Meaning |
|---|---|
| `year`, `member_id`, `member_name`, `Bill_id` | Session, sponsor, and bill |
| `patron_type` | Original LIS patron value |
| `patron_order` | Parsed order when LIS encodes one |
| `patron_role` | Normalized business role |
| `is_chief_patron`, `is_chief_co_patron`, `is_co_patron` | Explicit role flags |

### `sponsor_vote_behavior_<year>.csv`

Grain: one sponsor-bill-vote relationship after joining sponsorship to official recorded votes. It retains the sponsor fields plus `vote_id`, `vote`, `party`, `broke_with_party`, and `cross_party`.

Sponsor Yes rate uses only sponsor-linked `Y` and `N` rows. It measures recorded behavior on sponsored bills, not motivation or causal influence.

## Committee outputs

### `committees_<year>.csv`

One row per committee: `year`, `committee_id`, `committee_name`, and `chamber`.

### `committee_members_<year>.csv`

One row per committee assignment: committee fields plus `member_id` and `member_name`. A legislator serving on multiple committees has multiple rows.

## History and vote statements

### `bill_history_<year>.csv`

Grain: one official history row. Fields: `year`, `Bill_id`, `history_date`, `history_description`, and `history_refid`.

Dashboard outcome markers are text-based indicators and are not mutually exclusive final-status categories.

### `vote_statement_fact_<year>.csv`

Grain: one LIS vote statement.

| Field | Meaning |
|---|---|
| `year`, `Bill_id`, `vote_id`, `vote_date`, `member_id` | Statement linkage |
| `recorded_vote` | Official vote; never overwritten |
| `vote_statement` | Official statement text |
| `intended_vote` | Parsed `Y` or `N` only when explicitly stated |
| `intended_vote_explicit` | Whether the statement explicitly supports the parsed intention |

## `topic_coverage_<year>.csv`

Grain: one classification tier per year. `bill_count` is the number of distinct bills in the tier, `total_bills` is the complete bill universe, and `bill_percentage` is `bill_count / total_bills * 100`.

## Year-over-year and voting-tendency outputs

Files ending in `_yoy_<year1>_<year2>.csv` compare like-for-like measures between two sessions. `comparable_sample` identifies rows meeting documented minimum-volume rules. Files containing `voting_tendency` summarize observed Yes/No proportions only; labels such as `Mostly Yes`, `Mixed`, and `Mostly No` are not claims about ideology or policy support.

## Missing values and booleans

- A blank party position normally means a tie or insufficient comparison evidence, not zero.
- Blank official subject fields are expected for derived or unclassified topics.
- Boolean flags should be interpreted as calculation results at the dataset's stated grain.
- Counts from tables with different grains are not directly additive.
