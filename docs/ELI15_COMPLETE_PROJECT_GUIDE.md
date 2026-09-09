# ELI15 Complete Project Guide

## The project in one minute

Think of the project as a careful chain of receipts:

1. Virginia LIS publishes raw records.
2. The pipeline reshapes them into consistent tables without changing the official vote.
3. Deterministic rules calculate party majorities, party breaks, true cross-party votes, and topics.
4. Tests look for structural errors, broken joins, double counting, and violations of the written definitions.
5. The dashboard summarizes the results and lets a reviewer trace them back to bills and vote records.

The project measures **what was recorded**, not why a legislator acted or what the legislator believes.

## What each top-level file or folder is for

| File or folder | Plain-English purpose | Output or effect |
|---|---|---|
| `.git/` | Version history | Records exactly what changed and when |
| `.gitignore` | Lists machine-generated files Git should ignore | Prevents caches and local environments from being committed |
| `.venv/` | Project-only Python installation and packages | Lets the project run consistently without a global Streamlit command |
| `.pytest_cache/`, `__pycache__/` | Automatically generated speed-up files | Safe to recreate; not research data |
| `README.md` | Starting instructions and methodology summary | Tells a new user what to run and where to look |
| `requirements.txt` | Normal runtime and test packages | Installs pandas, Beautiful Soup, Plotly, pytest, requests, and Streamlit |
| `requirements-review.txt` | Optional semantic-review packages | Adds OpenAI and Pydantic without making AI part of production |
| `run_dashboard.ps1` | Reliable Windows launcher | Starts Streamlit with `.venv` Python |
| `onboard_session.py` | Future regular-session onboarding command | Downloads, inspects, processes, audits, and tests one new year |
| `data/raw/` | Untouched LIS source snapshots organized by session year | Source of truth |
| `data/reference/` | Auditable party assignments | Supplies party values for comparisons |
| `data/processed/` | Reproducible canonical, supporting, and analytical CSVs | Feeds analysis and dashboard |
| `data/qa/` | Consolidated topic-review outputs | Flags rows for review without changing production data |
| `docs/` | Human documentation | Explains data, terms, code, methodology, and limitations |
| `tests/` | Automated controls | Verifies that the written definitions remain true |

The documentation folder contains:

| Document | Use |
|---|---|
| `DATA_DICTIONARY.md` | Field, key, grain, and denominator reference |
| `BUSINESS_GLOSSARY.md` | Plain-language terminology and interpretation guardrails |
| `PIPELINE_CODE_GUIDE.md` | Shorter technical/business overview of the scripts |
| `VALIDATION_AND_CONFIDENCE.md` | Evidence completed, defensible claims, and sign-off gaps |
| `ELI15_COMPLETE_PROJECT_GUIDE.md` | This complete plain-language walkthrough |
| `TEST_CATALOG.md` | One explanation for every named automated test |
| `APPENDIX_METHODS_AND_VERIFICATION.md` | Separate methods, subject, formula, percentage, and verification appendix |

## The raw LIS files

Each exists under both `data/raw/2025/` and `data/raw/2026/`.

| Raw file | What it contains | What the project uses it for |
|---|---|---|
| `BILLS.CSV` | One row per bill with description, patron, flags, and latest actions | Bill universe, description fallback, bill lookup, outcome context |
| `HISTORY.CSV` | Dated official actions for bills | Timelines, pathway markers, and vote-to-bill links |
| `VOTE.CSV` | Compact LIS vote-event records | Official `Y`, `N`, `A`, and `X` member votes |
| `Members.csv` | Session roster | Official names and chambers |
| `CIBillSubjects.csv` | Official LIS bill subjects | First-priority topic source |
| `CIParentChildSubjects.csv` | Parent/child subject map | Rolls exact official subjects up to broader analytical subjects |
| `Summaries.csv` | Multiple official summaries at different stages | Second-priority topic text after selecting the most mature summary |
| `Sponsors.csv` | Patrons and co-patrons | Separate sponsorship layer |
| `Committees.csv` | Committee IDs, names, and chambers | Committee reference |
| `CommitteeMembers.csv` | Member-to-committee assignments | Committee membership layer |
| `VoteStatements.csv` | Official statements about recorded votes | Preserves context and explicitly stated intended votes separately |

