import pandas as pd
import pytest

from Version_1.lis_pipeline import (
    calculate_party_positions,
    add_own_party_position,
    flag_party_breaks,
    add_other_party_position,
    flag_cross_party_votes,
)


# =========================================================
# HELPERS
# =========================================================

def build_vote_fact(rows):

    return pd.DataFrame(
        rows,
        columns=[
            "year",
            "MBR_HOU",
            "vote_id",
            "member_id",
            "MBR_NAME",
            "party",
            "vote",
        ]
    )


def run_cross_party_logic(vote_fact):

    party_positions = (
        calculate_party_positions(
            vote_fact
        )
    )

    result = (
        add_own_party_position(
            vote_fact,
            party_positions
        )
    )

    result = (
        flag_party_breaks(
            result
        )
    )

    result = (
        add_other_party_position(
            result,
            party_positions
        )
    )

    result = (
        flag_cross_party_votes(
            result
        )
    )

    return result


def get_member_row(
    result,
    member_id
):

    row = result[
        result[
            "member_id"
        ]
        ==
        member_id
    ]

    assert len(row) == 1

    return row.iloc[0]


# =========================================================
# TEST 1
#
# REPUBLICAN BREAKS WITH R MAJORITY
# AND MATCHES D MAJORITY
#
# D:
#   3 Y
#   1 N
#
# R:
#   1 Y
#   3 N
#
# R4 votes Y.
#
# Expected:
# own party position = N
# other party position = Y
# broke_with_party = True
# cross_party = True
# =========================================================

def test_republican_cross_party_yes():

    vote_fact = build_vote_fact(
        [
            [
                2026,
                "H",
                "V1",
                "D1",
                "Democrat 1",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V1",
                "D2",
                "Democrat 2",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V1",
                "D3",
                "Democrat 3",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V1",
                "D4",
                "Democrat 4",
                "D",
                "N",
            ],
            [
                2026,
                "H",
                "V1",
                "R1",
                "Republican 1",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V1",
                "R2",
                "Republican 2",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V1",
                "R3",
                "Republican 3",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V1",
                "R4",
                "Republican 4",
                "R",
                "Y",
            ],
        ]
    )

    result = run_cross_party_logic(
        vote_fact
    )

    row = get_member_row(
        result,
        "R4"
    )

    assert (
        row[
            "own_party_position"
        ]
        ==
        "N"
    )

    assert (
        row[
            "other_party_position"
        ]
        ==
        "Y"
    )

    assert bool(
        row[
            "broke_with_party"
        ]
    )

    assert bool(
        row[
            "cross_party"
        ]
    )


# =========================================================
# TEST 2
#
# DEMOCRAT BREAKS WITH D MAJORITY
# AND MATCHES R MAJORITY
# =========================================================

def test_democrat_cross_party_no():

    vote_fact = build_vote_fact(
        [
            [
                2026,
                "H",
                "V2",
                "D1",
                "Democrat 1",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V2",
                "D2",
                "Democrat 2",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V2",
                "D3",
                "Democrat 3",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V2",
                "D4",
                "Democrat 4",
                "D",
                "N",
            ],
            [
                2026,
                "H",
                "V2",
                "R1",
                "Republican 1",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V2",
                "R2",
                "Republican 2",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V2",
                "R3",
                "Republican 3",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V2",
                "R4",
                "Republican 4",
                "R",
                "Y",
            ],
        ]
    )

    result = run_cross_party_logic(
        vote_fact
    )

    row = get_member_row(
        result,
        "D4"
    )

    assert (
        row[
            "own_party_position"
        ]
        ==
        "Y"
    )

    assert (
        row[
            "other_party_position"
        ]
        ==
        "N"
    )

    assert bool(
        row[
            "broke_with_party"
        ]
    )

    assert bool(
        row[
            "cross_party"
        ]
    )


# =========================================================
# TEST 3
#
# MEMBER AGREES WITH OWN PARTY
#
# Expected:
# broke_with_party = False
# cross_party = False
# =========================================================

