# Appendix: Methods, Subject Derivation, Calculations, and Verification

This appendix is intentionally separate from the dashboard. It provides the technical support behind leadership-facing figures without adding methodology clutter to the briefing page.

## A. Source hierarchy for subjects

Every bill is placed into exactly one provenance tier. The pipeline asks these questions in order and stops as soon as a tier qualifies:

```text
Does CIBillSubjects.csv contain the bill?
  Yes → Official LIS subject; never run derived rules.
  No  → Select the best supported LIS summary and run the rules.
          Match → Derived from LIS bill summary.
          No match → Run the same rules on Bill_description.
                       Match → Derived from LIS bill description.
                       No match → Unclassified.
```

A bill may have several topics within its chosen tier, but it cannot mix official, summary-derived, description-derived, and unclassified rows.

## B. Official LIS subject handling

1. `CIBillSubjects.csv` supplies the exact subject and subject ID.
2. The exact published text is preserved in `lis_subject_name`.
3. `CIParentChildSubjects.csv` is joined using the official subject ID/name.
4. The broader parent is preserved in `lis_parent_subject`.
5. `topic_name` uses the parent when one exists; otherwise it uses the exact subject.
6. Several exact child subjects that lead to the same parent can be combined for analytical display while the child text remains available for audit.

Example:

```text
Exact LIS subject: Labor and Employment | Wages
Broader LIS parent: Labor and Employment
Dashboard topic:   Labor and Employment
Classification:    Official LIS subject
```

The parent makes broad comparisons readable; the child preserves the detail needed to verify what LIS actually assigned.

## C. Summary selection

Only supported official summary types are considered. Lower number means higher priority:

| Priority | LIS summary type |
|---:|---|
| 1 | `SUMMARY AS ENACTED WITH GOVERNOR'S RECOMMENDATION` |
| 2 | `SUMMARY AS PASSED` |
| 3 | `SUMMARY AS PASSED HOUSE` |
| 3 | `SUMMARY AS PASSED SENATE` |
| 4 | `SUMMARY AS INTRODUCED` |

House- and Senate-passed summaries deliberately share a maturity level. HTML entities and tags are removed before matching. The selected document ID, type, priority, source row, and cleaned text are retained in `bill_summary_lookup_<year>.csv`.

## D. Deterministic derived-topic rules

The rule engine searches official text case-insensitively using word-aware regular expressions. A topic is produced when one of its positive patterns matches unless a topic-specific exclusion also matches. The same rules and exclusions are used for summaries and descriptions.

The frozen derived-topic families are:

| Topic | Examples of text evidence |
|---|---|
| Education | public school, school board/division, student, teacher, education, tuition |
| Higher Education | higher education, public university, community college, SCHEV |
| Health and Healthcare | health care, hospital, medical, Medicaid, patient, physician, nurse, pharmacy |
| Behavioral Health | mental/behavioral health, substance use, addiction, psychiatric, opioid |
| Housing | affordable housing, landlord/tenant, rental agreement, eviction, residential property |
| Labor and Employment | employment, employee/employer, wage, paid/sick leave, workers' compensation, workforce |
| Energy and Utilities | electric/public utility, electricity, energy, solar/wind, grid, demand response |
| Environment and Conservation | environmental, conservation, pollution, wetlands, water/air quality, wildlife, forestry, recycling |
| Transportation | VDOT, transportation, highway, motor vehicle, driver's license, traffic, transit, rail |
| Criminal Justice | criminal, crime/offense, felony/misdemeanor, sentencing, probation/parole, correctional/inmate |
| Courts and Civil Law | civil action/procedure/liability, lawsuit, damages, judgment, appellate/court-service references |
| Public Safety | public safety, law enforcement, police, firefighter, emergency/disaster services |
| Firearms | firearm, handgun, assault firearm, ammunition, weapon |
| Elections and Voting | election, voter/voting, ballot, polling place, absentee voting, campaign finance, primary date |
| Taxes and Revenue | income/sales/property tax, tax credit/deduction, taxation, taxable, revenue |
| Budget and Appropriations | budget, appropriation, general fund, state/local school funds |
| Business and Commerce | business license, corporation, commercial/commerce, consumer protection/debt, procurement, franchise |
| Insurance | health/motor/liability insurance, insurance policy/insurer, health plan, coverage, annuity |
| Agriculture and Food | agriculture/farm, livestock, food, hunger/insecurity, fertilizer, forest prosperity |
| Local Government | local government/locality, county board, supervisors, town/city charter, municipal, zoning |
| State Government | state agency/board/commission, state government/employee, Virginia Personnel Act |
| Technology and Data | artificial intelligence, cybersecurity, data privacy, digital assets/ID, automated decisions, internet |
| Family and Children | foster care, child abuse/neglect/custody/support/care, minor, parental, adoption |
| Marriage and Domestic Relations | marriage, divorce, spouse, domestic relations, annulment |
| Social Services | social services, public assistance, protective services, family assessments, care homes, hunger |

