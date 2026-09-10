import pandas as pd
import pytest

from topic_stance_analysis import (
    build_delegate_topic_voting_tendency,
)


# =========================================================
# TEST CONFIG
# =========================================================

EXPECTED_MINIMUM_VOTES = 10
EXPECTED_YES_THRESHOLD = 0.65
EXPECTED_NO_THRESHOLD = 0.35


# =========================================================
# HELPER
#
# Creates fake member-vote-topic data.
#
# Each row represents:
#
#     one member
#     + one recorded vote event
#     + one analytical topic
#
# topic_provenance is descriptive metadata.
#
# It explains where the topic assignment came from, but it
# does NOT create a separate analytical vote row.
# =========================================================

def make_topic_votes(
    yes_votes,
    no_votes,
    x_votes=0,
    a_votes=0,
    p_votes=0,
    *,
    year=2026,
    member_id="H9999",
    member_name="Test Delegate",
    party="D",
    topic_name="Education",
    topic_provenance="Derived from LIS bill description",
    vote_prefix="TEST",
):

    votes = (
        ["Y"] * yes_votes
        + ["N"] * no_votes
        + ["X"] * x_votes
        + ["A"] * a_votes
        + ["P"] * p_votes
    )

    rows = []

    for i, vote in enumerate(
        votes,
        start=1,
    ):

        rows.append(
            {
                "year": year,
                "vote_id": f"{vote_prefix}{i:04d}",
                "member_id": member_id,
                "MBR_NAME": member_name,
                "party": party,
                "topic_name": topic_name,
                "topic_provenance": topic_provenance,
                "vote": vote,
            }
        )

    return pd.DataFrame(rows)


def run_tendency(df):

    result = (
        build_delegate_topic_voting_tendency(
            df
        )
    )

    assert len(result) == 1, (
        "Expected exactly one "
        "delegate-topic summary row"
    )

    return result.iloc[0]


# =========================================================
# TEST 1
# 8 YES + 2 NO = 80% YES
#
# Expected: YES
# =========================================================

def test_clear_yes_tendency():

    df = make_topic_votes(
        yes_votes=8,
        no_votes=2,
    )

    row = run_tendency(df)

    assert row["yes_votes"] == 8
    assert row["no_votes"] == 2

    assert (
        row["directional_topic_votes"]
        ==
        10
    )

    assert row["yes_pct"] == pytest.approx(
        80.0
    )

    assert (
        row["voting_tendency"]
        ==
        "YES"
    )


# =========================================================
# TEST 2
# 2 YES + 8 NO = 20% YES
#
# Expected: NO
# =========================================================

def test_clear_no_tendency():

    df = make_topic_votes(
        yes_votes=2,
        no_votes=8,
    )

    row = run_tendency(df)

    assert row["yes_pct"] == pytest.approx(
        20.0
    )

    assert (
        row["voting_tendency"]
        ==
        "NO"
    )


# =========================================================
# TEST 3
# 5 YES + 5 NO = 50% YES
#
# Expected: MIXED
# =========================================================

def test_clear_mixed_tendency():

    df = make_topic_votes(
        yes_votes=5,
        no_votes=5,
    )

    row = run_tendency(df)

    assert row["yes_pct"] == pytest.approx(
        50.0
    )

    assert (
        row["voting_tendency"]
        ==
        "MIXED"
    )


# =========================================================
# TEST 4
# FEWER THAN 10 DIRECTIONAL VOTES
#
# Even if every vote is Yes:
#
# 9 Y / 0 N
#
# Expected: INSUFFICIENT DATA
# =========================================================

def test_insufficient_data_even_when_all_yes():

    df = make_topic_votes(
        yes_votes=9,
        no_votes=0,
    )

    row = run_tendency(df)

    assert (
        row["directional_topic_votes"]
        ==
        9
    )

    assert row["yes_pct"] == pytest.approx(
        100.0
    )

    assert (
        row["voting_tendency"]
        ==
        "INSUFFICIENT DATA"
    )


