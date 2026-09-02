from pathlib import Path

import pandas as pd
import pytest


# =========================================================
# CONFIG
# =========================================================

PROCESSED_ROOT = Path("data/processed")

YEARS = [
    2025,
    2026,
]

ALLOWED_CLASSIFICATIONS = {
    "Official LIS subject",
    "Derived from LIS bill description",
    "Unclassified",
}


# =========================================================
# HELPERS
# =========================================================

def load_processed_file(filename):

    path = (
        PROCESSED_ROOT
        / filename
    )

    if not path.exists():

        pytest.fail(
            f"Missing required file: {path}"
        )

    return pd.read_csv(
        path,
        dtype=str
    )


def load_bill_lookup(year):

    return load_processed_file(
        f"bill_lookup_{year}.csv"
    )


def load_topic_lookup(year):

    return load_processed_file(
        f"bill_topic_lookup_{year}.csv"
    )


def load_official_subjects(year):

    return load_processed_file(
        f"official_lis_subjects_{year}.csv"
    )


def load_derived_topics(year):

    return load_processed_file(
        f"derived_from_lis_bill_description_{year}.csv"
    )


def load_unclassified(year):

    return load_processed_file(
        f"unclassified_bills_{year}.csv"
    )


def normalize_text(series):

    return (
        series
        .fillna("")
        .astype(str)
        .str.strip()
    )


# =========================================================
# TEST 1
# BILL LOOKUP REQUIRED COLUMNS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_bill_lookup_required_columns(year):

    df = load_bill_lookup(year)

    required = {
        "Bill_id",
        "Bill_description",
    }

    missing = (
        required
        - set(df.columns)
    )

    assert not missing, (
        f"{year}: bill_lookup missing "
        f"required columns: {missing}"
    )


# =========================================================
# TEST 2
# TOPIC LOOKUP REQUIRED COLUMNS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_topic_lookup_required_columns(year):

    df = load_topic_lookup(year)

    required = {
        "Bill_id",
        "topic_name",
        "classification",
    }

    missing = (
        required
        - set(df.columns)
    )

    assert not missing, (
        f"{year}: bill_topic_lookup missing "
        f"required columns: {missing}"
    )


# =========================================================
# TEST 3
# TOPIC LOOKUP IS NOT EMPTY
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_topic_lookup_not_empty(year):

    df = load_topic_lookup(year)

    assert len(df) > 0, (
        f"{year}: bill_topic_lookup is empty"
    )


# =========================================================
# TEST 4
# ONLY THREE PERMITTED CLASSIFICATIONS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_only_allowed_classifications(year):

    df = load_topic_lookup(year)

    actual = set(
        normalize_text(
            df["classification"]
        )
        .unique()
    )

    invalid = (
        actual
        - ALLOWED_CLASSIFICATIONS
    )

    assert not invalid, (
        f"{year}: unexpected classification "
        f"values found: {invalid}"
    )


# =========================================================
# TEST 5
# NO BLANK CLASSIFICATION
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_no_blank_classification(year):

    df = load_topic_lookup(year)

    blank_count = (
        normalize_text(
            df["classification"]
        )
        .eq("")
        .sum()
    )

    assert blank_count == 0, (
        f"{year}: {blank_count} topic rows "
        f"have blank classification"
    )


# =========================================================
# TEST 6
# NO BLANK BILL ID
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_topic_lookup_no_blank_bill_id(year):

    df = load_topic_lookup(year)

    blank_count = (
        normalize_text(
            df["Bill_id"]
        )
        .eq("")
        .sum()
    )

    assert blank_count == 0, (
        f"{year}: {blank_count} topic rows "
        f"have blank Bill_id"
    )


# =========================================================
# TEST 7
# NO BLANK TOPIC NAME
#
# Unclassified should still have an explicit
# topic_name such as "Unclassified".
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_topic_lookup_no_blank_topic_name(year):

    df = load_topic_lookup(year)

    blank_count = (
        normalize_text(
            df["topic_name"]
        )
        .eq("")
        .sum()
    )

    assert blank_count == 0, (
        f"{year}: {blank_count} topic rows "
        f"have blank topic_name"
    )