The 2025 raw row counts are 3,510 bills, 54,136 history rows, 140 roster rows, 1,103 official-subject rows, 4,218 summaries, 16,368 sponsor rows, 25 committees, 470 committee assignments, and 3,609 vote statements. The equivalent 2026 counts are 3,646, 65,414, 148, 110, 5,776, 15,875, 25, 464, and 2,638.

## The reference files

| File | Explanation |
|---|---|
| `party_<year>.csv` | Compact member-to-party lookup retained for compatibility |
| `party_reference_<year>.csv` | Auditable member, chamber, party, source label, and source URL |
| `party_reference_2025_2026.csv` | The two yearly references stacked together |

No party is missing in the current references. The source label shows whether the value came from an official page extraction or a documented verified fallback.

## The processed files

`<year>` means that a separate file is created for every onboarded session; the current retained years are 2025 and 2026.

### Canonical and supporting files

| File family | Meaning and output grain |
|---|---|
| `vote_fact_<year>.csv` | One member on one vote event; the canonical vote table |
| `vote_bill_bridge_<year>.csv` | Official history evidence connecting vote events and bills; distinct history rows stay distinct |
| `bill_lookup_<year>.csv` | One bill with description and primary patron |
| `bill_history_<year>.csv` | One official dated bill action |
| `bill_summary_lookup_<year>.csv` | One selected, cleaned, highest-maturity summary per bill |
| `lis_subject_hierarchy_<year>.csv` | One official parent-child subject relationship |
| `bill_topic_lookup_<year>.csv` | One bill-topic row with full provenance |
| `sponsor_fact_<year>.csv` | One sponsor-bill relationship |
| `committees_<year>.csv` | One committee |
| `committee_members_<year>.csv` | One committee assignment |
| `vote_statement_fact_<year>.csv` | One vote statement with recorded and intended vote separated |

### Topic-tier extracts

These are readable slices of `bill_topic_lookup`, not competing classification systems.

| File family | Contents |
|---|---|
| `official_lis_subjects_<year>.csv` | Bills classified directly from LIS subjects |
| `derived_from_lis_bill_summary_<year>.csv` | Bills whose selected summary produced deterministic topics |
| `derived_from_lis_bill_description_<year>.csv` | Bills classified from descriptions only after the summary failed |
| `unclassified_bills_<year>.csv` | Bills for which no allowed topic source produced a topic |
| `topic_coverage_<year>.csv` | Distinct bill counts and percentages for the four tiers |

### Analysis files

| File family | Contents |
|---|---|
| `delegate_behavior_<year>.csv` | One House delegate's overall directional votes, party breaks, and true cross-party rates |
| `member_vote_topic_<year>.csv` | One member-vote-subject; used for subject drilldowns |
| `delegate_topic_behavior_<year>.csv` | One delegate-topic summary |
| `sponsor_vote_behavior_<year>.csv` | A sponsor's recorded votes on sponsored bills |
| `delegate_topic_voting_tendency_<year>.csv` | One delegate-topic Yes/No tendency calculation |
| `delegate_topic_voting_tendency_yoy_2025_2026.csv` | Like-for-like tendency comparison |
| `delegate_topic_stance_<year>.csv`, `delegate_topic_stance_yoy_2025_2026.csv` | Compatibility names for older consumers; “stance” must still be interpreted as recorded tendency |
| `topic_voting_tendency_summary_<year>.csv` | Topic totals of Mostly Yes/Mixed/Mostly No labels |
| `party_topic_voting_tendency_summary_<year>.csv` | The same summary split by party |
| `topic_stance_summary_<year>.csv`, `party_topic_stance_summary_<year>.csv` | Compatibility aliases using older terminology |
| `topic_yes_no_mixed_<year>.csv` | Topic roster of members in the three sufficiently observed tendency groups |

### Year-over-year files

| File | Contents |
|---|---|
| `delegate_behavior_yoy_2025_2026.csv` | Member-level change with comparable-sample flag |
| `delegate_topic_behavior_yoy_2025_2026.csv` | Member-topic change while keeping provenance distinct |
| `party_behavior_yoy_2025_2026.csv` | Party-level comparison |
| `topic_behavior_yoy_2025_2026.csv` | Detailed topic comparison |
| `topic_behavior_yoy_robust_2025_2026.csv` | Headline subset meeting stronger volume rules |
| `topic_behavior_yoy_exploratory_2025_2026.csv` | Broader lower-volume exploratory subset |

