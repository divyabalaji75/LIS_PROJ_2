# Virginia LIS Legislative Voting Analysis — v1

A reproducible Python data pipeline for analyzing observable voting behavior
in the Virginia General Assembly using official Virginia Legislative
Information System (LIS) data.

## Project Status

**Version:** v1 baseline  
**Sessions analyzed:** 2025 and 2026 Regular Sessions  
**Primary source:** Virginia Legislative Information System (LIS)  
**Pipeline status:** Automated validation passed  
**Manual source validation:** In progress  
**Topic methodology:** Functional, but manual QA identified opportunities for improvement

> v1 is being preserved as the validated baseline before development of an
> expanded v2 methodology.

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

The authoritative source for v1 is the official Virginia Legislative
Information System (LIS) CSV data.

Core v1 source files include:

- `BILLS.CSV`
- `HISTORY.CSV`
- `VOTE.CSV`
- `Members.csv`
- `CIBillSubjects.csv`

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