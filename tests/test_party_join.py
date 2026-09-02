from pathlib import Path

import pandas as pd
import pytest


# =========================================================
# CONFIG
# =========================================================

PROCESSED_ROOT = Path("data/processed")
REFERENCE_ROOT = Path("data/reference")

YEARS = [
    2025,
    2026,
]

VALID_PARTIES = {
    "D",
    "R",
    "I",
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

    return pd.read_csv(
        path,
        dtype=str
    )


def load_party_reference(year):

    path = (
        REFERENCE_ROOT
        / f"party_{year}.csv"
    )

    if not path.exists():

        pytest.fail(
            f"Missing required file: {path}"
        )

    return pd.read_csv(
        path,
        dtype=str
    )


def normalize_text(series):

    return (
        series
        .fillna("")
        .astype(str)
        .str.strip()
    )


# =========================================================
# TEST: PARTY REFERENCE REQUIRED COLUMNS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_party_reference_required_columns(year):

    df = load_party_reference(
        year
    )

    required_columns = {
        "member_id",
        "party",
        "member",
    }

    missing = (
        required_columns
        - set(df.columns)
    )

    assert not missing, (
        f"{year}: party reference is missing "
        f"required columns: {missing}"
    )


# =========================================================
# TEST: PARTY REFERENCE IS NOT EMPTY
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_party_reference_not_empty(year):

    df = load_party_reference(
        year
    )

    assert len(df) > 0, (
        f"{year}: party reference is empty"
    )


# =========================================================
# TEST: NO BLANK MEMBER IDS IN PARTY REFERENCE
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_party_reference_no_blank_member_id(year):

    df = load_party_reference(
        year
    )

    blank_count = (
        normalize_text(
            df["member_id"]
        )
        .eq("")
        .sum()
    )

    assert blank_count == 0, (
        f"{year}: {blank_count} party reference rows "
        f"have blank member_id"
    )


# =========================================================
# TEST: PARTY REFERENCE MEMBER IDS UNIQUE
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_party_reference_member_ids_unique(year):

    df = load_party_reference(
        year
    ).copy()

    df["member_id"] = (
        normalize_text(
            df["member_id"]
        )
        .str.upper()
    )

    duplicates = df[
        df[
            "member_id"
        ]
        .duplicated(
            keep=False
        )
    ]

    assert len(duplicates) == 0, (
        f"{year}: duplicate member IDs found "
        f"in party reference:\n"
        f"{duplicates.to_string(index=False)}"
    )


# =========================================================
# TEST: PARTY VALUES VALID
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_party_reference_valid_party_values(year):

    df = load_party_reference(
        year
    )

    actual = set(
        normalize_text(
            df["party"]
        )
        .str.upper()
        .unique()
    )

    invalid = (
        actual
        - VALID_PARTIES
    )

    assert not invalid, (
        f"{year}: invalid party values in "
        f"party reference: {invalid}"
    )


# =========================================================
# TEST: NO BLANK PARTY VALUES
#
# At this stage the reference files should be complete.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_party_reference_no_blank_party(year):

    df = load_party_reference(
        year
    )

    blank_count = (
        normalize_text(
            df["party"]
        )
        .eq("")
        .sum()
    )

    assert blank_count == 0, (
        f"{year}: {blank_count} party reference rows "
        f"still have blank party values"
    )


# =========================================================
# TEST: NO BLANK MEMBER NAMES IN PARTY REFERENCE
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_party_reference_no_blank_member_name(year):

    df = load_party_reference(
        year
    )

    blank_count = (
        normalize_text(
            df["member"]
        )
        .eq("")
        .sum()
    )

    assert blank_count == 0, (
        f"{year}: {blank_count} party reference rows "
        f"have blank member names"
    )


# =========================================================
# TEST: EVERY VOTING MEMBER EXISTS IN PARTY REFERENCE
#
# This is critical.
# A voting member cannot be missing from the party lookup.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_every_voting_member_exists_in_party_reference(year):

    vote_fact = load_vote_fact(
        year
    )

    party_ref = load_party_reference(
        year
    )

    voting_ids = set(
        normalize_text(
            vote_fact[
                "member_id"
            ]
        )
        .str.upper()
        .unique()
    )

    reference_ids = set(
        normalize_text(
            party_ref[
                "member_id"
            ]
        )
        .str.upper()
        .unique()
    )

    missing = (
        voting_ids
        - reference_ids
    )

    assert not missing, (
        f"{year}: voting member IDs missing "
        f"from party reference: "
        f"{sorted(missing)}"
    )


# =========================================================
# TEST: VOTE FACT HAS NO MISSING PARTY
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_party_join_complete(year):

    df = load_vote_fact(
        year
    )

    blank_count = (
        normalize_text(
            df["party"]
        )
        .eq("")
        .sum()
    )

    assert blank_count == 0, (
        f"{year}: {blank_count} vote rows "
        f"have missing party after join"
    )


# =========================================================
# TEST: VOTE FACT PARTY VALUES VALID
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_party_values_valid(year):

    df = load_vote_fact(
        year
    )

    actual = set(
        normalize_text(
            df["party"]
        )
        .str.upper()
        .unique()
    )

    invalid = (
        actual
        - VALID_PARTIES
    )

    assert not invalid, (
        f"{year}: invalid party values found "
        f"in vote_fact: {invalid}"
    )


# =========================================================
# TEST: PARTY JOIN AGREES WITH REFERENCE FILE
#
# This is one of the most important tests in this file.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_fact_party_matches_reference(year):

    vote_fact = load_vote_fact(
        year
    ).copy()

    party_ref = load_party_reference(
        year
    ).copy()

    vote_fact["member_id"] = (
        normalize_text(
            vote_fact[
                "member_id"
            ]
        )
        .str.upper()
    )

    vote_fact["party"] = (
        normalize_text(
            vote_fact[
                "party"
            ]
        )
        .str.upper()
    )

    party_ref["member_id"] = (
        normalize_text(
            party_ref[
                "member_id"
            ]
        )
        .str.upper()
    )

    party_ref[
        "reference_party"
    ] = (
        normalize_text(
            party_ref[
                "party"
            ]
        )
        .str.upper()
    )

    check = (
        vote_fact[
            [
                "member_id",
                "party",
            ]
        ]
        .drop_duplicates()
        .merge(
            party_ref[
                [
                    "member_id",
                    "reference_party",
                ]
            ],
            on="member_id",
            how="left",
            validate="one_to_one"
        )
    )

    mismatch = check[
        check[
            "party"
        ]
        !=
        check[
            "reference_party"
        ]
    ]

    assert len(mismatch) == 0, (
        f"{year}: party mismatch between "
        f"vote_fact and party reference:\n"
        f"{mismatch.to_string(index=False)}"
    )


# =========================================================
# TEST: EACH MEMBER MAPS TO ONE PARTY IN VOTE FACT
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_each_member_maps_to_one_party(year):

    df = load_vote_fact(
        year
    ).copy()

    df["member_id"] = (
        normalize_text(
            df["member_id"]
        )
        .str.upper()
    )

    df["party"] = (
        normalize_text(
            df["party"]
        )
        .str.upper()
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
        f"{year}: members mapped to "
        f"multiple parties: "
        f"{invalid.to_dict()}"
    )


# =========================================================
# TEST: PARTY REFERENCE NAME MATCHES FINAL MEMBER NAME
#
# This should now pass because the 2025 H0381 recovery
# used the party reference name.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_party_reference_name_matches_vote_fact_name(year):

    vote_fact = load_vote_fact(
        year
    ).copy()

    party_ref = load_party_reference(
        year
    ).copy()

    vote_members = (
        vote_fact[
            [
                "member_id",
                "MBR_NAME",
            ]
        ]
        .drop_duplicates()
        .copy()
    )

    vote_members["member_id"] = (
        normalize_text(
            vote_members[
                "member_id"
            ]
        )
        .str.upper()
    )

    vote_members[
        "vote_name_normalized"
    ] = (
        normalize_text(
            vote_members[
                "MBR_NAME"
            ]
        )
        .str.casefold()
    )

    party_ref["member_id"] = (
        normalize_text(
            party_ref[
                "member_id"
            ]
        )
        .str.upper()
    )

    party_ref[
        "reference_name_normalized"
    ] = (
        normalize_text(
            party_ref[
                "member"
            ]
        )
        .str.casefold()
    )

    check = vote_members.merge(
        party_ref[
            [
                "member_id",
                "reference_name_normalized",
            ]
        ],
        on="member_id",
        how="left",
        validate="one_to_one"
    )

    mismatch = check[
        check[
            "vote_name_normalized"
        ]
        !=
        check[
            "reference_name_normalized"
        ]
    ]

    assert len(mismatch) == 0, (
        f"{year}: member-name mismatch between "
        f"vote_fact and party reference:\n"
        f"{mismatch.to_string(index=False)}"
    )


# =========================================================
# TEST: MEMBER IDS HAVE EXPECTED PREFIX
#
# Party references should only contain House/Senate IDs.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_party_reference_member_id_prefix_valid(year):

    df = load_party_reference(
        year
    ).copy()

    prefixes = set(
        normalize_text(
            df[
                "member_id"
            ]
        )
        .str.upper()
        .str[:1]
        .unique()
    )

    invalid = (
        prefixes
        - {
            "H",
            "S",
        }
    )

    assert not invalid, (
        f"{year}: invalid member ID prefixes "
        f"in party reference: {invalid}"
    )


# =========================================================
# TEST: ALL HOUSE VOTERS HAVE H IDs
# AND ALL SENATE VOTERS HAVE S IDs
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_party_join_preserves_chamber_identity(year):

    df = load_vote_fact(
        year
    ).copy()

    df["member_id"] = (
        normalize_text(
            df[
                "member_id"
            ]
        )
        .str.upper()
    )

    df["MBR_HOU"] = (
        normalize_text(
            df[
                "MBR_HOU"
            ]
        )
        .str.upper()
    )

    df[
        "expected_chamber"
    ] = (
        df[
            "member_id"
        ]
        .str[:1]
    )

    mismatch = df[
        df[
            "MBR_HOU"
        ]
        !=
        df[
            "expected_chamber"
        ]
    ]

    assert len(mismatch) == 0, (
        f"{year}: party/member join created "
        f"chamber identity mismatches"
    )


# =========================================================
# TEST: PARTY COUNTS ARE PLAUSIBLE
#
# Intentionally broad.
#
# This is a catastrophic-error detector,
# not a frozen political composition assertion.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_party_counts_reasonable(year):

    df = load_vote_fact(
        year
    )

    members = (
        df[
            [
                "member_id",
                "party",
            ]
        ]
        .drop_duplicates()
    )

    counts = (
        members[
            "party"
        ]
        .value_counts()
    )

    assert counts.sum() > 100, (
        f"{year}: unexpectedly few "
        f"unique voting members"
    )

    assert counts.get(
        "D",
        0
    ) > 20, (
        f"{year}: unexpectedly few "
        f"Democratic voting members"
    )

    assert counts.get(
        "R",
        0
    ) > 20, (
        f"{year}: unexpectedly few "
        f"Republican voting members"
    )


# =========================================================
# TEST: NO PARTY INFORMATION WAS LOST AFTER JOIN
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_all_vote_rows_have_reference_backing(year):

    vote_fact = load_vote_fact(
        year
    ).copy()

    party_ref = load_party_reference(
        year
    ).copy()

    vote_fact["member_id"] = (
        normalize_text(
            vote_fact[
                "member_id"
            ]
        )
        .str.upper()
    )

    party_ref["member_id"] = (
        normalize_text(
            party_ref[
                "member_id"
            ]
        )
        .str.upper()
    )

    reference_ids = set(
        party_ref[
            "member_id"
        ]
        .unique()
    )

    missing_rows = vote_fact[
        ~vote_fact[
            "member_id"
        ]
        .isin(
            reference_ids
        )
    ]

    assert len(missing_rows) == 0, (
        f"{year}: {len(missing_rows)} vote rows "
        f"have no corresponding party reference row"
    )