These are analytical categories, not official LIS subjects.

### Exclusions

Exclusions prevent known literal-word false positives; they never create a new topic.

- Elections and Voting is suppressed for judicial-election language such as judges, courts, and nominations for election.
- Business and Commerce is suppressed for driver's licenses, consumer-directed services, and Medicaid waivers.
- State Government is suppressed when a department name merely mentions motor vehicles, environmental quality, taxation, or fire programs.
- Local Government is suppressed for ceremonial resolutions using “commending” or “celebrating the life.”

Every derived output retains `source_file`, `source_text_used`, `rule_derived`, and `matched_rule`, so a reviewer can see exactly why the rule fired.

## E. Subject provenance percentages

### Percentage of bills by source tier

This is the primary coverage measure because every bill appears in exactly one tier.

| Classification | 2025 bills | 2025 share | 2026 bills | 2026 share |
|---|---:|---:|---:|---:|
| Official LIS subject | 405 | 11.54% | 45 | 1.23% |
| Derived from LIS bill summary | 1,515 | 43.16% | 460 | 12.62% |
| Derived from LIS bill description | 270 | 7.69% | 1,224 | 33.57% |
| Unclassified | 1,320 | 37.61% | 1,917 | 52.58% |
| **Total** | **3,510** | **100.00%** | **3,646** | **100.00%** |

Formula:

```text
Bill share for a tier = distinct bills in that tier ÷ all distinct bills × 100
```

### Percentage of analytical bill-topic rows by source tier

This answers a different question. A classified bill can have multiple topics, so these are topic-row shares rather than bill shares.

| Classification | 2025 topic rows | 2025 share | 2026 topic rows | 2026 share |
|---|---:|---:|---:|---:|
| Official LIS subject | 959 | 17.92% | 98 | 2.27% |
| Derived from LIS bill summary | 2,770 | 51.76% | 871 | 20.17% |
| Derived from LIS bill description | 303 | 5.66% | 1,433 | 33.18% |
| Unclassified | 1,320 | 24.66% | 1,917 | 44.39% |
| **Total** | **5,352** | **100.00%** | **4,319** | **100.00%** |

Raw official-subject rows are not the same as analytical topic rows. Parent rollup and same-parent consolidation can reduce the number of displayed analytical rows while preserving the exact child evidence.

The unusually low 2026 official-source share must be treated as a source-completeness review item. `CIBillSubjects.csv` contains 1,103 raw rows in 2025 but only 110 in the current 2026 snapshot.

## F. Vote calculations

### Official vote codes

- `Y`: Yes
- `N`: No
- `A`: Abstained
- `X`: Not voting

Yes/No are directional. Abstained and not voting remain visible but are excluded from directional denominators.

### Yes-vote rate

```text
Yes-vote rate = Yes ÷ (Yes + No) × 100
```

| Year | Yes | No | Directional denominator | Yes rate |
|---|---:|---:|---:|---:|
| 2025 | 166,794 | 45,983 | 212,777 | 78.39% |
| 2026 | 237,742 | 67,235 | 304,977 | 77.95% |

### Party majority

For every vote event and party:

```text
Yes position when party Yes > party No
No position when party No > party Yes
No position when party Yes = party No
```

Abstained and not-voting records do not affect this comparison.

### Party break

```text
Party break = member cast Yes/No
              AND own party has a clear position
              AND member vote differs from that position

Party-break rate = party breaks ÷ eligible own-party comparisons × 100
```

| Year | Party breaks | Eligible own-party comparisons | Rate |
|---|---:|---:|---:|
| 2025 | 8,109 | 212,137 | 3.82% |
| 2026 | 10,049 | 304,281 | 3.30% |

### True cross-party vote

```text
True cross-party = party break
                   AND other party has a clear position
                   AND member vote matches the other party's position

Cross-party rate = true cross-party votes ÷ cross-party eligible votes × 100
```

| Year | True cross-party votes | Eligible comparisons | Rate |
|---|---:|---:|---:|
| 2025 | 3,930 | 211,310 | 1.86% |
| 2026 | 4,973 | 302,786 | 1.64% |

The reported change is `1.6424% - 1.8598% = -0.2174 percentage points`, displayed as a 0.22-point decrease.

### Subject vote counts

The subject analysis uses one member-vote-subject row. It answers “how many recorded member votes were connected to this subject?” A vote connected to multiple subjects is represented once in each applicable subject, so subject counts must not be added together to recreate the canonical vote total.