### QA and compatibility files

| File family | Why it exists |
|---|---|
| `topic_qa_sample_<year>.csv` | Small reproducible review sample created by the pipeline |
| `manual_source_validation_sample_<year>.csv` | Source-trace examples created by tests |
| `member_roster_recovery_2025.csv` | Documented 2025 reconciliation exceptions |
| `missing_party_members_2025.csv` | Earlier diagnostic retained for history; the current validated party join is complete |
| `bill_subject_lookup_2026.csv`, `member_vote_subject_2026.csv`, `delegate_subject_behavior_2026.csv` | Older 2026-only names retained for compatibility; new work uses the `topic` files |

The two files in `data/qa/`—`topic_validation_audit_2025.csv` and `topic_validation_audit_2026.csv`—combine many review sections into one file per year. `audit_section` tells you what each row represents.

## Every production Python function

### `lis_common.py`

| Function | What it does | Output |
|---|---|---|
| `configured_years` | Reads `LIS_ANALYSIS_YEARS`; otherwise uses 2025 and 2026 | List of integer years |
| `configured_test_years` | Reads `LIS_TEST_YEARS` independently of dashboard/comparison settings | Full-data test years |
| `environment_flag` | Converts conventional environment values such as `1`, `true`, or `off` into a Boolean and rejects ambiguous values | Boolean or clear failure |
| `require_columns` | Stops when required columns are missing | No table; raises a clear error |
| `read_csv` | Checks existence and reads all fields as text | DataFrame |
| `clean_text` | Replaces missing text and trims whitespace | Clean Series |
| `clean_upper` | Cleans text and makes it uppercase | Normalized Series |
| `write_csv` | Creates the destination folder and writes without an index | Output path |

### `onboard_session.py`

| Function | What it does | Output |
|---|---|---|
| `parse_args` | Reads the year and optional skip/comparison switches | Parsed command options |
| `validate_year` | Rejects an implausible session year | Pass or clear failure |
| `run_python` | Runs an existing project script with a controlled environment and stops on failure | Completed subprocess step |
| `download_sources` | Downloads all required files and reports every failed source | Retained raw-year folder |
| `remote_modified` | Reads the official LIS `Last-Modified` header when available | Timestamp or unavailable |
| `inspect_sources` | Parses every source, prints rows/bytes/timestamps, and warns about sparse or stale subject coverage | Terminal readiness report |
| `onboarding_environment` | Sets the new analysis year and prevents an accidental second download | Environment dictionary |
| `main` | Orchestrates party creation, pipeline, audit, new-year tests, and optional comparison | Completed session onboarding |

The script does not create another QA CSV for source freshness. It reports readiness in the terminal and leaves the retained raw files as the evidence.

### `member_party.py`

| Function | What it does | Output |
|---|---|---|
| `get_profile_url` | Chooses the official House or Senate profile URL from the member ID | URL |
| `extract_house_party` | Finds party text in House profile HTML | `D`, `R`, or missing |
| `extract_senate_party` | Finds party text in Senate profile HTML | `D`, `R`, or missing |
| `fetch_member_party` | Downloads one official profile and applies the chamber-specific parser | Party plus source evidence |
| `build_year` | Joins the year's roster to fetched parties and documented fallbacks | Auditable yearly party table |
| `validate_year` | Checks required fields, valid parties, uniqueness, and completeness | Pass or explicit failure |
| `save_year` | Writes compact and full-reference party files | CSV files |

Main block: loops through configured years, builds/validates/saves each, then writes the combined reference.

### `lis_pipeline.py`

