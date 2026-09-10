from pathlib import Path

import pandas as pd
import pytest

from lis_common import configured_test_years

YEARS = configured_test_years()


def read(path):
    assert path.exists(), f"Missing required file: {path}"
    return pd.read_csv(path, dtype=str).fillna("")


@pytest.mark.parametrize("year", YEARS)
def test_party_reference_contract(year):
    party = read(Path("data/reference") / f"party_{year}.csv")
    assert {"member_id", "member", "party"} <= set(party.columns) and not party.empty
    assert party[["member_id", "member", "party"]].apply(lambda s: s.str.strip().ne("").all()).all()
    assert not party["member_id"].duplicated().any()
    assert set(party["party"].str.upper()) <= {"D", "R"}
    assert party["member_id"].str.upper().str[0].isin(["H", "S"]).all()


@pytest.mark.parametrize("year", YEARS)
def test_all_voting_members_join_to_exact_party_and_name(year):
    votes = read(Path("data/processed") / f"vote_fact_{year}.csv")
    party = read(Path("data/reference") / f"party_{year}.csv")
    joined = votes.merge(party, on="member_id", how="left", validate="many_to_one", suffixes=("_vote", "_ref"))
    assert joined["party_ref"].ne("").all()
    assert joined["party_vote"].str.upper().eq(joined["party_ref"].str.upper()).all()
    assert joined["MBR_NAME"].str.strip().str.casefold().eq(joined["member"].str.strip().str.casefold()).all()


@pytest.mark.parametrize("year", YEARS)
def test_vote_member_has_one_party_and_chamber(year):
    votes = read(Path("data/processed") / f"vote_fact_{year}.csv")
    assert votes.groupby("member_id")["party"].nunique().le(1).all()
    assert votes.groupby("member_id")["MBR_HOU"].nunique().le(1).all()