The dashboard's “highest cross-party rate” comparison requires at least 1,000 eligible member-vote-subject rows, preventing a tiny denominator from leading the chart.

## G. Sponsorship calculation

Sponsors come directly from `Sponsors.csv`. Sponsor roles and ordering remain separate. The vote/bill bridge connects a sponsored bill to vote events; `vote_fact` then identifies the sponsor's own recorded vote.

This remains a supported backend analytical layer. It is intentionally omitted from the simplified leadership dashboard so the page stays focused on recorded voting, subjects, session change, and bill pathways.

```text
Sponsor Yes rate = sponsor-linked Yes votes
                   ÷ sponsor-linked (Yes + No) votes × 100
```

This is an association between sponsorship and recorded voting. It does not prove causation, persuasion, or private support.

## H. Bill pathways, committees, and vote statements

### Pathway markers

- Became law: official history contains Governor approval/chapter evidence.
- Left in committee: official history contains the phrase “Left in.”
- Failed or stricken: official history explicitly contains failed, defeated, or stricken language.

These markers are reproducible but not mutually exclusive final-disposition categories.

### Committees

Committee counts come from official committee reference and assignment files. A membership record is one member on one committee, not one unique person and not proof of action on every referred bill.

### Vote statements

`recorded_vote` always remains the official vote. `intended_vote` is filled only when the statement explicitly says intended yea/yes or nay/no. It never replaces the official record.

## I. How everything was verified

### Automated controls

On September 8, 2026:

```text
336 tests passed
```

The suite covers raw-to-processed vote reconciliation, required columns, allowed values, canonical uniqueness, member and party joins, chamber identity, party-majority ties, non-directional votes, party-break and cross-party implications, vote/bill one-to-many behavior, subject provenance and priority, parent hierarchy, source samples, tendency thresholds, and year-over-year comparability.

### In-pipeline controls

Production validators run on full datasets where practical. They stop rather than silently continue when core joins, allowed labels, provenance rules, logical implications, or bill coverage fail.

### Deterministic topic audit

The annual consolidated QA file contains rule populations, stratified samples, official samples, unclassified samples, summary-selection checks, broad-rule candidates, multi-topic candidates, source-agreement comparisons, and risk bands. Risk is a review priority, not a probability of error.

### Dashboard trace

- Delegate → subject → supporting bill and vote record.
- Subject → delegates → Yes, No, abstained, not-voting, and true cross-party records.
- Bill → description, analytical subject, provenance, exact child, broader parent, history, vote totals, and statements.
- Sponsorship remains traceable through the separate processed sponsor tables, outside the leadership page.
- Tables can be downloaded for independent review.

### Reproduction commands

```powershell
$env:LIS_ANALYSIS_YEAR = "2025"
.\.venv\Scripts\python.exe lis_pipeline.py
$env:LIS_ANALYSIS_YEAR = "2026"
.\.venv\Scripts\python.exe lis_pipeline.py
.\.venv\Scripts\python.exe topic_stance_analysis.py
.\.venv\Scripts\python.exe year_over_year_analysis.py
.\.venv\Scripts\python.exe -m pytest -q
```

### Adding a future regular session

```powershell
.\.venv\Scripts\python.exe onboard_session.py 2027
```

This command reuses the existing pipeline and validations. Before processing, it prints every required file's row count, byte size, and official `Last-Modified` value when available. It warns when `CIBillSubjects.csv` covers less than 5% of bills or is more than 30 days older than `BILLS.CSV`. These are review thresholds, not claims that the source is wrong. Existing years are retained, the latest earlier processed year is compared automatically, and the dashboard discovers all successfully processed regular sessions. Full-data tests can also be directed to retained years with `LIS_TEST_YEARS`.

## J. Verification still missing

1. Independently confirm the completeness of the 2026 official-subject download.
2. Obtain human sign-off on the high- and very-high-risk derived-topic review queue.
3. Add one consolidated source/run manifest with hashes and timestamps.
4. Independently recheck documented party fallbacks.
5. Create and test mutually exclusive final-outcome definitions before publishing final-disposition percentages.
6. Structure committee referral/report/action events before drawing committee-performance conclusions.
7. Have a second person manually trace and sign off on the headline dashboard figures.

## K. Confidence statement

The strongest accurate statement is:

> The results are reproducible, source-traceable, and tested against 336 automated cases. The calculations implement the documented definitions. Remaining uncertainty is explicitly limited to external source completeness, human semantic review of derived topics, selected party fallbacks, and analytical questions that have not yet been modeled as mutually exclusive outcomes.

This is more credible than claiming literal 100% certainty, because it explains both the evidence and its boundaries.