| Function | What it does | Output |
|---|---|---|
| `get_session_code` | Converts a year to the LIS regular-session code | Session code |
| `download_file` | Downloads one named LIS file with retry/error reporting | Raw file |
| `download_year` | Fetches every required source for one year | Complete raw-year folder |
| `load_party_reference` | Reads and validates the year's party reference | Party DataFrame |
| `parse_vote_file` | Parses the compact LIS vote layout into member-vote rows | Raw normalized votes |
| `add_member_names` | Joins `Members.csv` and records whether the member was found | Named vote rows |
| `add_party_info` | Joins the party reference without changing vote identity | Votes with party evidence |
| `reconcile_member_metadata` | Recovers legitimate roster gaps using explicit rules and flags | Completed canonical metadata |
| `validate_party_join` | Checks missing/invalid party values, identity consistency, and join coverage | Pass or failure |
| `calculate_party_positions` | Counts party Yes/No votes within each event and assigns only strict majorities | Vote-party position table |
| `add_own_party_position` | Adds the member's party position and its Yes/No counts | Enriched vote rows |
| `flag_party_breaks` | Marks directional votes against a clear own-party position | `broke_with_party` |
| `add_other_party_position` | Adds the comparison party's position and counts | Enriched vote rows |
| `flag_cross_party_votes` | Marks party breaks that match the other party's clear majority | `cross_party` |
| `validate_party_behavior` | Enforces that non-directional votes cannot break/cross and cross-party implies party break | Pass or failure |
| `build_member_behavior_summary` | Aggregates canonical votes to one House delegate | `delegate_behavior` |
| `build_vote_bill_bridge` | Parses official history text to connect vote IDs and bills while retaining evidence rows | Bridge table |
| `build_bill_history` | Cleans and renames the official history fields | History table |
| `build_bill_lookup` | Selects one row per bill with description and patron | Bill lookup |
| `normalize_text_value` | Converts one text value to clean normalized text | String |
| `strip_summary_html` | Decodes and removes HTML from summary text | Plain text |
| `build_lis_subject_hierarchy` | Standardizes official parent-child subject names and IDs | Hierarchy table |
| `build_bill_summary_lookup` | Ranks supported summary types and selects the best row per bill | Summary lookup |
| `build_official_bill_subject_lookup` | Joins exact bill subjects to parents and preserves both | Official topic rows |
| `derive_topics_from_description` | Compatibility wrapper around the production rule engine | Topic matches |
| `derive_topics_with_rules` | Applies frozen topic keywords and exclusion rules | Topics plus matched-rule evidence |
| `build_bill_topic_lookup` | Applies official → summary → description → unclassified priority | Five topic outputs |
| `validate_topic_classifications` | Checks allowed labels, full bill coverage, no tier overlap, evidence fields, and uniqueness | Pass or failure |
| `build_topic_coverage` | Counts distinct bills and percentages in each tier | Coverage table |
| `build_topic_qa_sample` | Draws a fixed-seed sample across topics/provenance | Review sample |
| `build_member_vote_topic` | Joins member votes to distinct vote/bill links and topics | Member-vote-subject table |
| `build_delegate_topic_summary` | Aggregates event counts and cross-party rates by delegate/topic | Topic behavior table |
| `print_delegate_summary` | Prints readable delegate leaders/checks | Terminal report |
| `print_topic_summary` | Prints classified topic leaders while excluding Unclassified from a policy-topic leaderboard | Terminal report |
| `build_sponsor_fact` | Parses patron type, order, normalized role, and flags | Sponsor fact |
| `build_sponsor_vote_behavior` | Connects sponsor-bill rows to the sponsor's official vote through the bridge | Sponsor-vote table |
| `build_committees` | Standardizes committee ID, name, and chamber | Committee table |
| `build_committee_members` | Joins committee assignments to committees and member names | Committee membership table |
| `build_vote_statement_fact` | Links statements to vote IDs, retains official vote, and parses only explicit intended Yes/No | Statement fact |
| `save_outputs` | Writes the year's durable and compatibility datasets | CSV paths |

Major configuration blocks: required filenames, session/year selection, the only allowed provenance values, frozen topic rules, and exclusion rules. The main block runs the functions in dependency order and prints final row counts.

### `topic_stance_analysis.py`

