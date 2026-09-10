import pandas as pd
import pytest

from topic_stance_analysis import build_voting_tendency_yoy
from year_over_year_analysis import build_delegate_yoy, build_topic_yoy


def delegate(member="H9999", *, eligible=100, cross=5, cross_pct=5.0, breaks=10, break_pct=10.0):
    return pd.DataFrame([{"member_id": member, "MBR_NAME": member, "party": "D", "directional_votes": 100,
                          "eligible_cross_party_votes": eligible, "party_breaks": breaks,
                          "cross_party_votes": cross, "cross_party_pct": cross_pct, "party_break_pct": break_pct}])


def tendency(year, label, *, member="H9999", topic="Education", provenance="Official LIS subject", directional=10, yes=8):
    return pd.DataFrame([{"year": year, "member_id": member, "MBR_NAME": member, "party": "D", "topic_name": topic,
                          "topic_provenance": provenance, "topic_vote_events": directional, "directional_topic_votes": directional,
                          "yes_votes": yes, "no_votes": directional - yes, "yes_pct": yes / directional * 100,
                          "no_pct": (directional - yes) / directional * 100, "voting_tendency": label}])


def topic_behavior(*, member="H9999", topic="Education", eligible=30, crossed=3, rate=10.0):
    return pd.DataFrame([{"member_id": member, "MBR_NAME": member, "party": "D", "topic_name": topic,
                          "topic_vote_events": eligible, "eligible_topic_events": eligible,
                          "party_break_events": crossed + 1, "cross_party_events": crossed, "cross_party_pct": rate}])


def test_delegate_changes_are_right_year_minus_left_year():
    result = build_delegate_yoy(delegate(cross=5, cross_pct=3.5, breaks=10, break_pct=7),
                                delegate(cross=13, cross_pct=6.0, breaks=16, break_pct=9)).iloc[0]
    assert result.cross_party_vote_change == 8
    assert result.cross_party_pct_change == pytest.approx(2.5)
    assert result.party_break_change == 6
    assert result.party_break_pct_change == pytest.approx(2.0)


@pytest.mark.parametrize("left,right,expected", [(True, True, "Present both years"), (True, False, "2025 only"), (False, True, "2026 only")])
def test_delegate_presence_status(left, right, expected):
    empty = delegate().iloc[0:0]
    result = build_delegate_yoy(delegate() if left else empty, delegate() if right else empty)
    assert result.iloc[0].member_status == expected


@pytest.mark.parametrize("eligible_left,eligible_right,expected", [(100, 100, True), (19, 100, False), (100, 19, False)])
def test_delegate_comparability_requires_both_samples(eligible_left, eligible_right, expected):
    row = build_delegate_yoy(delegate(eligible=eligible_left), delegate(eligible=eligible_right)).iloc[0]
    assert bool(row.comparable_sample) is expected


@pytest.mark.parametrize("left,right,changed", [
    ("YES", "NO", True), ("YES", "MIXED", True), ("NO", "MIXED", True),
    ("YES", "YES", False), ("INSUFFICIENT DATA", "YES", False), ("NO", "INSUFFICIENT DATA", False),
])
def test_topic_behavior_change_requires_two_sufficient_labels(left, right, changed):
    result = build_voting_tendency_yoy(tendency(2025, left), tendency(2026, right)).iloc[0]
    assert bool(result.voting_tendency_changed) is changed


def test_topic_change_and_provenance_are_handled_at_correct_grain():
    result = build_voting_tendency_yoy(
        tendency(2025, "YES", provenance="Official LIS subject", yes=7),
        tendency(2026, "MIXED", provenance="Derived from LIS bill summary", yes=5),
    ).iloc[0]
    assert result.yes_pct_change == pytest.approx(-20.0)
    assert result.topic_status == "Present both years"
    assert result.topic_provenance_2025 != result.topic_provenance_2026


def test_different_members_and_topics_do_not_merge():
    left = pd.concat([tendency(2025, "YES"), tendency(2025, "NO", member="H8888", topic="Housing", yes=2)])
    right = pd.concat([tendency(2026, "YES"), tendency(2026, "NO", member="H8888", topic="Housing", yes=2)])
    result = build_voting_tendency_yoy(left, right)
    assert len(result) == 2
    assert not result.duplicated(["member_id", "topic_name"]).any()


def test_cross_party_topic_yoy_uses_delegate_topic_grain_without_classification():
    result = build_topic_yoy(topic_behavior(rate=10.0), topic_behavior(rate=14.0, crossed=5)).iloc[0]
    assert result.topic_status == "Present both years"
    assert result.cross_party_pct_change == pytest.approx(4.0)
    assert "classification" not in result.index
