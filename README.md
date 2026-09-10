# Virginia LIS legislative analysis

A reproducible Python pipeline and small read-only dashboard for studying
observable Virginia General Assembly behavior from official Legislative
Information System (LIS) bulk data. The current configuration covers the 2025
and 2026 regular sessions; the code is session-agnostic.

The project describes recorded behavior. It does not infer beliefs, ideology,
motivation, or intent.

## Project documentation

- [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) defines source and processed datasets, grains, keys, and fields.
- [`docs/BUSINESS_GLOSSARY.md`](docs/BUSINESS_GLOSSARY.md) provides leadership-friendly terms and interpretation guardrails.
- [`docs/PIPELINE_CODE_GUIDE.md`](docs/PIPELINE_CODE_GUIDE.md) explains every Python script, representative logic, and business purpose.
- [`docs/VALIDATION_AND_CONFIDENCE.md`](docs/VALIDATION_AND_CONFIDENCE.md) records completed validation, defensible claims, and remaining sign-off gaps.
- [`docs/ELI15_COMPLETE_PROJECT_GUIDE.md`](docs/ELI15_COMPLETE_PROJECT_GUIDE.md) walks through every project file family, production function, code block, output, and test in plain language.
- [`docs/APPENDIX_METHODS_AND_VERIFICATION.md`](docs/APPENDIX_METHODS_AND_VERIFICATION.md) is the separate methods appendix with topic derivation, source percentages, formulas, and verification evidence.
- [`docs/TEST_CATALOG.md`](docs/TEST_CATALOG.md) explains the business control provided by every named automated test.

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
Derived rows reuse established subject names when the official text supports
them and add a documented analytical category only when needed. They remain
visibly labeled as summary- or description-derived and are never presented as
official LIS subjects.

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

To onboard a new regular session without copying code, use the dedicated command. It downloads all required LIS files, reports source row counts and freshness warnings, builds and validates the party reference, runs the pipeline and topic audit, and runs the full-data tests against the new year. Existing processed sessions are retained, and the latest earlier processed year is used for YoY automatically:

```powershell
.\.venv\Scripts\python.exe onboard_session.py 2027
```

Use `--compare-with 2025` to override the automatic comparison year. Use `--skip-download` or `--skip-party` only when the corresponding retained files already exist. The onboarding command warns when official-subject coverage is below 5% or `CIBillSubjects.csv` is more than 30 days older than `BILLS.CSV`; warnings require review but do not silently alter classification. The dashboard discovers every retained `vote_fact_<year>.csv`, so a successfully processed future regular session appears alongside 2025 and 2026 without replacing them.

For a manual raw-data refresh, set `$env:LIS_DOWNLOAD = "1"`. Ordinary runs default to retained raw files. Set `LIS_TEST_YEARS` to run the full-data tests against any processed sessions, for example `$env:LIS_TEST_YEARS="2027,2028"; python -m pytest -q`. The regular-session URL convention is `YYYY1`; special sessions need an explicit future session-code design because year alone is not a unique key.

As checked against the official LIS bulk endpoint on September 9, 2026, `20271` is a partial future-session folder and is still missing votes, vote statements, and both subject files. `20262` (2026 Special Session I) has recorded votes but lacks both official-subject files. No `20252` or `20253` bulk folder exists. The sampled pre-2024 regular-session URLs return 404 under the current blob convention even though older sessions remain visible in the LIS website. Do not place special-session files in `data/raw/2026/`: the current storage and output keys use year alone, so that would overwrite or mix the regular session. Special sessions require a session-key migration before ingestion; historical sessions may additionally require a legacy source adapter and schema reconciliation.

Launch the leadership-facing dashboard with the project-local Python runtime:

```powershell
.\run_dashboard.ps1
```

Equivalently, run `.venv\Scripts\python.exe -m streamlit run dashboard.py`.
Using `python -m streamlit` avoids depending on a globally installed
`streamlit` command.

The dashboard reads processed CSVs without modifying them. Sidebar navigation
separates four leadership questions into independent, wider pages: voting,
subjects and delegates, session comparison, and bills and context. The subject
page supports both directions of review: choose a delegate to see voting by
subject, or choose a subject and vote type to see the exact bills, delegates,
recorded votes, party-majority positions, and LIS vote records. The bill page
also provides a searchable view of records that remain unclassified.
The pages also show true cross-party leaders by count and rate,
delegate-subject leaders, bill-level
provenance (including child and parent LIS subjects), official histories and
vote statements, and subject-filtered bill lookup. Sponsorship remains a
separate processed analytical layer, but is intentionally omitted from the
simplified leadership interface.

For a small internal pilot, Streamlit Community Cloud can deploy from a private
GitHub repository and restrict a private app to invited viewers. Confirm the
repository is private before deployment and use the Community Cloud viewer list
rather than making the app public. For organization-managed identity,
conditional access, and longer-term ownership, deploy the same Streamlit app to
an approved internal platform such as Azure App Service with Microsoft Entra ID.

## Limitations

LIS records show formal legislative actions, not private reasoning. Topic rules
can miss context or match language imperfectly; derived classifications require
targeted semantic review. Multi-bill votes are represented through the bridge,
so bill/topic totals must use the documented grain. Session-to-session changes
may reflect membership, agenda, or vote availability as well as behavior.