def test_member_agrees_with_own_party():

    vote_fact = build_vote_fact(
        [
            [
                2026,
                "H",
                "V3",
                "D1",
                "Democrat 1",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V3",
                "D2",
                "Democrat 2",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V3",
                "D3",
                "Democrat 3",
                "D",
                "N",
            ],
            [
                2026,
                "H",
                "V3",
                "R1",
                "Republican 1",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V3",
                "R2",
                "Republican 2",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V3",
                "R3",
                "Republican 3",
                "R",
                "Y",
            ],
        ]
    )

    result = run_cross_party_logic(
        vote_fact
    )

    row = get_member_row(
        result,
        "D1"
    )

    assert (
        row[
            "own_party_position"
        ]
        ==
        "Y"
    )

    assert not bool(
        row[
            "broke_with_party"
        ]
    )

    assert not bool(
        row[
            "cross_party"
        ]
    )


# =========================================================
# TEST 4
#
# MEMBER BREAKS WITH OWN PARTY
# BUT DOES NOT MATCH OTHER PARTY
#
# This can happen when the other party is tied.
#
# Expected:
# broke_with_party = True
# cross_party = False
# =========================================================

def test_party_break_without_cross_party():

    vote_fact = build_vote_fact(
        [
            [
                2026,
                "H",
                "V4",
                "D1",
                "Democrat 1",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V4",
                "D2",
                "Democrat 2",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V4",
                "D3",
                "Democrat 3",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V4",
                "D4",
                "Democrat 4",
                "D",
                "N",
            ],
            [
                2026,
                "H",
                "V4",
                "R1",
                "Republican 1",
                "R",
                "Y",
            ],
            [
                2026,
                "H",
                "V4",
                "R2",
                "Republican 2",
                "R",
                "N",
            ],
        ]
    )

    result = run_cross_party_logic(
        vote_fact
    )

    row = get_member_row(
        result,
        "D4"
    )

    assert (
        row[
            "own_party_position"
        ]
        ==
        "Y"
    )

    assert (
        row[
            "other_party_position"
        ]
        ==
        "TIE"
    )

    assert bool(
        row[
            "broke_with_party"
        ]
    )

    assert not bool(
        row[
            "cross_party"
        ]
    )


# =========================================================
# TEST 5
#
# OWN PARTY IS TIED
#
# There is no directional own-party majority.
#
# Therefore:
# broke_with_party = False
# cross_party = False
# =========================================================

def test_own_party_tie_not_party_break():

    vote_fact = build_vote_fact(
        [
            [
                2026,
                "H",
                "V5",
                "D1",
                "Democrat 1",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V5",
                "D2",
                "Democrat 2",
                "D",
                "N",
            ],
            [
                2026,
                "H",
                "V5",
                "R1",
                "Republican 1",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V5",
                "R2",
                "Republican 2",
                "R",
                "N",
            ],
        ]
    )

    result = run_cross_party_logic(
        vote_fact
    )

    row = get_member_row(
        result,
        "D1"
    )

    assert (
        row[
            "own_party_position"
        ]
        ==
        "TIE"
    )

    assert not bool(
        row[
            "broke_with_party"
        ]
    )

    assert not bool(
        row[
            "cross_party"
        ]
    )


# =========================================================
# TEST 6
#
# OTHER PARTY IS TIED
#
# Member may break with own party,
# but cannot be called cross-party.
# =========================================================

def test_other_party_tie_not_cross_party():

    vote_fact = build_vote_fact(
        [
            [
                2026,
                "H",
                "V6",
                "D1",
                "Democrat 1",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V6",
                "D2",
                "Democrat 2",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V6",
                "D3",
                "Democrat 3",
                "D",
                "N",
            ],
            [
                2026,
                "H",
                "V6",
                "R1",
                "Republican 1",
                "R",
                "Y",
            ],
            [
                2026,
                "H",
                "V6",
                "R2",
                "Republican 2",
                "R",
                "N",
            ],
        ]
    )

    result = run_cross_party_logic(
        vote_fact
    )

    row = get_member_row(
        result,
        "D3"
    )

    assert bool(
        row[
            "broke_with_party"
        ]
    )

    assert (
        row[
            "other_party_position"
        ]
        ==
        "TIE"
    )

    assert not bool(
        row[
            "cross_party"
        ]
    )


