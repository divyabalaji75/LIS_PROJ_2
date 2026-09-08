# Python Pipeline and Business Context Guide

This guide explains what each Python script does, why it exists, and how its most important calculations support the research questions. The snippets are simplified representations of the production code; the linked function names in the source are authoritative.

## Recommended run order

```powershell
.\.venv\Scripts\python.exe member_party.py
$env:LIS_ANALYSIS_YEAR = "2025"; .\.venv\Scripts\python.exe lis_pipeline.py
$env:LIS_ANALYSIS_YEAR = "2026"; .\.venv\Scripts\python.exe lis_pipeline.py
.\.venv\Scripts\python.exe topic_stance_analysis.py
.\.venv\Scripts\python.exe year_over_year_analysis.py
.\.venv\Scripts\python.exe -m pytest -q
$env:LIS_ANALYSIS_YEAR = "2025"; .\.venv\Scripts\python.exe topic_validation_audit.py
$env:LIS_ANALYSIS_YEAR = "2026"; .\.venv\Scripts\python.exe topic_validation_audit.py
```

The dashboard is read-only and runs after the processed outputs exist:

```powershell
.\run_dashboard.ps1
```

## `lis_common.py`

Purpose: provides one shared definition of directory locations, configured years, required-column checks, text cleaning, and CSV writing.

Representative logic:

```python
def configured_years(default=(2025, 2026)):
    value = os.environ.get("LIS_ANALYSIS_YEARS", "")
    return parsed_years or list(default)
```

Business context: year selection and file handling are centralized so adding a session does not require copying scripts or changing business logic in several places. `require_columns` fails early when LIS schema changes instead of silently producing misleading results.

## `member_party.py`

Purpose: builds the auditable party reference used by the voting pipeline. It reads the session roster, retrieves party information, applies explicitly documented fallbacks only where needed, validates completeness, and writes per-year and combined reference files.

Representative logic:

```python
party = fetch_member_party(member_id)
if party is None:
    party = verified_fallbacks.get(member_id)
```

Business context: LIS member files identify people and chambers but the party comparison requires a defensible party assignment. Successful source results are not overwritten by fallbacks, and the reference retains evidence needed to audit the join.

Key functions: `fetch_member_party`, `build_year`, `validate_year`, and `save_year`.

## `lis_pipeline.py`

Purpose: performs the main deterministic transformation from official raw LIS files to canonical and supporting analytical datasets. It contains the established vote parser, member reconciliation, party logic, topic hierarchy, summary selection, sponsor/committee/statement layers, validations, and output writing.

### Download and session configuration

`get_session_code`, `download_file`, and `download_year` map a four-digit year to the LIS bulk-data location and fetch the required files when `RUN_DOWNLOAD` is intentionally enabled.

Business context: raw files remain the source of truth. Downloads are not silently refreshed during ordinary analysis, which helps make a run reproducible.

### Vote parsing and member reconciliation

`parse_vote_file` converts the compact `VOTE.CSV` layout into one row per member and vote event. `add_member_names`, `add_party_info`, and `reconcile_member_metadata` connect those rows to official names, chambers, and the party reference while retaining recovery flags.

Simplified flow:

```python
vote_rows = parse_vote_file(year)
vote_rows = add_member_names(vote_rows, members)
vote_rows = add_party_info(vote_rows, party_reference)
vote_rows = reconcile_member_metadata(vote_rows, members, party_reference)
```

Business context: this creates the canonical record of observable voting behavior. Recovery flags make exceptions visible instead of concealing join failures.

### Party-majority, party-break, and cross-party logic

`calculate_party_positions` counts Yes and No votes within each `vote_id + party`. A position exists only when one direction has a strict majority. `add_own_party_position` and `add_other_party_position` attach those positions to each member record. `flag_party_breaks` and `flag_cross_party_votes` then apply the business definitions.

Simplified formulas:

```python
own_party_position = "Y" if own_yes > own_no else "N" if own_no > own_yes else None
broke_with_party = directional and vote != own_party_position
cross_party = broke_with_party and vote == other_party_position
```