| Function | What it does | Output |
|---|---|---|
| `require_file` | Stops if an expected upstream file is absent | Clear error |
| `normalize_text` | Cleans a Series for stable grouping | Clean Series |
| `load_member_vote_topic` | Loads and validates member-vote-topic inputs | DataFrame |
| `assign_voting_tendency` | Uses directional count and Yes share to label Mostly Yes, Mixed, Mostly No, or Insufficient data | Label |
| `build_delegate_topic_voting_tendency` | Calculates one member-topic tendency | Detailed table |
| `build_topic_voting_tendency_roster` | Produces topic lists of members by tendency | Roster table |
| `build_topic_voting_tendency_summary` | Counts member tendencies by topic | Topic summary |
| `build_party_topic_voting_tendency_summary` | Adds party to the summary | Party-topic summary |
| `build_voting_tendency_yoy` | Compares tendency labels and Yes rates between years | Year-over-year table |
| `print_delegate_topic_results` | Prints examples and counts | Terminal report |
| `print_topic_roster_examples` | Prints readable roster examples | Terminal report |
| `print_voting_tendency_yoy` | Prints changes across sessions | Terminal report |
| `save_year_outputs` | Writes annual detailed/roster/summary tables and compatibility aliases | CSV files |
| `save_yoy_output` | Writes the two-year tendency comparison and alias | CSV files |

Major rules: at least 10 directional topic votes; Yes share at or above 65% is Mostly Yes; at or below 35% is Mostly No; the middle is Mixed. These are vote-pattern labels, not beliefs.

### `year_over_year_analysis.py`

| Function | What it does | Output |
|---|---|---|
| `require_file`, `load_csv` | Validate and read upstream files | DataFrames |
| `load_delegate_behavior` | Loads one year's member summary and standardizes columns | Year-specific delegate table |
| `build_delegate_yoy` | Outer-joins members, calculates changes, and marks comparable samples | Delegate comparison |
| `load_topic_behavior` | Loads and validates one year's delegate-topic summary | Topic input |
| `build_topic_yoy` | Joins on member, topic, and provenance and calculates changes | Topic comparison |
| `build_party_yoy_summary` | Summarizes comparable member changes by party | Party table |
| `build_topic_change_summary` | Builds headline topic changes using robust volume and member-count rules | Robust topic table |
| `build_exploratory_topic_summary` | Builds a broader, explicitly exploratory topic view | Exploratory table |
| `print_delegate_results`, `print_party_summary`, `print_topic_results` | Print readable results and caveats | Terminal reports |
| `save_outputs` | Writes detailed, party, robust, and exploratory comparisons | CSV files |

Major rules: two configured years are required; overall comparability needs at least 50 eligible votes per year; exploratory topics need 20; headline topic comparisons need 50 plus at least 10 delegates.

### `topic_validation_audit.py`

| Function | What it does | Output |
|---|---|---|
| `require_file`, `load_csv` | Check and load required files | DataFrames |
| `clean_string_series`, `normalize_bill_id`, `safe_bool`, `join_sorted` | Standardize audit fields | Clean values |
| `load_data` | Loads the current year's topic inputs | Named tables |
| `combine_derived` | Stacks summary- and description-derived assignments | Derived population |
| `build_rule_audit` | Counts use of each rule/topic and relevant risk flags | Rule audit |
| `is_ceremonial_text`, `build_ceremonial_candidates` | Identify text that may be honorary/non-substantive | Review candidates |
| `build_high_risk_rule_rows` | Selects assignments made by intentionally broad rules | Review rows |
| `build_topic_count_by_bill`, `build_multi_topic_candidates` | Find bills receiving many derived topics | Review rows |
| `build_redundant_topic_candidates` | Finds configured broad/specific topic pairs on one bill | Review rows |
| `build_topic_manual_sample` | Fixed-seed sample within topics | Manual sample |
| `build_rule_manual_sample` | Fixed-seed sample within matched rules | Manual sample |
| `build_unclassified_sample` | Samples possible false negatives | Manual sample |
| `build_official_sample` | Samples official parent/child mappings | Manual sample |
| `build_summary_selection_sample` | Samples selected summary ranks and text | Manual sample |
| `classify_text_for_qa`, `topics_from_matches` | Re-run the production classifier for review only | Comparable topic sets |
| `build_cross_source_comparison` | Compares what summary and description rules would produce | Agreement evidence |
| `measure_match_strength`, `build_match_strength_table` | Measures exact location/strength of matched text | Objective text evidence |
| `build_description_topic_map` | Caches description classifications by bill | Faster audit lookup |
| `calculate_risk_score` | Adds a deterministic triage score—not a probability | Numeric score and reasons |
| `build_semantic_review_queue` | Combines source text, rule evidence, and risk evidence | Review queue |
| `add_risk_band`, `build_risk_summary` | Converts scores to named triage bands and totals | Risk summary |
| `build_priority_review_subset` | Selects a manageable high-priority subset | Review workload |
| `build_audit_summary` | Produces the audit's key totals | Summary rows |
| `save_outputs` | Writes all sections into one annual audit CSV | Consolidated QA file |
| `print_rule_summary`, `print_high_risk_summary`, `print_risk_summary` | Explain the audit in the terminal | Terminal reports |
| `main` | Runs all deterministic audit sections | One complete audit |

