# Virginia LIS Legislative Voting Analysis

A reproducible Python data pipeline for analyzing observable voting behavior
in the Virginia General Assembly using official Virginia Legislative
Information System (LIS) data.

## Project Status

**Version:** expanded LIS analysis
**Sessions analyzed:** 2025 and 2026 Regular Sessions  
**Primary source:** Virginia Legislative Information System (LIS)  
**Pipeline status:** Automated validation passed  
**Manual source validation:** In progress  
**Topic methodology:** Official LIS hierarchy first, then summary and bill-description fallbacks

---

# 1. Project Purpose

This project converts Virginia LIS legislative data into reproducible
analytical datasets for studying observable legislative behavior.

The project currently focuses on two major questions:

1. How often does a legislator cast a directional vote that differs from the
   majority position of their own party and matches the majority position of
   the other party?

2. How does a legislator vote on legislation associated with different policy
   subjects?

The project measures **observable legislative behavior**.

It does not attempt to infer a legislator's private beliefs, motivations,
ideology, or psychological persuadability.

---

# 2. Data Source

The authoritative source is the official Virginia Legislative
Information System (LIS) CSV data.

Official LIS source files include:

- `BILLS.CSV`
- `HISTORY.CSV`
- `VOTE.CSV`
- `Members.csv`
- `CIBillSubjects.csv`
- `CIParentChildSubjects.csv`
- `Summaries.csv`
- `Sponsors.csv`
- `Committees.csv`
- `CommitteeMembers.csv`
- `VoteStatements.csv`

Party affiliation is maintained separately in:

- `data/reference/party_2025.csv`
- `data/reference/party_2026.csv`

Raw LIS files are preserved separately from processed analytical outputs.

The pipeline does not modify the original raw source files.

---

# 3. Core Pipeline

The primary pipeline is:

`lis_pipeline.py`

Conceptually, the pipeline performs:

```text
Raw LIS files
      ↓
Parse recorded votes
      ↓
Attach member metadata
      ↓
Attach party reference
      ↓
Reconcile missing member metadata
      ↓
Calculate party positions
      ↓
Calculate party breaks
      ↓
Calculate cross-party votes
      ↓
Connect vote events to bills
      ↓
Classify bills by topic
      ↓
Create delegate-level analytical tables
      ↓
Run validation
      ↓
Save processed outputs
```

Topic classification uses exactly one provenance tier per bill, in this order:

1. Official LIS subject, rolled up to its official parent subject when one exists.
2. Existing derived-topic and exclusion rules applied to the best available LIS summary.
3. The same rules applied to `BILLS.CSV` `Bill_description`.
4. Unclassified.

The exact official child subject is retained as `lis_subject_name`; its broader
official subject is retained as `lis_parent_subject`. Sponsorship, committee,
committee-membership, and vote-statement outputs remain separate analytical
layers and do not affect topic classification. Recorded votes in vote statements
are preserved separately from any explicitly stated intended yea or nay.