# =========================================================
# TEST 7
#
# X IS NOT DIRECTIONAL
#
# It should never count as:
# party break
# cross-party
# =========================================================

def test_x_vote_not_directional():

    vote_fact = build_vote_fact(
        [
            [
                2026,
                "H",
                "V7",
                "D1",
                "Democrat 1",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V7",
                "D2",
                "Democrat 2",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V7",
                "D3",
                "Democrat 3",
                "D",
                "X",
            ],
            [
                2026,
                "H",
                "V7",
                "R1",
                "Republican 1",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V7",
                "R2",
                "Republican 2",
                "R",
                "N",
            ],
        ]
    )

    result = run_cross_party_logic(
        vote_fact
    )

    row = get_member_row(
        result,
        "D3"
    )

    assert not bool(
        row[
            "broke_with_party"
        ]
    )

    assert not bool(
        row[
            "cross_party"
        ]
    )


# =========================================================
# TEST 8
#
# A IS NOT DIRECTIONAL
# =========================================================

def test_a_vote_not_directional():

    vote_fact = build_vote_fact(
        [
            [
                2026,
                "H",
                "V8",
                "D1",
                "Democrat 1",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V8",
                "D2",
                "Democrat 2",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V8",
                "D3",
                "Democrat 3",
                "D",
                "A",
            ],
            [
                2026,
                "H",
                "V8",
                "R1",
                "Republican 1",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V8",
                "R2",
                "Republican 2",
                "R",
                "N",
            ],
        ]
    )

    result = run_cross_party_logic(
        vote_fact
    )

    row = get_member_row(
        result,
        "D3"
    )

    assert not bool(
        row[
            "broke_with_party"
        ]
    )

    assert not bool(
        row[
            "cross_party"
        ]
    )


# =========================================================
# TEST 9
#
# P IS NOT DIRECTIONAL
#
# P is observed in 2025 source data,
# but we do not infer a meaning.
# =========================================================

def test_p_vote_not_directional():

    vote_fact = build_vote_fact(
        [
            [
                2025,
                "H",
                "V9",
                "D1",
                "Democrat 1",
                "D",
                "Y",
            ],
            [
                2025,
                "H",
                "V9",
                "D2",
                "Democrat 2",
                "D",
                "Y",
            ],
            [
                2025,
                "H",
                "V9",
                "D3",
                "Democrat 3",
                "D",
                "P",
            ],
            [
                2025,
                "H",
                "V9",
                "R1",
                "Republican 1",
                "R",
                "N",
            ],
            [
                2025,
                "H",
                "V9",
                "R2",
                "Republican 2",
                "R",
                "N",
            ],
        ]
    )

    result = run_cross_party_logic(
        vote_fact
    )

    row = get_member_row(
        result,
        "D3"
    )

    assert not bool(
        row[
            "broke_with_party"
        ]
    )

    assert not bool(
        row[
            "cross_party"
        ]
    )


# =========================================================
# TEST 10
#
# PARTY MAJORITY COUNTS ONLY Y/N
#
# X/A/P must not affect the directional majority.
# =========================================================