### `topic_semantic_adjudication.py`

| Function or class | What it does | Output |
|---|---|---|
| `Judgment`, `Confidence`, `RecommendedAction` | Restrict model responses to allowed review labels | Enums |
| `SemanticJudgment` | Validates the structured response fields | Pydantic record |
| `require_file`, `load_csv`, `normalize_text` | Basic input controls | Clean inputs |
| `build_assignment_key` | Creates a stable bill-topic-review key | Unique key |
| `build_full_review_queue`, `build_review_population` | Select high-risk cases plus an unbiased low-risk control sample | Review population |
| `build_model_prompt` | Supplies source text and rubric while hiding risk labels from the model | Blinded prompt |
| `adjudicate_once` | Requests one structured independent judgment | One judgment |
| `adjudicate_assignment` | Runs two passes and determines agreement/disagreement | Consensus record |
| `load_existing_results`, `save_checkpoint` | Resume safely without losing completed paid work | Checkpoint |
| `join_risk_metadata` | Restores risk details after blinded review | Enriched review results |
| `build_rule_results` | Estimates observed rule precision from reviewed TP/FP cases | Rule review summary |
| `build_review_summary` | Summarizes judgments, confidence, agreement, and human-review needs | QA summary |
| `main` | Runs or dry-runs the optional review workflow | QA-only CSV |

This script never changes the production topic table. AI review is evidence for a later human decision.

### `dashboard.py`

| Function | What it does | Output |
|---|---|---|
| `load_output` | Reads one processed year table and caches it | DataFrame |
| `pct` | Safely calculates a percentage, returning zero for a zero denominator | Number |
| `answer` | Renders the blue “What the records show” callout | Leadership text |
| `compact_table` | Renders a readable, downloadable table | Dashboard component |
| `bar_chart` | Builds consistently formatted vertical or horizontal Plotly bars | Dashboard chart |
| `session_vote_metrics` | Calculates directional, Yes, party-break, cross-party, member, and event totals with correct denominators | Metric dictionary |
| `party_vote_summary` | Repeats party-break/cross-party calculations within each party | Party table |
| `topic_summary` | Aggregates delegate-topic rows into subject volume and cross-party rates | Subject table |
| `subject_vote_counts` | Counts official vote codes and cross-party records by subject | Subject table |
| `legislator_evidence` | Joins selected member/topic rows back to bills, provenance, and LIS vote records | Verification table |
| `bill_outcomes` | Counts reproducible history-text pathway markers | Outcome dictionary |
| `render_voting_page` | Shows overall voting, count/rate leaders, and delegate drilldown | Voting page |
| `render_subjects_page` | Shows subject patterns, delegate-subject leaders, and subject-to-delegate comparison | Subjects page |
| `render_comparison_page` | Shows changes across the configured processed sessions | Comparison page |
| `render_bills_page` | Shows pathway markers, bill lookup, provenance, timelines, and statements | Bills page |

The sidebar separates the briefing into four pages: Voting overview, Subjects and delegates, Session comparison, and Bills and context. Only the selected page renders, and the content width is larger than the previous single-scroll layout. Sponsorship remains available in the processed data but is intentionally omitted from this simplified leadership interface.

## What every test protects

Pytest expands full-data tests across the years selected by `LIS_TEST_YEARS`. With the default 2025 and 2026 configuration, 195 named test functions currently produce 336 passing test cases.

### `test_vote_fact.py`

