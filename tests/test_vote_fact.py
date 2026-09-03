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

EXPECTED_VOTE_CODES = {
    "Y",
    "N",
    "X",
    "A",
    "P"
}


# =========================================================
# HELPERS
# =========================================================

def load_vote_fact(year):

    path = (
        PROCESSED_ROOT
        / f"vote_fact_{year}.csv"
    )

    if not path.exists():

        pytest.fail(
            f"Missing required file: {path}"
        )

    df = pd.read_csv(
        path,
        dtype=str
    )

    return df


# =========================================================
# TEST: REQUIRED COLUMNS EXIST
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_required_columns(year):

    df = load_vote_fact(
        year
    )

    required_columns = {
        "year",
        "vote_id",
        "member_id",
        "MBR_NAME",
        "MBR_HOU",
        "party",
        "vote",
    }

    missing = (
        required_columns
        - set(df.columns)
    )

    assert not missing, (
        f"{year}: vote_fact is missing "
        f"required columns: {missing}"
    )


# =========================================================
# TEST: TABLE IS NOT EMPTY
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_not_empty(year):

    df = load_vote_fact(
        year
    )

    assert len(df) > 0, (
        f"{year}: vote_fact is empty"
    )


# =========================================================
# TEST: YEAR COLUMN MATCHES FILE YEAR
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_year_matches(year):

    df = load_vote_fact(
        year
    )

    years_found = set(
        pd.to_numeric(
            df["year"],
            errors="coerce"
        )
        .dropna()
        .astype(int)
        .unique()
    )

    assert years_found == {year}, (
        f"{year}: unexpected year values "
        f"found: {years_found}"
    )


# =========================================================
# TEST: NO MISSING VOTE IDS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_no_missing_vote_id(year):

    df = load_vote_fact(
        year
    )

    missing = (
        df["vote_id"]
        .fillna("")
        .str.strip()
        .eq("")
        .sum()
    )

    assert missing == 0, (
        f"{year}: {missing} rows "
        f"have missing vote_id"
    )


# =========================================================
# TEST: NO MISSING MEMBER IDS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_no_missing_member_id(year):

    df = load_vote_fact(
        year
    )

    missing = (
        df["member_id"]
        .fillna("")
        .str.strip()
        .eq("")
        .sum()
    )

    assert missing == 0, (
        f"{year}: {missing} rows "
        f"have missing member_id"
    )


# =========================================================
# TEST: NO MISSING MEMBER NAMES
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_no_missing_member_name(year):

    df = load_vote_fact(
        year
    )

    missing = (
        df["MBR_NAME"]
        .fillna("")
        .str.strip()
        .eq("")
        .sum()
    )

    assert missing == 0, (
        f"{year}: {missing} vote rows "
        f"have missing member names"
    )


# =========================================================
# TEST: CHAMBER VALUES VALID
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_valid_chamber(year):

    df = load_vote_fact(
        year
    )

    actual = set(
        df["MBR_HOU"]
        .fillna("")
        .str.strip()
        .str.upper()
        .unique()
    )

    expected = {
        "H",
        "S",
    }

    invalid = (
        actual
        - expected
    )

    assert not invalid, (
        f"{year}: invalid chamber values "
        f"found: {invalid}"
    )


