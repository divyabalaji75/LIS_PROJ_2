"""
Structural bill-topic classification tests.

These tests answer:

    Did the pipeline obey the classification architecture?

They do NOT independently prove that every derived topic is
substantively correct.

Substantive rule validity is tested in:

    test_topic_rule_behavior.py

Independent reconciliation to raw LIS source files is tested in:

    test_source_sample.py
"""

from pathlib import Path

import pandas as pd
import pytest

from lis_common import configured_test_years


YEARS = configured_test_years()

ROOT = Path(
    "data/processed"
)


CLASSES = {
    "Official LIS subject",
    "Derived from LIS bill summary",
    "Derived from LIS bill description",
    "Unclassified",
}


FILES = {

    "official_lis_subjects":
        "Official LIS subject",

    "derived_from_lis_bill_summary":
        "Derived from LIS bill summary",

    "derived_from_lis_bill_description":
        "Derived from LIS bill description",

    "unclassified_bills":
        "Unclassified",
}


# =========================================================
# HELPERS
# =========================================================

def load(
    name,
    year,
):

    path = (
        ROOT
        /
        f"{name}_{year}.csv"
    )

    assert path.exists(), (
        f"Missing required file: {path}"
    )

    return (
        pd.read_csv(
            path,
            dtype=str,
        )
        .fillna("")
    )


# =========================================================
# 1. COMBINED TOPIC LOOKUP CONTRACT
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_combined_topic_lookup_contract(
    year,
):

    topics = load(
        "bill_topic_lookup",
        year,
    )

    required = {
        "Bill_id",
        "topic_name",
        "classification",
        "lis_subject_name",
        "lis_parent_subject",
        "source_file",
        "source_text_used",
        "rule_derived",
    }

    assert (
        required
        <=
        set(
            topics.columns
        )
    )

    assert not topics.empty

    required_nonblank = [
        "Bill_id",
        "topic_name",
        "classification",
    ]

    assert (
        topics[
            required_nonblank
        ]
        .apply(
            lambda series:
                series
                .astype(str)
                .str.strip()
                .ne("")
                .all()
        )
        .all()
    )

    assert (
        set(
            topics[
                "classification"
            ]
        )
        <=
        CLASSES
    )

    assert not (
        topics
        .duplicated()
        .any()
    )


# =========================================================
# 2. EVERY BILL HAS EXACTLY ONE PROVENANCE TIER
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_every_known_bill_has_exactly_one_provenance_tier(
    year,
):

    bills = load(
        "bill_lookup",
        year,
    )

    topics = load(
        "bill_topic_lookup",
        year,
    )

    assert not (
        bills[
            "Bill_id"
        ]
        .duplicated()
        .any()
    )

    assert (
        set(
            topics[
                "Bill_id"
            ]
        )
        ==
        set(
            bills[
                "Bill_id"
            ]
        )
    )

    assert (
        topics
        .groupby(
            "Bill_id"
        )[
            "classification"
        ]
        .nunique()
        .eq(1)
        .all()
    )


# =========================================================
# 3. PROVENANCE FILES PROJECT INTO THE COMBINED LOOKUP
#
# These files are separate production views of the same
# bill-level classification architecture.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_provenance_files_are_exact_key_projections(
    year,
):

    combined = load(
        "bill_topic_lookup",
        year,
    )

    key = [
        "Bill_id",
        "topic_name",
        "classification",
    ]

    for (
        name,
        classification,
    ) in FILES.items():

        separate = load(
            name,
            year,
        )

        assert (
            set(
                separate[
                    "classification"
                ]
            )
            ==
            {
                classification
            }
        )

        expected = (
            combined.loc[
                combined[
                    "classification"
                ]
                .eq(
                    classification
                ),
                key,
            ]
        )

        actual_keys = set(
            map(
                tuple,
                separate[
                    key
                ]
                .to_numpy(),
            )
        )

        expected_keys = set(
            map(
                tuple,
                expected.to_numpy(),
            )
        )

        assert (
            actual_keys
            ==
            expected_keys
        )


