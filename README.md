# Virginia LIS legislative analysis

A reproducible Python pipeline and small read-only dashboard for studying
observable Virginia General Assembly behavior from official Legislative
Information System (LIS) bulk data. The current configuration covers the 2025
and 2026 regular sessions; the code is session-agnostic.

The project describes recorded behavior. It does not infer beliefs, ideology,
motivation, or intent.

## Research questions

The canonical outputs support analysis of:

- Yes/No voting, party breaks, and clearly defined cross-party votes;
- differences in voting patterns by topic and session;
- sponsorship and co-sponsorship, including sponsors' recorded votes;
- committee membership and legislative handling;
- bill histories, timing, advancement, and outcomes visible in LIS history;
- vote statements, while keeping recorded and explicitly intended votes separate.

## Source data

Raw files under `data/raw/<year>/` remain the source of truth:

- `BILLS.CSV`, `HISTORY.CSV`, `VOTE.CSV`, `Members.csv`;
- `CIBillSubjects.csv`, `CIParentChildSubjects.csv`, `Summaries.csv`;
- `Sponsors.csv`, `Committees.csv`, `CommitteeMembers.csv`;
- `VoteStatements.csv`.

Party reference files live under `data/reference/`. Sponsorship, committees,
committee membership, histories, and statements are separate evidence layers;
none influences topic classification.

## Topic methodology

Every bill belongs to exactly one provenance tier:

1. `Official LIS subject`
2. `Derived from LIS bill summary`
3. `Derived from LIS bill description`
4. `Unclassified`

For official bills, `lis_subject_name` preserves the exact LIS child subject and
`lis_parent_subject` preserves the broader parent from
`CIParentChildSubjects.csv`. `topic_name` uses the parent when one exists and the
child otherwise. Multiple child subjects that resolve to the same parent are
kept as auditable text on one analytical bill-topic row.

Bills with an official subject never pass through derived rules. Bills without
one use the highest-maturity supported LIS summary (HTML removed), then fall
back to `Bill_description`. The same deterministic topic and exclusion rules
are applied to both text sources. `source_file`, `source_text_used`,
`rule_derived`, and `matched_rule` make every classification traceable.

## Vote definitions

Directional votes are Yes or No only. A party position exists only when one
direction has a strict majority among that party's directional votes in the
vote event.

- `broke_with_party`: the member's directional vote differs from their own
  party's strict-majority position.
- `cross_party`: the member broke with their own party and their recorded vote
  matches the other party's strict-majority position.

Ties, absent comparison-party positions, and non-directional votes are not
counted as cross-party events. The vote-to-bill bridge retains distinct LIS
history evidence rows; downstream topic joins deduplicate only
`vote_id + Bill_id`.

## Durable processed datasets

The main analytical tables under `data/processed/` are:

- `vote_fact_<year>.csv` — canonical member-by-vote records;
- `vote_bill_bridge_<year>.csv` — LIS vote-to-bill relationships;
- `bill_lookup_<year>.csv` and `bill_topic_lookup_<year>.csv` — bill text and
  auditable topic provenance;
- `sponsor_fact_<year>.csv` and `sponsor_vote_behavior_<year>.csv`;
- `committee_members_<year>.csv` (already includes committee attributes);
- `bill_history_<year>.csv` and `vote_statement_fact_<year>.csv`;
- `delegate_behavior_<year>.csv` and `delegate_topic_behavior_<year>.csv`.

Some narrower exports remain for compatibility with the existing validation
suite. New analysis should derive views from the canonical tables instead of
creating another permanent CSV.

Deterministic topic review writes one consolidated
`data/qa/topic_validation_audit_<year>.csv`, with `audit_section` identifying
the check. Optional AI-assisted semantic review writes one
`topic_semantic_adjudication_<year>.csv`; it is review evidence only and never
changes production classifications.

## Run

Create an environment and install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Build party references, then run each requested year:

```powershell
python member_party.py
$env:LIS_ANALYSIS_YEAR = "2025"; python lis_pipeline.py
$env:LIS_ANALYSIS_YEAR = "2026"; python lis_pipeline.py
python topic_stance_analysis.py
python year_over_year_analysis.py
```

To add sessions without copying code, set a comma-separated year list and
provide the corresponding raw directory and party source:

```powershell
$env:LIS_ANALYSIS_YEARS = "2025,2026,2027"
$env:LIS_ANALYSIS_YEAR = "2027"
python lis_pipeline.py
```

Set `RUN_DOWNLOAD = True` in `lis_pipeline.py` only when an intentional raw-data
refresh is required. Run validation with `python -m pytest -q` and the
consolidated topic audit with, for example,
`$env:LIS_ANALYSIS_YEAR="2025"; python topic_validation_audit.py`.

Launch the leadership-facing dashboard with:

```powershell
streamlit run dashboard.py
```

The dashboard reads processed CSVs without modifying them. It exposes overview
coverage, legislator and topic views, bill-level provenance (including child and
parent subjects), and the separate official evidence layers.

## Limitations

LIS records show formal legislative actions, not private reasoning. Topic rules
can miss context or match language imperfectly; derived classifications require
targeted semantic review. Multi-bill votes are represented through the bridge,
so bill/topic totals must use the documented grain. Session-to-session changes
may reflect membership, agenda, or vote availability as well as behavior.
