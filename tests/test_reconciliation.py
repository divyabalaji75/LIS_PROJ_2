from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lis_common import configured_test_years

YEARS = configured_test_years()
ROOT = Path("data/processed")


def load(name, year):
    return pd.read_csv(ROOT / f"{name}_{year}.csv", low_memory=False)


@pytest.mark.parametrize("year", YEARS)
def test_vote_flags_obey_directional_and_true_cross_party_definitions(year):
    votes = load("vote_fact", year)
    directional = votes.vote.isin(["Y", "N"])
    nondirectional = ~directional
    assert not votes.loc[nondirectional, "broke_with_party"].astype(bool).any()
    assert not votes.loc[nondirectional, "cross_party"].astype(bool).any()
    crossed = votes.cross_party.astype(bool)
    assert votes.loc[crossed, "broke_with_party"].astype(bool).all()
    assert votes.loc[crossed, "vote"].eq(votes.loc[crossed, "other_party_position"]).all()
    assert votes.loc[crossed, "vote"].ne(votes.loc[crossed, "own_party_position"]).all()


@pytest.mark.parametrize("year", YEARS)
def test_delegate_behavior_reconciles_to_house_vote_fact(year):
    votes = load("vote_fact", year)
    summary = load("delegate_behavior", year)
    house = votes[votes.MBR_HOU.eq("H")].copy()
    expected = house.groupby("member_id").agg(
        directional_votes=("vote", lambda s: s.isin(["Y", "N"]).sum()),
        party_breaks=("broke_with_party", "sum"), cross_party_votes=("cross_party", "sum"),
    )
    actual = summary.set_index("member_id")
    assert set(actual.index) == set(expected.index)
    for column in expected:
        pd.testing.assert_series_equal(pd.to_numeric(actual[column]).sort_index(), expected[column].sort_index(), check_names=False)


@pytest.mark.parametrize("year", YEARS)
def test_classification_partition_and_coverage_reconcile(year):
    bills = load("bill_lookup", year)
    topics = load("bill_topic_lookup", year)
    coverage = load("topic_coverage", year)
    partition = topics[["Bill_id", "classification"]].drop_duplicates()
    assert set(partition.Bill_id) == set(bills.Bill_id)
    assert partition.groupby("Bill_id").classification.nunique().eq(1).all()
    counts = partition.groupby("classification").Bill_id.nunique()
    reported = coverage.set_index("classification").bill_count.astype(int)
    pd.testing.assert_series_equal(counts.sort_index(), reported.sort_index(), check_names=False)


@pytest.mark.parametrize("year", YEARS)
def test_member_vote_topic_has_canonical_grain_and_vote_backing(year):
    member_topics = load("member_vote_topic", year)
    votes = load("vote_fact", year)
    grain = ["year", "vote_id", "member_id", "topic_name"]
    assert not member_topics.duplicated(grain).any()
    assert "topic_provenance" in member_topics and "classification" not in member_topics
    checked = member_topics.merge(votes[["year", "vote_id", "member_id", "vote"]], on=["year", "vote_id", "member_id"],
                                  how="left", validate="many_to_one", suffixes=("_topic", "_fact"), indicator=True)
    assert checked._merge.eq("both").all()
    assert checked.vote_topic.eq(checked.vote_fact).all()
    assert member_topics.topic_provenance.fillna("").str.strip().ne("").all()


@pytest.mark.parametrize("year", YEARS)
def test_delegate_topic_summary_reconciles_to_member_topic_events(year):
    member_topics = load("member_vote_topic", year)
    delegates = load("delegate_topic_behavior", year)
    expected = member_topics.groupby(["member_id", "topic_name"]).agg(
        topic_vote_events=("vote_id", "nunique"), party_break_events=("broke_with_party", "sum"),
        cross_party_events=("cross_party", "sum"),
    )
    actual = delegates.set_index(["member_id", "topic_name"])
    assert not delegates.duplicated(["member_id", "topic_name"]).any()
    for column in expected:
        pd.testing.assert_series_equal(pd.to_numeric(actual[column]).sort_index(), expected[column].sort_index(), check_names=False)


@pytest.mark.parametrize("year", YEARS)
def test_topic_tendency_counts_percentages_and_labels_reconcile(year):
    tendency = load("delegate_topic_voting_tendency", year)
    directional = pd.to_numeric(tendency.directional_topic_votes)
    yes, no = pd.to_numeric(tendency.yes_votes), pd.to_numeric(tendency.no_votes)
    assert (yes + no).eq(directional).all()
    mask = directional.gt(0)
    assert np.allclose(pd.to_numeric(tendency.loc[mask, "yes_pct"]), yes[mask] / directional[mask] * 100)
    assert np.allclose(pd.to_numeric(tendency.loc[mask, "no_pct"]), no[mask] / directional[mask] * 100)
    expected = pd.Series("MIXED", index=tendency.index)
    expected.loc[directional.lt(10)] = "INSUFFICIENT DATA"
    expected.loc[directional.ge(10) & (yes / directional).ge(.65)] = "YES"
    expected.loc[directional.ge(10) & (yes / directional).le(.35)] = "NO"
    assert tendency.voting_tendency.eq(expected).all()


@pytest.mark.parametrize("year", YEARS)
def test_member_and_party_keys_are_populated_across_analysis_outputs(year):
    for name in ("vote_fact", "member_vote_topic", "delegate_behavior", "delegate_topic_behavior", "delegate_topic_voting_tendency"):
        frame = load(name, year)
        assert frame.member_id.fillna("").astype(str).str.strip().ne("").all(), name
        assert frame.party.fillna("").astype(str).str.strip().ne("").all(), name