# =========================================================
# 4. OFFICIAL SUBJECT OUTPUT RETAINS OFFICIAL EVIDENCE
#
# Raw-source correctness itself is tested independently in
# test_source_sample.py.
#
# Here we only verify the processed structural contract.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_official_subject_processed_evidence_contract(
    year,
):

    official = load(
        "official_lis_subjects",
        year,
    )

    assert (
        official[
            "lis_subject_name"
        ]
        .str.strip()
        .ne("")
        .all()
    )

    assert (
        official[
            "source_file"
        ]
        .eq(
            "CIBillSubjects.csv"
        )
        .all()
    )

    assert (
        official[
            "source_text_used"
        ]
        ==
        official[
            "lis_subject_name"
        ]
    ).all()

    assert (
        official[
            "rule_derived"
        ]
        .str.lower()
        .isin(
            [
                "false",
                "0",
            ]
        )
        .all()
    )

    expected_rollup = (
        official[
            "lis_parent_subject"
        ]
        .where(
            official[
                "lis_parent_subject"
            ]
            .ne(""),
            official[
                "lis_subject_name"
            ],
        )
    )

    assert (
        official[
            "topic_name"
        ]
        ==
        expected_rollup
    ).all()


# =========================================================
# 5. DERIVED EVIDENCE CONTRACT
#
# Derived rows must:
#
#     use the expected official LIS source text
#     be marked as rule-derived
#     not pretend to contain official LIS subject values
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_derived_evidence_contract_and_official_priority(
    year,
):

    combined = load(
        "bill_topic_lookup",
        year,
    )

    official_bills = set(
        combined.loc[
            combined[
                "classification"
            ]
            .eq(
                "Official LIS subject"
            ),
            "Bill_id",
        ]
    )

    cases = (

        (
            "derived_from_lis_bill_summary",
            "Derived from LIS bill summary",
            "Summaries.csv",
        ),

        (
            "derived_from_lis_bill_description",
            "Derived from LIS bill description",
            "BILLS.CSV",
        ),

    )

    for (
        name,
        classification,
        source,
    ) in cases:

        derived = load(
            name,
            year,
        )

        assert (
            set(
                derived[
                    "classification"
                ]
            )
            ==
            {
                classification
            }
        )

        assert (
            set(
                derived[
                    "Bill_id"
                ]
            )
            .isdisjoint(
                official_bills
            )
        )

        assert (
            derived[
                "source_file"
            ]
            .eq(
                source
            )
            .all()
        )

        assert (
            derived[
                "source_text_used"
            ]
            .str.strip()
            .ne("")
            .all()
        )

        assert (
            derived[
                "rule_derived"
            ]
            .str.lower()
            .isin(
                [
                    "true",
                    "1",
                ]
            )
            .all()
        )

        assert (
            derived[
                "lis_subject_name"
            ]
            .eq("")
            .all()
        )

        assert (
            derived[
                "lis_parent_subject"
            ]
            .eq("")
            .all()
        )


# =========================================================
# 6. PROVENANCE PRECEDENCE
#
# Summary-derived bills must not fall through to description.
#
# Description-derived bills must not also be Unclassified.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_summary_precedes_description_and_unclassified(
    year,
):

    summary = set(
        load(
            "derived_from_lis_bill_summary",
            year,
        )[
            "Bill_id"
        ]
    )

    description = set(
        load(
            "derived_from_lis_bill_description",
            year,
        )[
            "Bill_id"
        ]
    )

    unclassified = load(
        "unclassified_bills",
        year,
    )

    unclassified_ids = set(
        unclassified[
            "Bill_id"
        ]
    )

    assert (
        summary
        .isdisjoint(
            description
        )
    )

    assert (
        summary
        .isdisjoint(
            unclassified_ids
        )
    )

    assert (
        description
        .isdisjoint(
            unclassified_ids
        )
    )

    assert (
        unclassified
        .groupby(
            "Bill_id"
        )
        .size()
        .eq(1)
        .all()
    )

    assert (
        unclassified[
            "topic_name"
        ]
        .eq(
            "Unclassified"
        )
        .all()
    )


# =========================================================
# 7. TOPIC COVERAGE RECONCILES TO BILL PARTITION
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_topic_coverage_reconciles_to_bill_partition(
    year,
):

    coverage = load(
        "topic_coverage",
        year,
    )

    topics = (
        load(
            "bill_topic_lookup",
            year,
        )[
            [
                "Bill_id",
                "classification",
            ]
        ]
        .drop_duplicates()
    )

    expected = (
        topics
        .groupby(
            "classification"
        )[
            "Bill_id"
        ]
        .nunique()
        .to_dict()
    )

    actual = (
        pd.to_numeric(
            coverage[
                "bill_count"
            ]
        )
        .groupby(
            coverage[
                "classification"
            ]
        )
        .sum()
        .to_dict()
    )

    assert (
        actual
        ==
        expected
    )

    assert (
        coverage[
            "classification"
        ]
        .isin(
            CLASSES
        )
        .all()
    )

    assert (
        pd.to_numeric(
            coverage[
                "bill_percentage"
            ]
        )
        .sum()
        ==
        pytest.approx(
            100.0,
            abs=0.02,
        )
    )