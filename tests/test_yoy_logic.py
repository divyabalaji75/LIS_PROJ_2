import pandas as pd
import pytest

from year_over_year_analysis import (
    build_delegate_yoy,
)

from topic_stance_analysis import (
    build_voting_tendency_yoy,
)


# =========================================================
# HELPERS
# =========================================================

def make_delegate_behavior(
    *,
    member_id="H9999",
    member_name="Test Delegate",
    party="D",
    directional_votes=100,
    eligible_cross_party_votes=100,
    party_breaks=10,
    cross_party_votes=5,
    cross_party_pct=5.0,
    party_break_pct=10.0,
):

    return pd.DataFrame(
        [
            {
                "member_id": member_id,
                "MBR_NAME": member_name,
                "party": party,
                "directional_votes": directional_votes,
                "eligible_cross_party_votes": (
                    eligible_cross_party_votes
                ),
                "party_breaks": party_breaks,
                "cross_party_votes": cross_party_votes,
                "cross_party_pct": cross_party_pct,
                "party_break_pct": party_break_pct,
            }
        ]
    )


def make_topic_tendency(
    *,
    member_id="H9999",
    member_name="Test Delegate",
    party="D",
    topic_name="Education",
    classification="Derived from LIS bill description",
    yes_votes=8,
    no_votes=2,
    directional_topic_votes=10,
    yes_pct=80.0,
    no_pct=20.0,
    voting_tendency="YES",
):

    return pd.DataFrame(
        [
            {
                "member_id": member_id,
                "MBR_NAME": member_name,
                "party": party,
                "topic_name": topic_name,
                "classification": classification,
                "yes_votes": yes_votes,
                "no_votes": no_votes,
                "directional_topic_votes": (
                    directional_topic_votes
                ),
                "yes_pct": yes_pct,
                "no_pct": no_pct,
                "voting_tendency": voting_tendency,
            }
        ]
    )


# =========================================================
# DELEGATE YOY TESTS
# =========================================================


# =========================================================
# TEST 1
# CROSS-PARTY RATE CHANGE IS 2026 - 2025
# =========================================================

def test_delegate_cross_party_pct_change():

    df_2025 = make_delegate_behavior(
        cross_party_pct=3.59,
        cross_party_votes=56,
    )

    df_2026 = make_delegate_behavior(
        cross_party_pct=6.28,
        cross_party_votes=136,
    )

    result = build_delegate_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert (
        row["cross_party_pct_change"]
        ==
        pytest.approx(
            2.69
        )
    )


# =========================================================
# TEST 2
# RAW CROSS-PARTY COUNT CHANGE IS ALSO CORRECT
# =========================================================

def test_delegate_cross_party_vote_change():

    df_2025 = make_delegate_behavior(
        cross_party_votes=56,
    )

    df_2026 = make_delegate_behavior(
        cross_party_votes=136,
    )

    result = build_delegate_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert (
        row["cross_party_vote_change"]
        ==
        80
    )


# =========================================================
# TEST 3
# PARTY BREAK RATE CHANGE IS CORRECT
# =========================================================

def test_delegate_party_break_pct_change():

    df_2025 = make_delegate_behavior(
        party_break_pct=7.11,
    )

    df_2026 = make_delegate_behavior(
        party_break_pct=8.44,
    )

    result = build_delegate_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert (
        row["party_break_pct_change"]
        ==
        pytest.approx(
            1.33
        )
    )


# =========================================================
# TEST 4
# SAME MEMBER IN BOTH YEARS IS PRESENT BOTH YEARS
# =========================================================

def test_delegate_present_both_years():

    df_2025 = make_delegate_behavior()
    df_2026 = make_delegate_behavior()

    result = build_delegate_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert (
        row["member_status"]
        ==
        "Present both years"
    )


# =========================================================
# TEST 5
# MEMBER ONLY IN 2025
# =========================================================

