from pathlib import Path

import pandas as pd
import pytest

from lis_common import configured_test_years

YEARS = configured_test_years()
PROCESSED = Path("data/processed")


def load(year):
    path = PROCESSED / f"vote_fact_{year}.csv"
    assert path.exists(), f"Missing required file: {path}"
    return pd.read_csv(path, dtype=str)


@pytest.mark.parametrize("year", YEARS)
def test_vote_fact_contract(year):
    df = load(year)
    required = {"year", "vote_id", "member_id", "MBR_NAME", "MBR_HOU", "party", "vote"}
    assert required <= set(df.columns) and not df.empty
    assert set(pd.to_numeric(df["year"]).astype(int)) == {year}
    for column in required - {"year"}:
        assert df[column].fillna("").str.strip().ne("").all(), f"blank {column}"
    assert set(df["vote"].str.upper()) <= {"Y", "N", "X", "A", "P"}
    assert set(df["party"].str.upper()) <= {"D", "R"}
    assert set(df["MBR_HOU"].str.upper()) <= {"H", "S"}


@pytest.mark.parametrize("year", YEARS)
def test_member_vote_event_is_canonical_grain(year):
    df = load(year)
    assert not df.duplicated(["year", "vote_id", "member_id"]).any()
    assert df.groupby("vote_id")["member_id"].nunique().gt(0).all()


@pytest.mark.parametrize("year", YEARS)
def test_member_identity_is_stable_and_matches_chamber(year):
    df = load(year).assign(member_id=lambda x: x.member_id.str.upper())
    for column in ("MBR_NAME", "party", "MBR_HOU"):
        assert df.groupby("member_id")[column].nunique().le(1).all()
    assert df["member_id"].str[0].eq(df["MBR_HOU"].str.upper()).all()