# =========================================================
# TEST 5
# EXACTLY 10 DIRECTIONAL VOTES QUALIFIES
# =========================================================

def test_exact_minimum_sample_qualifies():

    df = make_topic_votes(
        yes_votes=7,
        no_votes=3,
    )

    row = run_tendency(df)

    assert (
        row["directional_topic_votes"]
        ==
        EXPECTED_MINIMUM_VOTES
    )

    assert (
        row["voting_tendency"]
        ==
        "YES"
    )


# =========================================================
# TEST 6
# EXACT YES THRESHOLD
#
# 13 / 20 = 65%
#
# Expected: YES
# =========================================================

def test_exact_65_percent_is_yes():

    df = make_topic_votes(
        yes_votes=13,
        no_votes=7,
    )

    row = run_tendency(df)

    assert row["yes_pct"] == pytest.approx(
        65.0
    )

    assert (
        row["voting_tendency"]
        ==
        "YES"
    )


# =========================================================
# TEST 7
# JUST BELOW YES THRESHOLD
#
# 64 / 100 = 64%
#
# Expected: MIXED
# =========================================================

def test_below_65_percent_is_mixed():

    df = make_topic_votes(
        yes_votes=64,
        no_votes=36,
    )

    row = run_tendency(df)

    assert row["yes_pct"] == pytest.approx(
        64.0
    )

    assert (
        row["voting_tendency"]
        ==
        "MIXED"
    )


# =========================================================
# TEST 8
# EXACT NO THRESHOLD
#
# 7 / 20 = 35%
#
# Expected: NO
# =========================================================

def test_exact_35_percent_is_no():

    df = make_topic_votes(
        yes_votes=7,
        no_votes=13,
    )

    row = run_tendency(df)

    assert row["yes_pct"] == pytest.approx(
        35.0
    )

    assert (
        row["voting_tendency"]
        ==
        "NO"
    )


# =========================================================
# TEST 9
# JUST ABOVE NO THRESHOLD
#
# 36 / 100 = 36%
#
# Expected: MIXED
# =========================================================

def test_above_35_percent_is_mixed():

    df = make_topic_votes(
        yes_votes=36,
        no_votes=64,
    )

    row = run_tendency(df)

    assert row["yes_pct"] == pytest.approx(
        36.0
    )

    assert (
        row["voting_tendency"]
        ==
        "MIXED"
    )


# =========================================================
# TEST 10
# X / A / P DO NOT ENTER DIRECTIONAL DENOMINATOR
#
# Directional:
# 8 Y + 2 N = 10
#
# Non-directional:
# 20 X + 20 A + 20 P
#
# Yes rate should STILL be:
# 8 / 10 = 80%
#
# Not:
# 8 / 70
# =========================================================

def test_nondirectional_votes_excluded_from_denominator():

    df = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        x_votes=20,
        a_votes=20,
        p_votes=20,
    )

    row = run_tendency(df)

    assert (
        row["directional_topic_votes"]
        ==
        10
    )

    assert row["yes_votes"] == 8
    assert row["no_votes"] == 2

    assert row["yes_pct"] == pytest.approx(
        80.0
    )

    assert (
        row["voting_tendency"]
        ==
        "YES"
    )


# =========================================================
# TEST 11
# NON-DIRECTIONAL VOTES CANNOT CREATE SAMPLE SIZE
#
# Only:
# 5 Y + 4 N = 9 directional votes
#
# Even with 100 X votes, the member still has
# insufficient directional evidence.
# =========================================================

def test_nondirectional_votes_do_not_satisfy_minimum():

    df = make_topic_votes(
        yes_votes=5,
        no_votes=4,
        x_votes=100,
    )

    row = run_tendency(df)

    assert (
        row["directional_topic_votes"]
        ==
        9
    )

    assert (
        row["voting_tendency"]
        ==
        "INSUFFICIENT DATA"
    )


