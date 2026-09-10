from pathlib import Path

import pandas as pd
import pytest

from lis_common import configured_test_years

YEARS = configured_test_years()
ROOT = Path("data/processed")


def load(name, year):
    path = ROOT / f"{name}_{year}.csv"
    assert path.exists(), f"Missing required file: {path}"
    return pd.read_csv(path, dtype=str).fillna("")


@pytest.mark.parametrize("year", YEARS)
def test_bridge_contract_and_history_grain(year):
    bridge = load("vote_bill_bridge", year)
    required = ["vote_id", "Bill_id", "History_date", "History_description"]
    assert set(required) <= set(bridge.columns) and not bridge.empty
    assert bridge[required].apply(lambda s: s.str.strip().ne("").all()).all()
    assert not bridge.duplicated(required).any()


@pytest.mark.parametrize("year", YEARS)
def test_bridge_keys_have_canonical_parents(year):
    bridge, votes, bills = load("vote_bill_bridge", year), load("vote_fact", year), load("bill_lookup", year)
    assert set(bridge.vote_id) <= set(votes.vote_id)
    assert set(bridge.Bill_id) <= set(bills.Bill_id)
    assert not bills.Bill_id.duplicated().any()


@pytest.mark.parametrize("year", YEARS)
def test_bridge_preserves_multibill_and_unmatched_vote_events(year):
    bridge, votes = load("vote_bill_bridge", year), load("vote_fact", year)
    assert bridge.groupby("vote_id")["Bill_id"].nunique().gt(1).any()
    assert set(votes.vote_id) - set(bridge.vote_id), "unmatched vote events must remain in vote_fact"
    assert not votes.duplicated(["year", "vote_id", "member_id"]).any()


@pytest.mark.parametrize("year", YEARS)
def test_downstream_bill_join_expands_only_through_known_relationships(year):
    bridge, votes = load("vote_bill_bridge", year), load("vote_fact", year)
    relationships = bridge[["vote_id", "Bill_id"]].drop_duplicates()
    expanded = votes.merge(relationships, on="vote_id", how="inner")
    assert len(expanded) > len(votes[votes.vote_id.isin(bridge.vote_id)])
    assert set(zip(expanded.vote_id, expanded.Bill_id)) <= set(zip(bridge.vote_id, bridge.Bill_id))