def test_nondirectional_votes_do_not_affect_party_majority():

    vote_fact = build_vote_fact(
        [
            [
                2025,
                "H",
                "V10",
                "D1",
                "Democrat 1",
                "D",
                "Y",
            ],
            [
                2025,
                "H",
                "V10",
                "D2",
                "Democrat 2",
                "D",
                "Y",
            ],
            [
                2025,
                "H",
                "V10",
                "D3",
                "Democrat 3",
                "D",
                "N",
            ],
            [
                2025,
                "H",
                "V10",
                "D4",
                "Democrat 4",
                "D",
                "X",
            ],
            [
                2025,
                "H",
                "V10",
                "D5",
                "Democrat 5",
                "D",
                "A",
            ],
            [
                2025,
                "H",
                "V10",
                "D6",
                "Democrat 6",
                "D",
                "P",
            ],
            [
                2025,
                "H",
                "V10",
                "R1",
                "Republican 1",
                "R",
                "N",
            ],
            [
                2025,
                "H",
                "V10",
                "R2",
                "Republican 2",
                "R",
                "N",
            ],
        ]
    )

    result = run_cross_party_logic(
        vote_fact
    )

    row = get_member_row(
        result,
        "D1"
    )

    assert (
        row[
            "own_party_position"
        ]
        ==
        "Y"
    )


# =========================================================
# TEST 11
#
# CROSS-PARTY MUST IMPLY PARTY BREAK
# =========================================================

def test_cross_party_always_implies_party_break():

    vote_fact = build_vote_fact(
        [
            [
                2026,
                "H",
                "V11",
                "D1",
                "Democrat 1",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V11",
                "D2",
                "Democrat 2",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V11",
                "D3",
                "Democrat 3",
                "D",
                "N",
            ],
            [
                2026,
                "H",
                "V11",
                "R1",
                "Republican 1",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V11",
                "R2",
                "Republican 2",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V11",
                "R3",
                "Republican 3",
                "R",
                "Y",
            ],
        ]
    )

    result = run_cross_party_logic(
        vote_fact
    )

    cross_party_rows = result[
        result[
            "cross_party"
        ]
    ]

    assert (
        cross_party_rows[
            "broke_with_party"
        ]
        .all()
    )


# =========================================================
# TEST 12
#
# HOUSE AND SENATE MUST BE CALCULATED SEPARATELY
#
# Same vote_id can hypothetically appear in both chambers.
#
# Party majorities should not bleed across chambers.
# =========================================================

def test_party_positions_are_chamber_specific():

    vote_fact = build_vote_fact(
        [
            # House Democrats -> Y majority
            [
                2026,
                "H",
                "V12",
                "HD1",
                "House Democrat 1",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V12",
                "HD2",
                "House Democrat 2",
                "D",
                "Y",
            ],
            [
                2026,
                "H",
                "V12",
                "HD3",
                "House Democrat 3",
                "D",
                "N",
            ],

            # Senate Democrats -> N majority
            [
                2026,
                "S",
                "V12",
                "SD1",
                "Senate Democrat 1",
                "D",
                "N",
            ],
            [
                2026,
                "S",
                "V12",
                "SD2",
                "Senate Democrat 2",
                "D",
                "N",
            ],
            [
                2026,
                "S",
                "V12",
                "SD3",
                "Senate Democrat 3",
                "D",
                "Y",
            ],

            # House Republicans
            [
                2026,
                "H",
                "V12",
                "HR1",
                "House Republican 1",
                "R",
                "N",
            ],
            [
                2026,
                "H",
                "V12",
                "HR2",
                "House Republican 2",
                "R",
                "N",
            ],

            # Senate Republicans
            [
                2026,
                "S",
                "V12",
                "SR1",
                "Senate Republican 1",
                "R",
                "Y",
            ],
            [
                2026,
                "S",
                "V12",
                "SR2",
                "Senate Republican 2",
                "R",
                "Y",
            ],
        ]
    )

    result = run_cross_party_logic(
        vote_fact
    )

    house_row = get_member_row(
        result,
        "HD1"
    )

    senate_row = get_member_row(
        result,
        "SD1"
    )

    assert (
        house_row[
            "own_party_position"
        ]
        ==
        "Y"
    )

    assert (
        senate_row[
            "own_party_position"
        ]
        ==
        "N"
    )