- `test_vote_fact_required_columns`: required canonical fields exist.
- `test_vote_fact_not_empty`: a session did not produce an empty dataset.
- `test_vote_fact_year_matches`: rows are labeled with the requested year.
- `test_vote_fact_no_missing_vote_id`, `test_vote_fact_no_missing_member_id`, `test_vote_fact_no_missing_member_name`, `test_vote_fact_no_blank_vote`: essential identity/vote fields are populated.
- `test_vote_fact_valid_chamber`, `test_member_id_prefix_matches_chamber`: chamber values and ID evidence agree.
- `test_vote_fact_valid_party`, `test_vote_fact_no_missing_party`: party values are complete and allowed.
- `test_vote_fact_vote_codes_expected`: vote codes stay within the supported official set.
- `test_vote_fact_unique_member_vote_event`: the canonical key is unique.
- `test_member_id_maps_to_one_name`, `test_member_id_maps_to_one_party`, `test_member_id_maps_to_one_chamber`: identity is stable within a session.
- `test_vote_events_have_member_responses`, `test_vote_fact_reasonable_scale`: catches empty/malformed event parsing and implausible collapse.

### `test_cross-party logic.py`

- `test_republican_cross_party_yes`, `test_democrat_cross_party_no`: positive examples work in both political directions.
- `test_member_agrees_with_own_party`: agreement is not a party break.
- `test_party_break_without_cross_party`: disagreement alone is not automatically cross-party.
- `test_own_party_tie_not_party_break`, `test_other_party_tie_not_cross_party`: strict-majority tie exclusions work.
- `test_x_vote_not_directional`, `test_a_vote_not_directional`, `test_p_vote_not_directional`: non-directional codes cannot create party behavior flags.
- `test_nondirectional_votes_do_not_affect_party_majority`: only Yes/No determines a party position.
- `test_cross_party_always_implies_party_break`: logical implication holds for all rows.
- `test_party_positions_are_chamber_specific`: members are compared within the correct institutional context.

### `test_party_join.py`

- Required-column, nonempty, nonblank-ID, unique-ID, valid-party, nonblank-party, and nonblank-name tests validate the reference itself.
- `test_every_voting_member_exists_in_party_reference`, `test_vote_fact_party_join_complete`, and `test_all_vote_rows_have_reference_backing` verify complete coverage.
- `test_vote_fact_party_values_valid`, `test_vote_fact_party_matches_reference`, and `test_each_member_maps_to_one_party` verify party correctness and stability.
- `test_party_reference_name_matches_vote_fact_name` checks identity agreement.
- `test_party_reference_member_id_prefix_valid` and `test_party_join_preserves_chamber_identity` protect chamber mapping.
- `test_party_counts_reasonable` catches an implausible all-one-party or badly collapsed result.

### `test_vote_bill_bridge.py`

- Required-column, nonempty, nonblank vote/bill ID, and bill-lookup uniqueness tests protect structure.
- `test_vote_bill_relationships_unique` protects the intended evidence-row identity.
- Vote-ID and bill-ID existence tests ensure every bridge endpoint is real.
- `test_some_votes_map_to_multiple_bills` proves the model preserves the real one-to-many relationship.
- `test_unmatched_vote_events_are_preserved` proves the canonical vote table does not lose events just because no bill link exists.
- `test_vote_fact_grain_remains_unique` proves the bridge never contaminates canonical grain.
- Join-expansion tests prove expansion is expected, creates no new vote IDs, repeats member identity only because bills differ, and has more rows than canonical votes.
- `test_every_bridge_vote_has_member_responses` confirms linked vote events contain actual votes.

### `test_topic_classification.py`

- Required-column, nonempty, allowed-label, nonblank ID/name/classification, full bill coverage, and known-bill tests protect the basic contract.
- Official/derived/unclassified file tests verify each slice contains only its named tier.
- Unclassified tests verify the explicit label, one row, and exclusivity.
- Official precedence and “not unclassified” tests protect the exact tier order.
- Bill-level partition, no-duplicate-row, and one-provenance-tier tests prevent overlap and double assignment across tiers.
- Derived/official nonblank-topic tests protect usable results.
- Projection reconciliation tests prove the tier extracts reconstruct the combined lookup.
- Description presence and four provenance-contract tests verify the source fields appropriate to every tier.
- `test_topic_coverage_reconciles_to_provenance_sets` proves coverage totals use the same distinct bill sets.

### `test_source_sample.py`