# =========================================================
# TEST 8
# EVERY BILL IN BILL LOOKUP HAS CLASSIFICATION COVERAGE
#
# A bill may have multiple official subject rows.
# Therefore compare SETS of Bill_id values.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_every_bill_has_topic_classification(year):

    bills = load_bill_lookup(year)
    topics = load_topic_lookup(year)

    bill_ids = set(
        normalize_text(
            bills["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    topic_bill_ids = set(
        normalize_text(
            topics["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    missing = (
        bill_ids
        - topic_bill_ids
    )

    assert not missing, (
        f"{year}: bills missing from "
        f"bill_topic_lookup: "
        f"{sorted(missing)[:20]}"
    )


# =========================================================
# TEST 9
# TOPIC LOOKUP DOES NOT CONTAIN UNKNOWN BILLS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_topic_lookup_contains_only_known_bills(year):

    bills = load_bill_lookup(year)
    topics = load_topic_lookup(year)

    bill_ids = set(
        normalize_text(
            bills["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    topic_bill_ids = set(
        normalize_text(
            topics["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    unknown = (
        topic_bill_ids
        - bill_ids
    )

    assert not unknown, (
        f"{year}: bill_topic_lookup contains "
        f"unknown bills: "
        f"{sorted(unknown)[:20]}"
    )


# =========================================================
# TEST 10
# OFFICIAL SUBJECT FILE USES ONLY OFFICIAL LABEL
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_official_subject_file_classification(year):

    df = load_official_subjects(year)

    assert (
        normalize_text(
            df["classification"]
        )
        ==
        "Official LIS subject"
    ).all(), (
        f"{year}: official subject file contains "
        f"non-official classification values"
    )


# =========================================================
# TEST 11
# DERIVED FILE USES ONLY DERIVED LABEL
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_derived_file_classification(year):

    df = load_derived_topics(year)

    assert (
        normalize_text(
            df["classification"]
        )
        ==
        "Derived from LIS bill description"
    ).all(), (
        f"{year}: derived topic file contains "
        f"unexpected classification values"
    )


# =========================================================
# TEST 12
# UNCLASSIFIED FILE USES ONLY UNCLASSIFIED LABEL
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_unclassified_file_classification(year):

    df = load_unclassified(year)

    assert (
        normalize_text(
            df["classification"]
        )
        ==
        "Unclassified"
    ).all(), (
        f"{year}: unclassified file contains "
        f"unexpected classification values"
    )


# =========================================================
# TEST 13
# UNCLASSIFIED TOPIC NAME SHOULD BE EXPLICIT
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_unclassified_topic_name_explicit(year):

    df = load_unclassified(year)

    assert (
        normalize_text(
            df["topic_name"]
        )
        ==
        "Unclassified"
    ).all(), (
        f"{year}: unclassified rows do not all "
        f"use topic_name='Unclassified'"
    )


# =========================================================
# TEST 14
# OFFICIAL BILLS MUST NOT ALSO APPEAR AS DERIVED
#
# Official LIS subject takes precedence.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_official_subject_precedence_over_derived(year):

    official = load_official_subjects(year)
    derived = load_derived_topics(year)

    official_bill_ids = set(
        normalize_text(
            official["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    derived_bill_ids = set(
        normalize_text(
            derived["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    overlap = (
        official_bill_ids
        &
        derived_bill_ids
    )

    assert not overlap, (
        f"{year}: bills classified both "
        f"Official and Derived: "
        f"{sorted(overlap)[:20]}"
    )


# =========================================================
# TEST 15
# OFFICIAL BILLS MUST NOT ALSO BE UNCLASSIFIED
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_official_bills_not_unclassified(year):

    official = load_official_subjects(year)
    unclassified = load_unclassified(year)

    official_bill_ids = set(
        normalize_text(
            official["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    unclassified_bill_ids = set(
        normalize_text(
            unclassified["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    overlap = (
        official_bill_ids
        &
        unclassified_bill_ids
    )

    assert not overlap, (
        f"{year}: official LIS subject bills "
        f"also appear as Unclassified: "
        f"{sorted(overlap)[:20]}"
    )


# =========================================================
# TEST 16
# DERIVED BILLS MUST NOT ALSO BE UNCLASSIFIED
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_derived_bills_not_unclassified(year):

    derived = load_derived_topics(year)
    unclassified = load_unclassified(year)

    derived_bill_ids = set(
        normalize_text(
            derived["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    unclassified_bill_ids = set(
        normalize_text(
            unclassified["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    overlap = (
        derived_bill_ids
        &
        unclassified_bill_ids
    )

    assert not overlap, (
        f"{year}: derived bills also appear "
        f"as Unclassified: "
        f"{sorted(overlap)[:20]}"
    )


# =========================================================
# TEST 17
# BILL-LEVEL CLASSIFICATION PARTITION RECONCILES
#
# Every bill must belong to exactly one provenance bucket
# at the BILL level:
#
# Official
# OR Derived
# OR Unclassified
#
# Official may have multiple subject rows,
# but still represents one bill-level provenance bucket.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_bill_level_classification_partition(year):

    bills = load_bill_lookup(year)
    official = load_official_subjects(year)
    derived = load_derived_topics(year)
    unclassified = load_unclassified(year)

    all_bills = set(
        normalize_text(
            bills["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    official_ids = set(
        normalize_text(
            official["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    derived_ids = set(
        normalize_text(
            derived["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    unclassified_ids = set(
        normalize_text(
            unclassified["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    combined = (
        official_ids
        |
        derived_ids
        |
        unclassified_ids
    )

    assert combined == all_bills, (
        f"{year}: bill-level classification "
        f"partition does not reconcile.\n"
        f"Missing: "
        f"{sorted(all_bills - combined)[:20]}\n"
        f"Unexpected: "
        f"{sorted(combined - all_bills)[:20]}"
    )


# =========================================================
# TEST 18
# NO EXACT DUPLICATE TOPIC ROWS
#
# Same bill/topic/classification row should not repeat.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_no_duplicate_topic_rows(year):

    df = load_topic_lookup(year)

    duplicates = df[
        df.duplicated(
            subset=[
                "Bill_id",
                "topic_name",
                "classification",
            ],
            keep=False
        )
    ]

    assert len(duplicates) == 0, (
        f"{year}: found {len(duplicates)} "
        f"duplicate bill/topic/classification rows"
    )


# =========================================================
# TEST 19
# UNCLASSIFIED BILLS HAVE EXACTLY ONE TOPIC ROW
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_unclassified_bills_have_one_row(year):

    df = load_unclassified(year)

    counts = (
        df
        .groupby(
            "Bill_id"
        )
        .size()
    )

    invalid = counts[
        counts != 1
    ]

    assert len(invalid) == 0, (
        f"{year}: unclassified bills with "
        f"unexpected row counts: "
        f"{invalid.to_dict()}"
    )


# =========================================================
# TEST 20
# DERIVED BILL TOPICS ARE NOT BLANK
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_derived_topics_not_blank(year):

    df = load_derived_topics(year)

    blank_count = (
        normalize_text(
            df["topic_name"]
        )
        .eq("")
        .sum()
    )

    assert blank_count == 0, (
        f"{year}: {blank_count} derived rows "
        f"have blank topic_name"
    )


# =========================================================
# TEST 21
# OFFICIAL SUBJECT TOPICS ARE NOT BLANK
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_official_topics_not_blank(year):

    df = load_official_subjects(year)

    blank_count = (
        normalize_text(
            df["topic_name"]
        )
        .eq("")
        .sum()
    )

    assert blank_count == 0, (
        f"{year}: {blank_count} official subject rows "
        f"have blank topic_name"
    )


# =========================================================
# TEST 22
# CLASSIFICATION FILES RECONSTRUCT TOPIC LOOKUP
#
# Union of:
# official + derived + unclassified
#
# should match bill_topic_lookup rows.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_classification_files_reconstruct_topic_lookup(year):

    topic_lookup = load_topic_lookup(year)

    official = load_official_subjects(year)
    derived = load_derived_topics(year)
    unclassified = load_unclassified(year)

    key_columns = [
        "Bill_id",
        "topic_name",
        "classification",
    ]

    expected = pd.concat(
        [
            official[key_columns],
            derived[key_columns],
            unclassified[key_columns],
        ],
        ignore_index=True
    )

    actual_keys = set(
        map(
            tuple,
            topic_lookup[
                key_columns
            ]
            .fillna("")
            .astype(str)
            .apply(
                lambda col:
                    col.str.strip()
            )
            .to_numpy()
        )
    )

    expected_keys = set(
        map(
            tuple,
            expected[
                key_columns
            ]
            .fillna("")
            .astype(str)
            .apply(
                lambda col:
                    col.str.strip()
            )
            .to_numpy()
        )
    )

    missing = (
        expected_keys
        - actual_keys
    )

    extra = (
        actual_keys
        - expected_keys
    )

    assert not missing, (
        f"{year}: topic lookup missing "
        f"classification rows: "
        f"{list(missing)[:10]}"
    )

    assert not extra, (
        f"{year}: topic lookup contains "
        f"unexpected rows: "
        f"{list(extra)[:10]}"
    )


# =========================================================
# TEST 23
# EVERY DERIVED BILL HAS A LIS BILL DESCRIPTION
#
# We derive only from LIS Bill_description.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_derived_bills_have_bill_description(year):

    bills = load_bill_lookup(year)
    derived = load_derived_topics(year)

    bills = bills.copy()

    bills["Bill_id"] = (
        normalize_text(
            bills["Bill_id"]
        )
        .str.upper()
    )

    bills[
        "Bill_description"
    ] = normalize_text(
        bills[
            "Bill_description"
        ]
    )

    derived_ids = set(
        normalize_text(
            derived["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    check = bills[
        bills[
            "Bill_id"
        ]
        .isin(
            derived_ids
        )
    ]

    missing_descriptions = check[
        check[
            "Bill_description"
        ]
        .eq("")
    ]

    assert len(
        missing_descriptions
    ) == 0, (
        f"{year}: derived topic bills exist "
        f"without LIS Bill_description:\n"
        f"{missing_descriptions[['Bill_id']].to_string(index=False)}"
    )


# =========================================================
# TEST 24
# UNCLASSIFIED BILLS MUST NOT APPEAR IN OFFICIAL
# OR DERIVED FILES
#
# This is redundant by design.
# It protects the most conservative classification bucket.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_unclassified_is_exclusive(year):

    official = load_official_subjects(year)
    derived = load_derived_topics(year)
    unclassified = load_unclassified(year)

    classified_ids = (
        set(
            normalize_text(
                official["Bill_id"]
            )
            .str.upper()
            .unique()
        )
        |
        set(
            normalize_text(
                derived["Bill_id"]
            )
            .str.upper()
            .unique()
        )
    )

    unclassified_ids = set(
        normalize_text(
            unclassified["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    overlap = (
        classified_ids
        &
        unclassified_ids
    )

    assert not overlap, (
        f"{year}: unclassified bills also "
        f"appear in classified outputs: "
        f"{sorted(overlap)[:20]}"
    )