# =========================================================
# TEST: MEMBER PREFIX AGREES WITH CHAMBER
#
# Hxxxx -> H
# Sxxxx -> S
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_member_id_prefix_matches_chamber(year):

    df = load_vote_fact(
        year
    ).copy()

    df["expected_chamber"] = (
        df["member_id"]
        .fillna("")
        .str.strip()
        .str.upper()
        .str[:1]
    )

    df["actual_chamber"] = (
        df["MBR_HOU"]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    mismatch = df[
        df["expected_chamber"]
        !=
        df["actual_chamber"]
    ]

    assert len(mismatch) == 0, (
        f"{year}: {len(mismatch)} rows "
        f"have member_id/chamber mismatch"
    )


# =========================================================
# TEST: PARTY VALUES VALID
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_valid_party(year):

    df = load_vote_fact(
        year
    )

    actual = set(
        df["party"]
        .fillna("")
        .str.strip()
        .str.upper()
        .unique()
    )

    expected = {
        "D",
        "R",
        "I",
    }

    invalid = (
        actual
        - expected
    )

    assert not invalid, (
        f"{year}: invalid party values "
        f"found: {invalid}"
    )


# =========================================================
# TEST: NO BLANK PARTY
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_no_missing_party(year):

    df = load_vote_fact(
        year
    )

    missing = (
        df["party"]
        .fillna("")
        .str.strip()
        .eq("")
        .sum()
    )

    assert missing == 0, (
        f"{year}: {missing} vote rows "
        f"have missing party"
    )


# =========================================================
# TEST: VOTE CODES VALID
#
# IMPORTANT:
# This reflects the currently accepted 2025/2026
# analytical vote codes only.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_vote_codes_expected(year):

    df = load_vote_fact(
        year
    )

    actual = set(
        df["vote"]
        .fillna("")
        .str.strip()
        .str.upper()
        .unique()
    )

    invalid = (
        actual
        - EXPECTED_VOTE_CODES
    )

    assert not invalid, (
        f"{year}: unexpected vote codes "
        f"found: {invalid}"
    )


# =========================================================
# TEST: ONE MEMBER RESPONSE PER VOTE EVENT
#
# Grain should be:
#
# year + vote_id + member_id
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_unique_member_vote_event(year):

    df = load_vote_fact(
        year
    )

    duplicates = df[
        df.duplicated(
            subset=[
                "year",
                "vote_id",
                "member_id",
            ],
            keep=False
        )
    ]

    assert len(duplicates) == 0, (
        f"{year}: found "
        f"{len(duplicates)} duplicate rows "
        f"at year + vote_id + member_id grain"
    )


# =========================================================
# TEST: EACH MEMBER ID MAPS TO ONE NAME PER YEAR
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_member_id_maps_to_one_name(year):

    df = load_vote_fact(
        year
    )

    counts = (
        df
        .groupby(
            "member_id"
        )["MBR_NAME"]
        .nunique()
    )

    invalid = counts[
        counts > 1
    ]

    assert len(invalid) == 0, (
        f"{year}: member IDs mapping "
        f"to multiple names: "
        f"{invalid.to_dict()}"
    )


# =========================================================
# TEST: EACH MEMBER ID MAPS TO ONE PARTY PER YEAR
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_member_id_maps_to_one_party(year):

    df = load_vote_fact(
        year
    )

    counts = (
        df
        .groupby(
            "member_id"
        )["party"]
        .nunique()
    )

    invalid = counts[
        counts > 1
    ]

    assert len(invalid) == 0, (
        f"{year}: member IDs mapping "
        f"to multiple parties: "
        f"{invalid.to_dict()}"
    )


# =========================================================
# TEST: EACH MEMBER ID MAPS TO ONE CHAMBER PER YEAR
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_member_id_maps_to_one_chamber(year):

    df = load_vote_fact(
        year
    )

    counts = (
        df
        .groupby(
            "member_id"
        )["MBR_HOU"]
        .nunique()
    )

    invalid = counts[
        counts > 1
    ]

    assert len(invalid) == 0, (
        f"{year}: member IDs mapping "
        f"to multiple chambers: "
        f"{invalid.to_dict()}"
    )


# =========================================================
# TEST: VOTE IDS HAVE AT LEAST ONE MEMBER RESPONSE
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_events_have_member_responses(year):

    df = load_vote_fact(
        year
    )

    counts = (
        df
        .groupby(
            "vote_id"
        )["member_id"]
        .count()
    )

    invalid = counts[
        counts <= 0
    ]

    assert len(invalid) == 0, (
        f"{year}: vote events with no "
        f"member responses found"
    )


# =========================================================
# TEST: NO ENTIRELY BLANK VOTE VALUES
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_no_blank_vote(year):

    df = load_vote_fact(
        year
    )

    missing = (
        df["vote"]
        .fillna("")
        .str.strip()
        .eq("")
        .sum()
    )

    assert missing == 0, (
        f"{year}: {missing} rows "
        f"have blank vote values"
    )


# =========================================================
# TEST: EXPECTED BASIC SCALE
#
# This is intentionally broad.
#
# It catches catastrophic parsing errors without freezing
# the exact row count into the test.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_reasonable_scale(year):

    df = load_vote_fact(
        year
    )

    assert len(df) > 100_000, (
        f"{year}: unexpectedly small "
        f"vote_fact: {len(df):,} rows"
    )

    assert (
        df["vote_id"]
        .nunique()
        >
        1_000
    ), (
        f"{year}: unexpectedly few "
        f"vote events"
    )

    assert (
        df["member_id"]
        .nunique()
        >
        100
    ), (
        f"{year}: unexpectedly few "
        f"voting members"
    )