# =========================================================
# TEST 12
# TOTAL TOPIC EVENTS CAN EXCEED DIRECTIONAL EVENTS
# =========================================================

def test_topic_events_include_nondirectional_events():

    df = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        x_votes=3,
        a_votes=2,
        p_votes=1,
    )

    row = run_tendency(df)

    assert (
        row["topic_vote_events"]
        ==
        16
    )

    assert (
        row["directional_topic_votes"]
        ==
        10
    )


# =========================================================
# TEST 13
# OFFICIAL LIS PROVENANCE IS PRESERVED
#
# Provenance survives aggregation as metadata.
# =========================================================

def test_official_provenance_preserved():

    df = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        topic_name="Education",
        topic_provenance="Official LIS subject",
    )

    row = run_tendency(df)

    assert (
        row["topic_provenance"]
        ==
        "Official LIS subject"
    )


# =========================================================
# TEST 14
# DERIVED PROVENANCE IS PRESERVED
# =========================================================

def test_derived_provenance_preserved():

    df = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        topic_provenance=(
            "Derived from LIS bill description"
        ),
    )

    row = run_tendency(df)

    assert (
        row["topic_provenance"]
        ==
        "Derived from LIS bill description"
    )


# =========================================================
# TEST 15
# OFFICIAL AND DERIVED PROVENANCE MERGE INTO ONE TOPIC ROW
#
# Same member + same topic:
#
# Official LIS subject
# Derived from LIS bill description
#
# These should NOT become separate analytical rows.
#
# Why:
#
# The analytical identity is:
#
#     year + member + topic
#
# Provenance is metadata describing where the topic came
# from.
#
# The combined output should therefore contain one topic
# row with both provenance labels retained.
# =========================================================

def test_official_and_derived_provenance_merge_into_one_topic():

    official = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        topic_name="Education",
        topic_provenance="Official LIS subject",
        vote_prefix="OFFICIAL_",
    )

    derived = make_topic_votes(
        yes_votes=2,
        no_votes=8,
        topic_name="Education",
        topic_provenance=(
            "Derived from LIS bill description"
        ),
        vote_prefix="DERIVED_",
    )

    combined = pd.concat(
        [
            official,
            derived,
        ],
        ignore_index=True,
    )

    result = (
        build_delegate_topic_voting_tendency(
            combined
        )
    )

    assert len(result) == 1

    row = result.iloc[0]

    assert (
        row["topic_vote_events"]
        ==
        20
    )

    assert (
        row["directional_topic_votes"]
        ==
        20
    )

    assert (
        row["yes_votes"]
        ==
        10
    )

    assert (
        row["no_votes"]
        ==
        10
    )

    assert (
        row["yes_pct"]
        ==
        pytest.approx(
            50.0
        )
    )

    assert (
        row["voting_tendency"]
        ==
        "MIXED"
    )

    provenance = set(
        row[
            "topic_provenance"
        ]
        .split(" | ")
    )

    assert provenance == {
        "Official LIS subject",
        "Derived from LIS bill description",
    }


# =========================================================
# TEST 16
# SAME MEMBER + SAME VOTE + SAME TOPIC COUNTS ONCE
#
# This protects the new canonical grain.
#
# Even if duplicate input reaches this function, one vote
# event should not count twice for the same member/topic.
# =========================================================

def test_duplicate_member_vote_topic_counts_once():

    df = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        topic_name="Education",
        topic_provenance=(
            "Derived from LIS bill description"
        ),
    )

    duplicate = (
        df.iloc[
            [
                0
            ]
        ]
        .copy()
    )

    combined = pd.concat(
        [
            df,
            duplicate,
        ],
        ignore_index=True,
    )

    row = run_tendency(
        combined
    )

    assert (
        row["topic_vote_events"]
        ==
        10
    )

    assert (
        row["directional_topic_votes"]
        ==
        10
    )


# =========================================================
# TEST 17
# DIFFERENT TOPICS MUST NOT MERGE
# =========================================================

