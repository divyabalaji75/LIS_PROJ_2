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
# Each row represents one member's vote event associated
# with one topic.
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
    classification="Derived from LIS bill description",
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
        start=1
    ):

        rows.append(
            {
                "year": year,
                "vote_id": f"TEST{i:04d}",
                "member_id": member_id,
                "MBR_NAME": member_name,
                "party": party,
                "topic_name": topic_name,
                "classification": classification,
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
# OFFICIAL LIS SUBJECT REMAINS OFFICIAL
#
# Provenance must survive aggregation.
# =========================================================

def test_official_classification_preserved():

    df = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        topic_name="Education",
        classification="Official LIS subject",
    )

    row = run_tendency(df)

    assert (
        row["classification"]
        ==
        "Official LIS subject"
    )


# =========================================================
# TEST 14
# DERIVED CLASSIFICATION REMAINS DERIVED
# =========================================================

def test_derived_classification_preserved():

    df = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        classification=(
            "Derived from LIS bill description"
        ),
    )

    row = run_tendency(df)

    assert (
        row["classification"]
        ==
        "Derived from LIS bill description"
    )


# =========================================================
# TEST 15
# DIFFERENT CLASSIFICATION PROVENANCE MUST NOT MERGE
#
# Same member + same topic name:
#
# Official LIS subject
# Derived from LIS bill description
#
# These must remain separate analytical rows.
# =========================================================

def test_official_and_derived_topics_do_not_merge():

    official = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        classification="Official LIS subject",
    )

    derived = make_topic_votes(
        yes_votes=2,
        no_votes=8,
        classification=(
            "Derived from LIS bill description"
        ),
    )

    # Make vote IDs distinct.
    derived = derived.copy()

    derived["vote_id"] = (
        "DERIVED_"
        +
        derived["vote_id"]
    )

    combined = pd.concat(
        [
            official,
            derived,
        ],
        ignore_index=True
    )

    result = (
        build_delegate_topic_voting_tendency(
            combined
        )
    )

    assert len(result) == 2

    classifications = set(
        result[
            "classification"
        ]
    )

    assert classifications == {
        "Official LIS subject",
        "Derived from LIS bill description",
    }


# =========================================================
# TEST 16
# DIFFERENT TOPICS MUST NOT MERGE
# =========================================================

def test_different_topics_do_not_merge():

    education = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        topic_name="Education",
    )

    housing = make_topic_votes(
        yes_votes=2,
        no_votes=8,
        topic_name="Housing",
    )

    housing = housing.copy()

    housing["vote_id"] = (
        "HOUSING_"
        +
        housing["vote_id"]
    )

    combined = pd.concat(
        [
            education,
            housing,
        ],
        ignore_index=True
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
# TEST 17
# DIFFERENT MEMBERS MUST NOT MERGE
# =========================================================

def test_different_members_do_not_merge():

    member_one = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        member_id="H9001",
        member_name="Test Member One",
    )

    member_two = make_topic_votes(
        yes_votes=2,
        no_votes=8,
        member_id="H9002",
        member_name="Test Member Two",
    )

    member_two = member_two.copy()

    member_two["vote_id"] = (
        "MEMBER2_"
        +
        member_two["vote_id"]
    )

    combined = pd.concat(
        [
            member_one,
            member_two,
        ],
        ignore_index=True
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
# TEST 18
# YEAR MUST NOT MERGE
# =========================================================

def test_different_years_do_not_merge():

    year_2025 = make_topic_votes(
        yes_votes=8,
        no_votes=2,
        year=2025,
    )

    year_2026 = make_topic_votes(
        yes_votes=2,
        no_votes=8,
        year=2026,
    )

    year_2026 = year_2026.copy()

    year_2026["vote_id"] = (
        "Y2026_"
        +
        year_2026["vote_id"]
    )

    combined = pd.concat(
        [
            year_2025,
            year_2026,
        ],
        ignore_index=True
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

    assert tendencies[2025] == "YES"
    assert tendencies[2026] == "NO"


# =========================================================
# TEST 19
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
# TEST 20
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
# TEST 21
# LABELS MUST COME FROM APPROVED SET
# =========================================================

@pytest.mark.parametrize(
    "yes_votes,no_votes",
    [
        (8, 2),
        (5, 5),
        (2, 8),
        (9, 0),
    ]
)
def test_tendency_label_is_valid(
    yes_votes,
    no_votes
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