Business context: true cross-party voting is intentionally narrower than disagreement with one's own party. Ties, unavailable positions, abstentions, and not-voting records cannot become cross-party votes.

`validate_party_join` and `validate_party_behavior` test uniqueness, allowed values, eligibility, and logical implications before outputs are written.

### Vote-to-bill bridge and bill history

`build_vote_bill_bridge` extracts vote/bill relationships from official history evidence. `build_bill_history` retains the history timeline. Distinct history rows remain in the bridge; only downstream analytical joins deduplicate `vote_id + Bill_id`.

Business context: one vote can relate to several bills, so forcing a single bill onto `vote_fact` would distort the official record.

### Summary selection

`strip_summary_html` removes presentation markup. `build_bill_summary_lookup` selects the highest-maturity supported summary using the documented priority order.

Simplified priority:

```python
priority = {
    "SUMMARY AS ENACTED WITH GOVERNOR'S RECOMMENDATION": 1,
    "SUMMARY AS PASSED": 2,
    "SUMMARY AS PASSED HOUSE": 3,
    "SUMMARY AS PASSED SENATE": 3,
    "SUMMARY AS INTRODUCED": 4,
}
```

Business context: classification uses the most mature official explanation available and treats House- and Senate-passed summaries consistently.

### Topic classification

`build_lis_subject_hierarchy` loads official parent-child relationships. `build_official_bill_subject_lookup` preserves exact LIS subjects and resolves broader parents. `derive_topics_with_rules` applies the established deterministic topic and exclusion rules. `build_bill_topic_lookup` enforces provenance priority.

Simplified decision order:

```python
if bill_has_official_subject:
    use_official_subject_and_parent()
elif selected_summary_produces_topics:
    use_summary_topics()
elif bill_description_produces_topics:
    use_description_topics()
else:
    classify_as_unclassified()
```

Business context: every bill is assigned to only one evidence tier, even when it has multiple topics within that tier. Official LIS information always outranks derived rules.

`validate_topic_classifications` checks allowed labels, one-tier-per-bill behavior, provenance fields, bill coverage, and official-versus-derived separation. `build_topic_coverage` reports distinct bill counts and percentages by tier. `build_topic_qa_sample` creates a small reproducible semantic-review sample.

### Topic-vote analysis

`build_member_vote_topic` joins canonical member votes to distinct vote/bill links and bill topics. `build_delegate_topic_summary` aggregates the result by legislator and topic.

Business context: this supports questions about observed voting patterns by subject. The output grain is member-vote-subject, so subject totals are not additive to the unique member-vote total.

### Sponsorship, committees, and statements

- `build_sponsor_fact` preserves official sponsor roles and parsed flags.
- `build_sponsor_vote_behavior` joins a sponsor to their official votes on sponsored bills.
- `build_committees` and `build_committee_members` preserve committee reference and assignments.
- `build_vote_statement_fact` retains the official vote and parses an intended Yes/No only when the statement explicitly says so.

Business context: these are separate evidence layers. They enrich analysis but cannot influence topic classification or overwrite official votes.

### Output writing

`save_outputs` writes canonical tables, supporting layers, analytical summaries, and compatibility outputs. New questions should normally be answered from existing canonical tables rather than creating another permanent CSV.

## `topic_stance_analysis.py`

Purpose: summarizes topic-level Yes/No voting proportions using neutral “voting tendency” terminology. The filename remains for compatibility, but outputs do not infer personal belief.

Key thresholds:

```python
MIN_TOPIC_DIRECTIONAL_VOTES = 10
YES_THRESHOLD = 0.65
NO_THRESHOLD = 0.35
```

`assign_voting_tendency` labels sufficiently observed patterns as Mostly Yes, Mixed, or Mostly No. `build_delegate_topic_voting_tendency` produces legislator-topic measures; roster and party summaries provide group views; `build_voting_tendency_yoy` compares sessions.

Business context: these labels describe proportions of recorded votes on bills in a subject. They are not statements that a legislator “supports education” or “opposes healthcare,” because bills within a subject can point in different policy directions.

