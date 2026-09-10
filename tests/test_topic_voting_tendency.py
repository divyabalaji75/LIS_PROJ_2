import pandas as pd
import pytest

from topic_stance_analysis import build_delegate_topic_voting_tendency


def votes(yes, no, other="", *, member="H9999", topic="Education", provenance="Official LIS subject", year=2026):
    values = ["Y"] * yes + ["N"] * no + list(other)
    return pd.DataFrame([
        {"year": year, "vote_id": f"V{i}", "member_id": member, "MBR_NAME": member,
         "party": "D", "topic_name": topic, "topic_provenance": provenance, "vote": value}
        for i, value in enumerate(values)
    ])


def summarize(frame):
    result = build_delegate_topic_voting_tendency(frame)
    assert len(result) == 1
    return result.iloc[0]


@pytest.mark.parametrize(
    "yes,no,expected",
    [(8, 2, "YES"), (2, 8, "NO"), (5, 5, "MIXED"), (9, 0, "INSUFFICIENT DATA"),
     (7, 3, "YES"), (6, 4, "MIXED"), (3, 7, "NO"), (4, 6, "MIXED")],
)
def test_tendency_thresholds_and_minimum_sample(yes, no, expected):
    row = summarize(votes(yes, no))
    assert row.voting_tendency == expected
    assert row.directional_topic_votes == yes + no
    assert row.yes_votes + row.no_votes == row.directional_topic_votes


def test_nondirectional_votes_are_events_but_not_denominator():
    row = summarize(votes(7, 3, "XAP"))
    assert row.topic_vote_events == 13
    assert row.directional_topic_votes == 10
    assert (row.yes_pct, row.no_pct, row.voting_tendency) == (70.0, 30.0, "YES")


def test_nondirectional_votes_do_not_satisfy_minimum():
    row = summarize(votes(6, 3, "XXXXX"))
    assert row.directional_topic_votes == 9
    assert row.voting_tendency == "INSUFFICIENT DATA"


def test_provenance_is_metadata_and_does_not_split_topic_grain():
    frame = pd.concat([
        votes(5, 0, provenance="Official LIS subject"),
        votes(5, 0, provenance="Derived from LIS bill summary").assign(vote_id=lambda x: "S" + x.vote_id),
    ])
    row = summarize(frame)
    assert row.directional_topic_votes == 10
    assert {part.strip() for part in row.topic_provenance.split("|")} == {"Official LIS subject", "Derived from LIS bill summary"}


def test_duplicate_member_vote_topic_counts_once():
    frame = votes(7, 3)
    row = summarize(pd.concat([frame, frame.iloc[[0]]], ignore_index=True))
    assert row.topic_vote_events == 10


def test_member_topic_and_year_remain_distinct_dimensions():
    frame = pd.concat([
        votes(7, 3),
        votes(7, 3, member="H8888"),
        votes(7, 3, topic="Housing"),
        votes(7, 3, year=2025),
    ], ignore_index=True)
    result = build_delegate_topic_voting_tendency(frame)
    assert len(result) == 4
    assert not result.duplicated(["year", "member_id", "topic_name"]).any()
