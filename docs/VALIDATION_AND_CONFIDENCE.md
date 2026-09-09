# Validation, Confidence, and Remaining Gaps

## Executive conclusion

The voting calculations are reproducible, internally consistent, and traceable to official LIS records. On September 9, 2026, the expanded automated suite completed with **336 tests passing**. That supports high confidence in the implemented vote parsing, member reconciliation, party joins, strict-majority logic, party-break logic, true cross-party logic, vote/bill bridge behavior, topic-provenance priority, year-over-year calculations, future-session configuration, and dashboard page isolation.

It would still be inappropriate to promise “100% certainty.” Automated tests demonstrate that the code behaves as specified; they cannot prove that every external source file is complete, every party fallback remains correct, or every deterministic text classification is substantively ideal. Leadership can instead be told that the results are **reproducible, source-traceable, tested, and accompanied by explicit limitations and open review items**.

## Validation completed

| Control | Current evidence | Confidence supported |
|---|---|---|
| Automated test suite | 336 tests passed | Structural and logical implementation |
| Full-row programmatic checks | Production validation functions fail on invalid schemas, joins, labels, or logical implications | Dataset-wide consistency |
| Canonical vote grain | `vote_id + member_id` checks | Member-vote counts are not inflated by topic joins |
| Strict party positions | Positions require more Yes than No or more No than Yes | Ties are not silently assigned |
| Cross-party implication | Cross-party requires a party break and a match to the other party | Narrow definition is enforced |
| Topic provenance | Allowed four-value classification and one tier per bill | Official and derived evidence remain distinct |
| Vote/bill relationship | Distinct history evidence retained; downstream deduplication occurs only at the analytical join | Multi-bill votes are preserved |
| Recorded versus intended vote | Separate fields and explicit-intention flag | Statements do not rewrite official votes |
| Dashboard checks | All four navigation pages load independently without exceptions; delegate-to-subject and subject-to-delegate filters recalculate; count/rate rankings render; bill subject filter returns only matching bills | Presentation uses the intended processed data without a single long-scroll page |
| Consolidated topic audit | `topic_validation_audit_2025.csv` and `_2026.csv` | Reproducible QA queue and samples |
| Future-session onboarding | Required-file parsing, source inventory, subject sparsity/freshness warnings, party validation, pipeline, audit, and configurable full-data tests | A new year reuses the established controls without copied scripts |

## Current source and coverage facts

| Item | 2025 | 2026 | Interpretation |
|---|---:|---:|---|
| Bills | 3,510 | 3,646 | Complete pipeline bill universe for each loaded snapshot |
| Official-subject bills | 405 (11.54%) | 45 (1.23%) | Large source-coverage difference requires confirmation |
| Summary-derived bills | 1,515 (43.16%) | 460 (12.62%) | Deterministic, but semantically reviewable |
| Description-derived bills | 270 (7.69%) | 1,224 (33.57%) | Deterministic, but semantically reviewable |
| Unclassified bills | 1,320 (37.61%) | 1,917 (52.58%) | Explicit missing classification, not a forced guess |
| High-risk derived assignments | 660 | 188 | QA priority, not known errors |
| Very-high-risk derived assignments | 246 | 72 | Highest-priority human review queue |

## What is still missing

### 1. Confirm the 2026 official-subject source snapshot

`CIBillSubjects.csv` is materially smaller for 2026 than for 2025, and only 45 of 3,646 bills receive official subjects. This may accurately reflect what LIS published in the downloaded snapshot, but the difference is large enough that it should be confirmed directly with LIS before making strong claims about subject availability across sessions.

Recommended sign-off: re-download or independently compare the 2026 file, record the retrieval timestamp and file hash, then rerun the pipeline and coverage report.

### 2. Complete human semantic review of derived topics

The deterministic audit identifies high- and very-high-risk assignments, broad-rule matches, ceremonial-language candidates, multi-topic bills, and low agreement between summary and description evidence. These are review priorities, not automatically incorrect rows.

