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


# =========================================================
# HELPERS
# =========================================================

def load_processed_file(filename):

    path = PROCESSED_ROOT / filename

    if not path.exists():
        pytest.fail(
            f"Missing required processed file: {path}"
        )

    return pd.read_csv(
        path,
        dtype=str
    )


def load_vote_fact(year):

    return load_processed_file(
        f"vote_fact_{year}.csv"
    )


def load_vote_bill_bridge(year):

    return load_processed_file(
        f"vote_bill_bridge_{year}.csv"
    )


def load_bill_lookup(year):

    return load_processed_file(
        f"bill_lookup_{year}.csv"
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
# REQUIRED BRIDGE COLUMNS EXIST
#
# Year is NOT stored as a bridge column.
# Year context is carried by the year-specific filename.
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_bridge_required_columns(year):

    bridge = load_vote_bill_bridge(year)

    required_columns = {
        "vote_id",
        "Bill_id"
    }

    missing = (
        required_columns
        - set(bridge.columns)
    )

    assert not missing, (
        f"{year}: vote_bill_bridge is missing "
        f"required columns: {missing}"
    )


# =========================================================
# TEST 2
# BRIDGE IS NOT EMPTY
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_bridge_not_empty(year):

    bridge = load_vote_bill_bridge(year)

    assert len(bridge) > 0, (
        f"{year}: vote_bill_bridge is empty"
    )


# =========================================================
# TEST 3
# NO BLANK VOTE IDS
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_bridge_no_blank_vote_id(year):

    bridge = load_vote_bill_bridge(year)

    blank_count = (
        normalize_text(
            bridge["vote_id"]
        )
        .eq("")
        .sum()
    )

    assert blank_count == 0, (
        f"{year}: {blank_count} bridge rows "
        f"have blank vote_id"
    )


# =========================================================
# TEST 4
# NO BLANK BILL IDS
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_bridge_no_blank_bill_id(year):

    bridge = load_vote_bill_bridge(year)

    blank_count = (
        normalize_text(
            bridge["Bill_id"]
        )
        .eq("")
        .sum()
    )

    assert blank_count == 0, (
        f"{year}: {blank_count} bridge rows "
        f"have blank Bill_id"
    )


# =========================================================
# TEST 5
# VOTE + BILL RELATIONSHIPS ARE UNIQUE
#
# A vote may connect to MANY bills,
# but the same vote/bill relationship should not
# appear repeatedly.
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_vote_bill_relationships_unique(year):

    bridge = load_vote_bill_bridge(year)

    duplicates = bridge[
        bridge.duplicated(
            subset=[
                "vote_id",
                "Bill_id",
                "History_date",
                "History_description",
            ],
            keep=False
        )
    ]

    assert len(duplicates) == 0, (
        f"{year}: found {len(duplicates)} "
        f"duplicate vote-to-bill bridge rows"
    )


# =========================================================
# TEST 6
# BRIDGE VOTE IDS MUST COME FROM VOTE FACT
#
# We should not have invented vote IDs during
# the history/bill join.
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_bridge_vote_ids_exist_in_vote_fact(year):

    vote_fact = load_vote_fact(year)
    bridge = load_vote_bill_bridge(year)

    vote_fact_ids = set(
        normalize_text(
            vote_fact["vote_id"]
        )
        .unique()
    )

    bridge_ids = set(
        normalize_text(
            bridge["vote_id"]
        )
        .unique()
    )

    unknown = (
        bridge_ids
        - vote_fact_ids
    )

    assert not unknown, (
        f"{year}: bridge contains vote IDs "
        f"not present in vote_fact: "
        f"{sorted(unknown)[:20]}"
    )


# =========================================================
# TEST 7
# BRIDGE BILL IDS MUST EXIST IN BILL LOOKUP
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_bridge_bill_ids_exist_in_bill_lookup(year):

    bridge = load_vote_bill_bridge(year)
    bills = load_bill_lookup(year)

    bridge_bill_ids = set(
        normalize_text(
            bridge["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    lookup_bill_ids = set(
        normalize_text(
            bills["Bill_id"]
        )
        .str.upper()
        .unique()
    )

    unknown = (
        bridge_bill_ids
        - lookup_bill_ids
    )

    assert not unknown, (
        f"{year}: bridge contains Bill_id values "
        f"not found in bill_lookup: "
        f"{sorted(unknown)[:20]}"
    )


# =========================================================
# TEST 8
# BILL LOOKUP SHOULD HAVE ONE ROW PER BILL
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_bill_lookup_bill_ids_unique(year):

    bills = load_bill_lookup(year)

    duplicates = bills[
        bills.duplicated(
            subset=[
                "Bill_id",
            ],
            keep=False
        )
    ]

    assert len(duplicates) == 0, (
        f"{year}: bill_lookup contains "
        f"{len(duplicates)} duplicate Bill_id rows"
    )


# =========================================================
# TEST 9
# BLOCK VOTES REALLY EXIST
#
# Documents that the relationship is legitimately:
#
# one vote -> many bills
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_some_votes_map_to_multiple_bills(year):

    bridge = load_vote_bill_bridge(year)

    bill_counts = (
        bridge
        .groupby(
            "vote_id"
        )["Bill_id"]
        .nunique()
    )

    multi_bill_votes = (
        bill_counts > 1
    ).sum()

    assert multi_bill_votes > 0, (
        f"{year}: no vote events map to "
        f"multiple bills. This is unexpected "
        f"based on known LIS block-vote behavior."
    )


# =========================================================
# TEST 10
# SOME VOTES MAY HAVE NO BILL RELATIONSHIP
#
# Procedural or otherwise unmatched vote events
# should remain in vote_fact.
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_unmatched_vote_events_are_preserved(year):

    vote_fact = load_vote_fact(year)
    bridge = load_vote_bill_bridge(year)

    vote_ids = set(
        normalize_text(
            vote_fact["vote_id"]
        )
        .unique()
    )

    mapped_ids = set(
        normalize_text(
            bridge["vote_id"]
        )
        .unique()
    )

    unmatched = (
        vote_ids
        - mapped_ids
    )

    assert len(vote_ids) >= len(mapped_ids)

    assert len(unmatched) > 0, (
        f"{year}: every vote event unexpectedly "
        f"maps to a bill. Investigate whether "
        f"procedural/unmatched votes were dropped."
    )


# =========================================================
# TEST 11
# VOTE FACT GRAIN REMAINS UNIQUE
#
# Bill relationships must never alter the authoritative
# member-vote table.
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_vote_fact_grain_remains_unique(year):

    vote_fact = load_vote_fact(year)

    duplicates = vote_fact[
        vote_fact.duplicated(
            subset=[
                "year",
                "vote_id",
                "member_id",
            ],
            keep=False
        )
    ]

    assert len(duplicates) == 0, (
        f"{year}: vote_fact contains duplicate "
        f"member-vote events"
    )


# =========================================================
# TEST 12
# JOINING BRIDGE CAN EXPAND ROW COUNT
#
# This is NOT an error.
#
# Bridge joins use vote_id only because each bridge file
# is already year-specific.
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_bridge_join_can_expand_vote_rows(year):

    vote_fact = load_vote_fact(year)
    bridge = load_vote_bill_bridge(year)

    mapped_vote_fact = (
        vote_fact[
            vote_fact[
                "vote_id"
            ]
            .isin(
                bridge[
                    "vote_id"
                ]
            )
        ][
            [
                "year",
                "vote_id",
                "member_id",
            ]
        ]
    )

    joined = (
        mapped_vote_fact
        .merge(
            bridge[
                [
                    "vote_id",
                    "Bill_id",
                ]
            ],
            on=
                "vote_id",
            how=
                "inner"
        )
    )

    assert len(joined) >= len(
        mapped_vote_fact
    ), (
        f"{year}: bridge join behaved "
        f"unexpectedly"
    )


# =========================================================
# TEST 13
# EXPANDED BILL ROWS MUST NOT CREATE NEW MEMBER VOTES
#
# This is the core block-vote protection test.
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_bridge_expansion_does_not_create_new_vote_events(year):

    vote_fact = load_vote_fact(year)
    bridge = load_vote_bill_bridge(year)

    joined = (
        vote_fact[
            [
                "year",
                "vote_id",
                "member_id",
            ]
        ]
        .merge(
            bridge[
                [
                    "vote_id",
                    "Bill_id",
                ]
            ],
            on=
                "vote_id",
            how=
                "inner"
        )
    )

    original_member_votes = set(
        zip(
            normalize_text(
                vote_fact[
                    "year"
                ]
            ),
            normalize_text(
                vote_fact[
                    "vote_id"
                ]
            ),
            normalize_text(
                vote_fact[
                    "member_id"
                ]
            ),
        )
    )

    joined_member_votes = set(
        zip(
            normalize_text(
                joined[
                    "year"
                ]
            ),
            normalize_text(
                joined[
                    "vote_id"
                ]
            ),
            normalize_text(
                joined[
                    "member_id"
                ]
            ),
        )
    )

    unexpected = (
        joined_member_votes
        - original_member_votes
    )

    assert not unexpected, (
        f"{year}: joining the bridge created "
        f"member-vote identities that did not "
        f"exist in vote_fact"
    )


# =========================================================
# TEST 14
# MULTI-BILL VOTES REPEAT MEMBER-VOTE IDENTITIES
#
# This demonstrates why the exploded bill table cannot
# replace vote_fact as the master vote table.
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_multibill_join_repeats_member_vote_identity(year):

    vote_fact = load_vote_fact(year)
    bridge = load_vote_bill_bridge(year)

    bill_counts = (
        bridge
        .groupby(
            "vote_id"
        )["Bill_id"]
        .nunique()
    )

    multi_bill_vote_ids = set(
        bill_counts[
            bill_counts > 1
        ].index
    )

    assert multi_bill_vote_ids, (
        f"{year}: no multi-bill vote IDs found"
    )

    sample_vote_id = next(
        iter(
            multi_bill_vote_ids
        )
    )

    vote_rows = (
        vote_fact[
            vote_fact[
                "vote_id"
            ]
            ==
            sample_vote_id
        ][
            [
                "year",
                "vote_id",
                "member_id",
            ]
        ]
    )

    bridge_rows = (
        bridge[
            bridge[
                "vote_id"
            ]
            ==
            sample_vote_id
        ][
            [
                "vote_id",
                "Bill_id",
            ]
        ]
    )

    joined = (
        vote_rows
        .merge(
            bridge_rows,
            on=
                "vote_id",
            how=
                "inner"
        )
    )

    bill_count = (
        bridge_rows[
            "Bill_id"
        ]
        .nunique()
    )

    member_count = (
        vote_rows[
            "member_id"
        ]
        .nunique()
    )

    expected_rows = (
        member_count
        *
        bill_count
    )

    assert len(joined) == expected_rows, (
        f"{year}: unexpected row count for "
        f"multi-bill vote {sample_vote_id}. "
        f"Expected {expected_rows}, "
        f"found {len(joined)}."
    )


# =========================================================
# TEST 15
# EXPLODED BILL REPRESENTATION SHOULD HAVE MORE ROWS
#
# This guards against someone later replacing vote_fact
# with the bill-expanded representation.
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_exploded_bill_representation_has_more_rows(year):

    vote_fact = load_vote_fact(year)
    bridge = load_vote_bill_bridge(year)

    mapped_vote_fact = (
        vote_fact[
            vote_fact[
                "vote_id"
            ]
            .isin(
                bridge[
                    "vote_id"
                ]
            )
        ][
            [
                "year",
                "vote_id",
                "member_id",
            ]
        ]
    )

    exploded = (
        mapped_vote_fact
        .merge(
            bridge[
                [
                    "vote_id",
                    "Bill_id",
                ]
            ],
            on=
                "vote_id",
            how=
                "inner"
        )
    )

    assert len(exploded) > len(
        mapped_vote_fact
    ), (
        f"{year}: bill-level representation "
        f"did not expand despite known "
        f"multi-bill vote relationships"
    )


# =========================================================
# TEST 16
# EVERY BRIDGE VOTE HAS AT LEAST ONE MEMBER RESPONSE
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_every_bridge_vote_has_member_responses(year):

    vote_fact = load_vote_fact(year)
    bridge = load_vote_bill_bridge(year)

    member_counts = (
        vote_fact
        .groupby(
            "vote_id"
        )["member_id"]
        .nunique()
    )

    bridge_vote_ids = set(
        normalize_text(
            bridge[
                "vote_id"
            ]
        )
        .unique()
    )

    invalid = [
        vote_id
        for vote_id in bridge_vote_ids
        if (
            vote_id not in member_counts.index
            or member_counts.loc[
                vote_id
            ]
            <=
            0
        )
    ]

    assert not invalid, (
        f"{year}: bridge vote IDs with no "
        f"member responses: "
        f"{invalid[:20]}"
    )


# =========================================================
# TEST 17
# BILL LOOKUP HAS NO BLANK BILL IDS
# =========================================================

@pytest.mark.parametrize("year", YEARS)
def test_bill_lookup_no_blank_bill_id(year):

    bills = load_bill_lookup(year)

    blank_count = (
        normalize_text(
            bills[
                "Bill_id"
            ]
        )
        .eq("")
        .sum()
    )

    assert blank_count == 0, (
        f"{year}: {blank_count} bill_lookup rows "
        f"have blank Bill_id"
    )