def test_delegate_2025_only():

    df_2025 = make_delegate_behavior()

    df_2026 = pd.DataFrame(
        columns=df_2025.columns
    )

    result = build_delegate_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert (
        row["member_status"]
        ==
        "2025 only"
    )


# =========================================================
# TEST 6
# MEMBER ONLY IN 2026
# =========================================================

def test_delegate_2026_only():

    df_2026 = make_delegate_behavior()

    df_2025 = pd.DataFrame(
        columns=df_2026.columns
    )

    result = build_delegate_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert (
        row["member_status"]
        ==
        "2026 only"
    )


# =========================================================
# TEST 7
# DELEGATE COMPARABLE SAMPLE REQUIRES
# ENOUGH ELIGIBLE VOTES IN BOTH YEARS
# =========================================================

def test_delegate_comparable_sample_requires_both_years():

    df_2025 = make_delegate_behavior(
        eligible_cross_party_votes=100,
    )

    df_2026 = make_delegate_behavior(
        eligible_cross_party_votes=100,
    )

    result = build_delegate_yoy(
        df_2025,
        df_2026,
    )

    assert bool(
        result.iloc[0][
            "comparable_sample"
        ]
    )


# =========================================================
# TEST 8
# DELEGATE NOT COMPARABLE IF ONE YEAR BELOW THRESHOLD
# =========================================================

def test_delegate_not_comparable_if_one_year_too_small():

    df_2025 = make_delegate_behavior(
        eligible_cross_party_votes=100,
    )

    df_2026 = make_delegate_behavior(
        eligible_cross_party_votes=10,
    )

    result = build_delegate_yoy(
        df_2025,
        df_2026,
    )

    assert not bool(
        result.iloc[0][
            "comparable_sample"
        ]
    )


# =========================================================
# TOPIC VOTING-TENDENCY YOY TESTS
# =========================================================


# =========================================================
# TEST 9
# YES -> NO IS A TRUE BEHAVIOR CHANGE
# =========================================================