def test_different_topics_do_not_merge():

    education = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        topic_name="Education",
        vote_prefix="EDUCATION_",
    )

    housing = make_topic_votes(
        yes_votes=2,
        no_votes=8,
        topic_name="Housing",
        vote_prefix="HOUSING_",
    )

    combined = pd.concat(
        [
            education,
            housing,
        ],
        ignore_index=True,
    )

    result = (
        build_delegate_topic_voting_tendency(
            combined
        )
    )

    assert len(result) == 2

    topics = set(
        result[
            "topic_name"
        ]
    )

    assert topics == {
        "Education",
        "Housing",
    }


# =========================================================
# TEST 18
# DIFFERENT MEMBERS MUST NOT MERGE
# =========================================================

def test_different_members_do_not_merge():

    member_one = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        member_id="H9001",
        member_name="Test Member One",
        vote_prefix="MEMBER1_",
    )

    member_two = make_topic_votes(
        yes_votes=2,
        no_votes=8,
        member_id="H9002",
        member_name="Test Member Two",
        vote_prefix="MEMBER2_",
    )

    combined = pd.concat(
        [
            member_one,
            member_two,
        ],
        ignore_index=True,
    )

    result = (
        build_delegate_topic_voting_tendency(
            combined
        )
    )

    assert len(result) == 2

    tendencies = dict(
        zip(
            result["member_id"],
            result["voting_tendency"],
        )
    )

    assert (
        tendencies["H9001"]
        ==
        "YES"
    )

    assert (
        tendencies["H9002"]
        ==
        "NO"
    )


# =========================================================
# TEST 19
# YEAR MUST NOT MERGE
# =========================================================

def test_different_years_do_not_merge():

    year_2025 = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        year=2025,
        vote_prefix="Y2025_",
    )

    year_2026 = make_topic_votes(
        yes_votes=2,
        no_votes=8,
        year=2026,
        vote_prefix="Y2026_",
    )

    combined = pd.concat(
        [
            year_2025,
            year_2026,
        ],
        ignore_index=True,
    )

    result = (
        build_delegate_topic_voting_tendency(
            combined
        )
    )

    assert len(result) == 2

    tendencies = dict(
        zip(
            result["year"],
            result["voting_tendency"],
        )
    )

    assert (
        tendencies[2025]
        ==
        "YES"
    )

    assert (
        tendencies[2026]
        ==
        "NO"
    )


# =========================================================
# TEST 20
# YES + NO MUST EQUAL DIRECTIONAL VOTES
# =========================================================

def test_directional_vote_reconciliation():

    df = make_topic_votes(
        yes_votes=7,
        no_votes=5,
        x_votes=3,
        a_votes=2,
        p_votes=1,
    )

    row = run_tendency(df)

    assert (
        row["yes_votes"]
        +
        row["no_votes"]
        ==
        row["directional_topic_votes"]
    )


# =========================================================
# TEST 21
# YES PCT + NO PCT = 100 FOR DIRECTIONAL SAMPLE
# =========================================================

def test_yes_no_percent_reconciliation():

    df = make_topic_votes(
        yes_votes=7,
        no_votes=5,
    )

    row = run_tendency(df)

    assert (
        row["yes_pct"]
        +
        row["no_pct"]
    ) == pytest.approx(
        100.0
    )


# =========================================================
# TEST 22
# LABELS MUST COME FROM APPROVED SET
# =========================================================

@pytest.mark.parametrize(
    "yes_votes,no_votes",
    [
        (8, 2),
        (5, 5),
        (2, 8),
        (9, 0),
    ],
)
def test_tendency_label_is_valid(
    yes_votes,
    no_votes,
):

    df = make_topic_votes(
        yes_votes=yes_votes,
        no_votes=no_votes,
    )

    row = run_tendency(df)

    assert (
        row["voting_tendency"]
        in {
            "YES",
            "NO",
            "MIXED",
            "INSUFFICIENT DATA",
        }
    )