from pathlib import Path
import csv

import pandas as pd
import pytest

from lis_common import configured_test_years
from lis_pipeline import SUMMARY_TYPE_PRIORITY, strip_summary_html

YEARS = configured_test_years()
RAW, PROCESSED, REFERENCE = Path("data/raw"), Path("data/processed"), Path("data/reference")


def read(path):
    assert path.exists(), f"Missing required file: {path}"
    return pd.read_csv(path, dtype=str).fillna("")


def norm(series, upper=False):
    result = series.fillna("").astype(str).str.strip()
    return result.str.upper() if upper else result


def parse_raw_votes(year):
    rows = []
    with (RAW / str(year) / "VOTE.CSV").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 3 or not row[0].strip():
                continue
            for index in range(1, len(row) - 1, 2):
                member, vote = row[index].strip().upper(), row[index + 1].strip().upper()
                if member and vote:
                    rows.append((row[0].strip(), member, vote))
    return rows


@pytest.mark.parametrize("year", YEARS)
def test_all_raw_vote_records_reconcile_exactly(year):
    raw = parse_raw_votes(year)
    processed = read(PROCESSED / f"vote_fact_{year}.csv")
    actual = list(zip(norm(processed.vote_id), norm(processed.member_id, True), norm(processed.vote, True)))
    assert len(actual) == len(raw)
    assert sorted(actual) == sorted(raw)


@pytest.mark.parametrize("year", YEARS)
def test_bill_lookup_reconciles_to_raw_lis_bills(year):
    raw = read(RAW / str(year) / "BILLS.CSV")
    processed = read(PROCESSED / f"bill_lookup_{year}.csv")
    expected = set(zip(norm(raw.Bill_id, True), norm(raw.Bill_description)))
    actual = set(zip(norm(processed.Bill_id, True), norm(processed.Bill_description)))
    assert actual == expected


@pytest.mark.parametrize("year", YEARS)
def test_official_subjects_and_parent_rollups_reconcile_to_raw_lis(year):
    subjects = read(RAW / str(year) / "CIBillSubjects.csv")
    hierarchy = read(RAW / str(year) / "CIParentChildSubjects.csv")
    official = read(PROCESSED / f"official_lis_subjects_{year}.csv")
    expected = subjects.merge(hierarchy[["C_Subject_Id", "Parent_Subject"]].drop_duplicates("C_Subject_Id"),
                              left_on="Subject_Id", right_on="C_Subject_Id", how="left", validate="many_to_one").fillna("")
    expected["topic_name"] = expected.Parent_Subject.where(expected.Parent_Subject.ne(""), expected.Subject_Name)
    expected_rows = set(zip(norm(expected.Bill_Number, True), norm(expected.Subject_Name), norm(expected.Parent_Subject), norm(expected.topic_name)))
    actual_rows = set(zip(norm(official.Bill_id, True), norm(official.lis_subject_name), norm(official.lis_parent_subject), norm(official.topic_name)))
    assert actual_rows == expected_rows


@pytest.mark.parametrize("year", YEARS)
def test_selected_summaries_are_best_available_raw_lis_text(year):
    raw = read(RAW / str(year) / "Summaries.csv")
    selected = read(PROCESSED / f"bill_summary_lookup_{year}.csv")
    raw["priority"] = norm(raw.SUMMARY_TYPE, True).map(SUMMARY_TYPE_PRIORITY)
    eligible = raw[raw.priority.notna()].copy()
    best = eligible.groupby(norm(eligible.SUM_BILNO, True)).priority.transform("min")
    eligible = eligible[eligible.priority.eq(best)]
    allowed = set(zip(norm(eligible.SUM_BILNO, True), norm(eligible.SUMMARY_DOCID)))
    actual = set(zip(norm(selected.Bill_id, True), norm(selected.summary_doc_id)))
    assert actual <= allowed
    raw_text = {(bill, doc): strip_summary_html(text) for bill, doc, text in zip(norm(raw.SUM_BILNO, True), norm(raw.SUMMARY_DOCID), raw.SUMMARY_TEXT)}
    assert all(text == raw_text[(bill, doc)] for bill, doc, text in zip(norm(selected.Bill_id, True), norm(selected.summary_doc_id), norm(selected.summary_text)))


@pytest.mark.parametrize("year", YEARS)
def test_vote_bill_bridge_rows_reconcile_to_raw_history(year):
    history = read(RAW / str(year) / "HISTORY.CSV")
    bridge = read(PROCESSED / f"vote_bill_bridge_{year}.csv")
    raw_rows = set(zip(norm(history.History_refid), norm(history.Bill_id, True), norm(history.History_date), norm(history.History_description)))
    actual = set(zip(norm(bridge.vote_id), norm(bridge.Bill_id, True), norm(bridge.History_date), norm(bridge.History_description)))
    assert actual <= raw_rows
    assert set(norm(bridge.vote_id)) <= set(vote_id for vote_id, _, _ in parse_raw_votes(year))


@pytest.mark.parametrize("year", YEARS)
def test_member_names_and_parties_have_official_or_documented_backing(year):
    votes = read(PROCESSED / f"vote_fact_{year}.csv")
    members = read(RAW / str(year) / "Members.csv")
    party = read(REFERENCE / f"party_{year}.csv")
    voting_ids = set(norm(votes.member_id, True))
    assert voting_ids <= set(norm(members.MBR_MBRNO, True)) | set(norm(party.member_id, True))
    joined = votes[["member_id", "party"]].drop_duplicates().merge(party[["member_id", "party"]], on="member_id", how="left", suffixes=("_vote", "_reference"), validate="one_to_one")
    assert joined.party_vote.eq(joined.party_reference).all()