def test_yes_to_no_is_behavior_change():

    df_2025 = make_topic_tendency(
        voting_tendency="YES",
        yes_pct=80.0,
        no_pct=20.0,
    )

    df_2026 = make_topic_tendency(
        voting_tendency="NO",
        yes_pct=20.0,
        no_pct=80.0,
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert bool(
        row[
            "comparable_tendency"
        ]
    )

    assert bool(
        row[
            "voting_tendency_changed"
        ]
    )

    assert not bool(
        row[
            "data_availability_changed"
        ]
    )


# =========================================================
# TEST 10
# YES -> MIXED IS A TRUE BEHAVIOR CHANGE
# =========================================================

def test_yes_to_mixed_is_behavior_change():

    df_2025 = make_topic_tendency(
        voting_tendency="YES",
        yes_pct=80.0,
        no_pct=20.0,
    )

    df_2026 = make_topic_tendency(
        voting_tendency="MIXED",
        yes_pct=50.0,
        no_pct=50.0,
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert bool(
        row[
            "voting_tendency_changed"
        ]
    )


# =========================================================
# TEST 11
# NO -> MIXED IS A TRUE BEHAVIOR CHANGE
# =========================================================

def test_no_to_mixed_is_behavior_change():

    df_2025 = make_topic_tendency(
        voting_tendency="NO",
        yes_pct=20.0,
        no_pct=80.0,
    )

    df_2026 = make_topic_tendency(
        voting_tendency="MIXED",
        yes_pct=50.0,
        no_pct=50.0,
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert bool(
        row[
            "voting_tendency_changed"
        ]
    )


# =========================================================
# TEST 12
# SAME TENDENCY BOTH YEARS IS NOT A CHANGE
# =========================================================

def test_same_tendency_is_not_behavior_change():

    df_2025 = make_topic_tendency(
        voting_tendency="YES",
        yes_pct=80.0,
    )

    df_2026 = make_topic_tendency(
        voting_tendency="YES",
        yes_pct=90.0,
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert bool(
        row[
            "comparable_tendency"
        ]
    )

    assert not bool(
        row[
            "voting_tendency_changed"
        ]
    )


# =========================================================
# TEST 13
# INSUFFICIENT -> YES
#
# NOT a behavior change.
#
# It is a data availability change.
# =========================================================

def test_insufficient_to_yes_not_behavior_change():

    df_2025 = make_topic_tendency(
        voting_tendency="INSUFFICIENT DATA",
        directional_topic_votes=5,
        yes_pct=80.0,
        no_pct=20.0,
    )

    df_2026 = make_topic_tendency(
        voting_tendency="YES",
        directional_topic_votes=20,
        yes_pct=80.0,
        no_pct=20.0,
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert not bool(
        row[
            "comparable_tendency"
        ]
    )

    assert not bool(
        row[
            "voting_tendency_changed"
        ]
    )

    assert bool(
        row[
            "data_availability_changed"
        ]
    )


# =========================================================
# TEST 14
# INSUFFICIENT -> NO
#
# NOT a behavior change.
# =========================================================

def test_insufficient_to_no_not_behavior_change():

    df_2025 = make_topic_tendency(
        voting_tendency="INSUFFICIENT DATA",
        directional_topic_votes=5,
        yes_pct=20.0,
        no_pct=80.0,
    )

    df_2026 = make_topic_tendency(
        voting_tendency="NO",
        directional_topic_votes=20,
        yes_pct=20.0,
        no_pct=80.0,
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert not bool(
        row[
            "voting_tendency_changed"
        ]
    )

    assert bool(
        row[
            "data_availability_changed"
        ]
    )


# =========================================================
# TEST 15
# YES -> INSUFFICIENT
#
# NOT a behavior change.
# =========================================================

def test_yes_to_insufficient_not_behavior_change():

    df_2025 = make_topic_tendency(
        voting_tendency="YES",
        directional_topic_votes=20,
        yes_pct=80.0,
        no_pct=20.0,
    )

    df_2026 = make_topic_tendency(
        voting_tendency="INSUFFICIENT DATA",
        directional_topic_votes=5,
        yes_pct=80.0,
        no_pct=20.0,
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert not bool(
        row[
            "comparable_tendency"
        ]
    )

    assert not bool(
        row[
            "voting_tendency_changed"
        ]
    )

    assert bool(
        row[
            "data_availability_changed"
        ]
    )


# =========================================================
# TEST 16
# NO -> INSUFFICIENT
#
# NOT a behavior change.
# =========================================================

def test_no_to_insufficient_not_behavior_change():

    df_2025 = make_topic_tendency(
        voting_tendency="NO",
        directional_topic_votes=20,
        yes_pct=20.0,
        no_pct=80.0,
    )

    df_2026 = make_topic_tendency(
        voting_tendency="INSUFFICIENT DATA",
        directional_topic_votes=5,
        yes_pct=20.0,
        no_pct=80.0,
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert not bool(
        row[
            "voting_tendency_changed"
        ]
    )

    assert bool(
        row[
            "data_availability_changed"
        ]
    )


# =========================================================
# TEST 17
# MIXED -> INSUFFICIENT
#
# NOT a behavior change.
# =========================================================

def test_mixed_to_insufficient_not_behavior_change():

    df_2025 = make_topic_tendency(
        voting_tendency="MIXED",
        directional_topic_votes=20,
        yes_pct=50.0,
        no_pct=50.0,
    )

    df_2026 = make_topic_tendency(
        voting_tendency="INSUFFICIENT DATA",
        directional_topic_votes=5,
        yes_pct=50.0,
        no_pct=50.0,
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert not bool(
        row[
            "voting_tendency_changed"
        ]
    )

    assert bool(
        row[
            "data_availability_changed"
        ]
    )


# =========================================================
# TEST 18
# INSUFFICIENT -> MIXED
#
# NOT a behavior change.
# =========================================================

def test_insufficient_to_mixed_not_behavior_change():

    df_2025 = make_topic_tendency(
        voting_tendency="INSUFFICIENT DATA",
        directional_topic_votes=5,
        yes_pct=50.0,
        no_pct=50.0,
    )

    df_2026 = make_topic_tendency(
        voting_tendency="MIXED",
        directional_topic_votes=20,
        yes_pct=50.0,
        no_pct=50.0,
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert not bool(
        row[
            "voting_tendency_changed"
        ]
    )

    assert bool(
        row[
            "data_availability_changed"
        ]
    )


# =========================================================
# TEST 19
# INSUFFICIENT -> INSUFFICIENT
#
# Neither behavioral nor availability change.
# =========================================================

def test_insufficient_to_insufficient_not_change():

    df_2025 = make_topic_tendency(
        voting_tendency="INSUFFICIENT DATA",
        directional_topic_votes=5,
    )

    df_2026 = make_topic_tendency(
        voting_tendency="INSUFFICIENT DATA",
        directional_topic_votes=6,
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert not bool(
        row[
            "comparable_tendency"
        ]
    )

    assert not bool(
        row[
            "voting_tendency_changed"
        ]
    )

    assert not bool(
        row[
            "data_availability_changed"
        ]
    )


# =========================================================
# TEST 20
# YES PERCENTAGE CHANGE CALCULATES CORRECTLY
# =========================================================

def test_topic_yes_pct_change():

    df_2025 = make_topic_tendency(
        voting_tendency="MIXED",
        yes_pct=50.0,
        no_pct=50.0,
    )

    df_2026 = make_topic_tendency(
        voting_tendency="YES",
        yes_pct=75.0,
        no_pct=25.0,
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    row = result.iloc[0]

    assert (
        row[
            "yes_pct_change"
        ]
        ==
        pytest.approx(
            25.0
        )
    )


# =========================================================
# TEST 21
# CLASSIFICATION PROVENANCE IS PART OF JOIN KEY
#
# Same member + same topic name,
# but different provenance,
# must NOT be merged.
# =========================================================

def test_classification_provenance_not_merged():

    df_2025 = make_topic_tendency(
        classification="Official LIS subject",
    )

    df_2026 = make_topic_tendency(
        classification=(
            "Derived from LIS bill description"
        ),
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    assert len(result) == 2

    statuses = set(
        result[
            "topic_status"
        ]
    )

    assert statuses == {
        "2025 only",
        "2026 only",
    }


# =========================================================
# TEST 22
# SAME TOPIC + SAME CLASSIFICATION JOINS
# =========================================================

def test_same_topic_and_classification_join():

    df_2025 = make_topic_tendency(
        topic_name="Housing",
        classification=(
            "Derived from LIS bill description"
        ),
    )

    df_2026 = make_topic_tendency(
        topic_name="Housing",
        classification=(
            "Derived from LIS bill description"
        ),
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    assert len(result) == 1

    assert (
        result.iloc[0][
            "topic_status"
        ]
        ==
        "Present both years"
    )


# =========================================================
# TEST 23
# DIFFERENT MEMBER IDS MUST NOT MERGE
# =========================================================

def test_different_members_not_merged():

    df_2025 = make_topic_tendency(
        member_id="H9001",
        member_name="Member One",
    )

    df_2026 = make_topic_tendency(
        member_id="H9002",
        member_name="Member Two",
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    assert len(result) == 2


# =========================================================
# TEST 24
# DIFFERENT TOPICS MUST NOT MERGE
# =========================================================

def test_different_topics_not_merged():

    df_2025 = make_topic_tendency(
        topic_name="Education",
    )

    df_2026 = make_topic_tendency(
        topic_name="Housing",
    )

    result = build_voting_tendency_yoy(
        df_2025,
        df_2026,
    )

    assert len(result) == 2