Recommended sign-off: have a policy/domain reviewer adjudicate at least all very-high-risk assignments and a stratified sample of high-risk, unclassified, official, and ordinary derived rows. Record reviewer, date, decision, and rationale. If rules change, rerun the deterministic pipeline and tests.

Optional AI review may help triage, but it must remain separate review evidence and cannot silently change production data.

### 3. Create a source/run manifest

The repository retains raw files, but a formal manifest containing source URL, retrieval timestamp, byte size, cryptographic hash, session code, code commit, and output row counts is not yet a standard pipeline artifact.

Recommended sign-off: add one consolidated manifest per run—not a proliferation of validation CSVs—so any published number can be tied to an exact source snapshot and code version.

### 4. Review party fallback assignments

Party references have no missing party values, but 26 records in 2025 and 9 in 2026 use the documented verified-fallback path rather than a successful live page extraction.

Recommended sign-off: independently confirm those fallback rows against official House/Senate records and record a review date. The current reference retains source labels and URLs for this purpose.

### 5. Strengthen final-disposition and committee-pathway analysis

The dashboard's outcome figures are reproducible history-text markers, not a mutually exclusive final-status model. Committee membership is well represented, but the project does not yet provide a single canonical bill-committee-handling table that identifies referrals, reports, and outcomes as structured events.

Recommended sign-off: before making claims such as “the percentage of bills killed in committee” or causal claims about committee membership, define and test a mutually exclusive outcome methodology and structured committee-event rules. The current dashboard appropriately uses narrower wording.

### 6. Record manual verification of headline figures

Automated tests should be supplemented with a small, documented source trace for the most visible leadership claims: the overall Yes rate, party-break rate, true cross-party rate, leading delegate by count, leading delegate by rate, leading subject, leading delegate-subject combination, and became-law marker.

Recommended sign-off: two reviewers independently trace a small set of displayed rows from dashboard to processed table to raw LIS source and initial a dated checklist. This validates both the calculation and the communication layer.

### 7. Add a session key before special-session ingestion

The current canonical paths and output names use year alone. Regular Session 2026 and Special Session I 2026 would therefore collide if both were written under `data/raw/2026/` or emitted as `vote_fact_2026.csv`. The 2026 special-session bulk folder also lacks both official-subject files. Historical sessions before 2024 are not available at the sampled current blob URLs and may use older schemas or delivery methods.

Recommended sign-off: introduce a durable session key such as `20261`/`20262` throughout raw paths, canonical tables, outputs, tests, and dashboard labels before downloading a special session. Treat missing subject sources as an explicit provenance/coverage condition, not as permission to invent official classifications. Build a separately tested legacy adapter if pre-2024 data is obtained from the LIS archive or API.

## Claims that are currently defensible

- “The dashboard is built from official LIS bulk records and an auditable party reference.”
- “The calculations are deterministic and reproducible from retained raw files.”
- “All 336 automated tests pass.”
- “True cross-party voting uses a documented, deliberately narrow definition.”
- “Official topics, derived topics, and unclassified bills remain distinguishable.”
- “Every leadership drilldown can be traced to bill and vote records.”

## Claims to avoid until the gaps are closed

- “Every topic assignment is substantively correct.”
- “The 2026 LIS subject file is unquestionably complete.”
- “A voting pattern reveals a legislator's personal belief or motivation.”
- “Sponsorship caused a legislator's voting behavior.”
- “A history marker is a mutually exclusive final outcome.”
- “The numbers are 100% certain.”

## Leadership-ready confidence statement

> I am confident that these figures are reproducible and accurately implement our documented definitions. They are built from retained official LIS records, the full automated suite passes, and the dashboard provides a trace back to the underlying vote and bill evidence. I also distinguish what the records prove from what they cannot prove. Before treating derived topics or 2026 official-subject coverage as final, I would complete the documented source and human semantic reviews.