- Raw-vote reconciliation tests compare parsed totals and sampled records directly with `VOTE.CSV`.
- Bill-description sampling checks processed descriptions against `BILLS.CSV`.
- Official-subject tests check source backing, exact preservation, parent rollup, and provenance fields against both LIS subject files.
- Derived-topic tests check official description backing and exact provenance labels.
- Party/member tests check reference and roster evidence.
- Bridge tests compare rows to raw history and ensure vote/bill endpoints exist in raw sources.
- `test_create_manual_source_validation_sample` produces a compact human-readable trace sample.

### `test_reconciliation.py`

- Vote-code and directional totals reconcile raw/canonical counts.
- Non-directional and cross-party implication tests repeat the most important behavior invariants on full outputs.
- Delegate summary tests prove it contains House members and reconciles party-break, cross-party, and directional totals.
- Classification partition/overlap/value tests reconcile bill provenance.
- Member-vote-topic uniqueness, backing, and vote-equality tests protect the downstream join.
- Topic and tendency tests check counts, percentages, labels, minimum volumes, and 65%/35% thresholds.
- Bill IDs must be backed by the bill lookup.
- Member IDs and parties cannot be blank across analysis outputs.

### `test_topic_voting_tendency.py`

- Clear Yes, No, and Mixed examples prove the basic labels.
- Minimum-sample tests prove too-few directional votes remain Insufficient and exactly 10 qualifies.
- Boundary tests prove exactly 65% is Mostly Yes, exactly 35% is Mostly No, and values just inside are Mixed.
- Non-directional tests prove `A`/`X` are excluded from the denominator and cannot satisfy the minimum, while total topic-event counts still retain them.
- Provenance tests prove official and derived rows stay distinct.
- Topic/member/year separation tests prevent accidental grouping across keys.
- Reconciliation tests prove directional totals and Yes/No percentages add up.
- The parameterized valid-label test rejects unexpected tendency labels.

### `test_yoy_logic.py`

- Delegate percentage/count-change tests verify subtraction between sessions.
- Presence tests distinguish both-year, 2025-only, and 2026-only members.
- Comparable-sample tests require both years and sufficient volume.
- Tendency-transition tests define which pairs count as observed behavior changes and exclude changes involving Insufficient data.
- Topic Yes-percentage change is recomputed correctly.
- Provenance, member, and topic join tests prevent unlike rows from merging; matching topic and provenance rows do merge.

### `test_session_configuration.py`

- Default and future-year tests verify analysis-year parsing.
- Regular-session-code tests verify that 2027 and 2028 map to `20271` and `20281`.
- Independent test-year selection proves a new year can be validated without changing dashboard or comparison configuration.
- True, false, and invalid download-flag tests prevent an ambiguous refresh setting.
- Onboarding-year tests accept 2027/2028 and reject implausible values.
- The onboarding environment test proves the command targets one year and prevents an accidental second download during processing.

## What has been verified

- All 336 current automated test cases pass.
- Canonical vote parsing reconciles to raw LIS samples and totals.
- Member, chamber, and party joins are complete under the documented reconciliation rules.
- Party-majority, party-break, and true cross-party definitions are tested with positive, negative, tie, non-directional, and full-data cases.
- One-to-many vote/bill relationships are preserved without changing canonical vote grain.
- Topic priority, allowed provenance, exact official subject, parent rollup, summary/description evidence, and full bill partition are tested.
- Voting-tendency thresholds and year-over-year comparability are tested.
- Dashboard delegate-to-subject, subject-to-delegate, ranking, and bill-subject filters load and calculate without exceptions.

## What remains to be verified or improved

1. Confirm that the very small 2026 `CIBillSubjects.csv` snapshot is complete; only 45 bills receive official subjects versus 405 in 2025.
2. Finish human semantic review of derived-topic rules, especially the audit's high- and very-high-risk assignments.
3. Add one run manifest with source URL, retrieval time, hash, code commit, and output row counts.
4. Reconfirm the documented party fallbacks: 26 rows in 2025 and 9 in 2026.
5. Define mutually exclusive final bill outcomes before presenting pathway markers as final disposition percentages.
6. Structure committee referral/report/action events before making committee-effectiveness or “killed in committee” claims.
7. Have a second reviewer manually trace the highest-profile dashboard figures to raw LIS rows and sign a dated checklist.

The separate appendix gives the exact topic percentages, formulas, and verification procedure.