## `year_over_year_analysis.py`

Purpose: compares two configured sessions using common vote and topic definitions.

Volume safeguards:

```python
MIN_ELIGIBLE_VOTES = 50
MIN_TOPIC_ELIGIBLE_VOTES = 20
ROBUST_TOPIC_ELIGIBLE_VOTES = 50
MIN_DELEGATES_FOR_TOPIC_SUMMARY = 10
```

`build_delegate_yoy` compares legislators, `build_topic_yoy` compares legislator-topic rows, `build_party_yoy_summary` provides party-level context, and robust versus exploratory topic summaries keep low-volume changes out of headline findings.

Business context: a percentage can change sharply when based on few votes. Comparable-sample and robust-volume flags prevent leadership summaries from treating unstable estimates as strong evidence. Even robust changes may reflect a changed agenda or membership mix.

## `topic_validation_audit.py`

Purpose: performs deterministic QA and creates one consolidated audit file per year. It reuses the production classifier rather than maintaining a second copy of the rules.

Checks include rule counts, ceremonial-language candidates, broad/high-risk rules, multi-topic bills, redundant topic pairs, unclassified samples, official-subject samples, summary-selection samples, cross-source comparisons, match strength, and prioritized semantic-review queues.

Representative principle:

```python
from lis_pipeline import derive_topics_with_rules
```

Business context: the audit identifies where human attention has the highest value. Risk scores are triage scores—not probabilities, truth labels, or production changes.

## `topic_semantic_adjudication.py`

Purpose: optional AI-assisted review of difficult derived classifications. Structured judgments are checkpointed and summarized by rule, confidence, and recommended action.

Representative guardrail:

```python
class RecommendedAction(Enum):
    KEEP = "keep"
    REVIEW = "review"
    REMOVE = "remove"
```

Business context: AI judgments are review evidence only. The script does not alter production classifications. A human must decide whether a rule should change, after which the deterministic pipeline and tests must be rerun.

## `dashboard.py`

Purpose: reads processed CSVs and presents five leadership questions. It does not modify source or processed data.

Key calculation helpers:

- `session_vote_metrics`: session Yes, party-break, and true cross-party counts/rates with the correct denominators.
- `party_vote_summary`: party-specific rates.
- `subject_vote_counts`: Yes, No, abstained, not-voting, and cross-party counts by subject.
- `legislator_evidence`: bill-level evidence behind a selected legislator/subject view.
- `bill_outcomes`: reproducible pathway markers from official history text.

Business context: the dashboard deliberately leads with concise answers, then allows drilldown to a legislator, subject, bill, official history, topic provenance, sponsorship, and vote statements. Member IDs remain internal join keys and are not displayed in leadership views.

## Test scripts

The tests protect existing behavior; they should not be weakened merely to make a run pass.

| Test script | Business control |
|---|---|
| `tests/test_vote_fact.py` | Canonical member-vote grain, allowed vote values, and structural integrity |
| `tests/test_vote_bill_bridge.py` | Vote/bill relationships and preservation of distinct history evidence |
| `tests/test_party_join.py` | Completeness and correctness of party attachment |
| `tests/test_reconciliation.py` | Member identity reconciliation and documented recovery behavior |
| `tests/test_cross-party logic.py` | Strict definition of party breaks and true cross-party votes |
| `tests/test_topic_classification.py` | Classification priority, allowed provenance, hierarchy, and source fields |
| `tests/test_topic_voting_tendency.py` | Neutral tendency thresholds and topic-level aggregation |
| `tests/test_yoy_logic.py` | Comparable-sample and year-over-year calculations |
| `tests/test_source_sample.py` | Targeted checks against source-derived records |

## Reading the code with confidence

For any displayed result, trace in this order:

1. Dashboard helper and displayed denominator.
2. Analytical output used by that helper.
3. Canonical table and its stated grain.
4. Production function that created it.
5. Validation function and relevant test.
6. Raw LIS source row.

That chain establishes reproducibility and auditability. It does not remove the need for human semantic review of derived topics or turn descriptive associations into causal conclusions.
