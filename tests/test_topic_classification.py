from pathlib import Path

import pandas as pd
import pytest

from lis_common import configured_test_years

YEARS = configured_test_years()
ROOT = Path("data/processed")
CLASSES = {"Official LIS subject", "Derived from LIS bill summary", "Derived from LIS bill description", "Unclassified"}
FILES = {
    "official_lis_subjects": "Official LIS subject",
    "derived_from_lis_bill_summary": "Derived from LIS bill summary",
    "derived_from_lis_bill_description": "Derived from LIS bill description",
    "unclassified_bills": "Unclassified",
}


def load(name, year):
    path = ROOT / f"{name}_{year}.csv"
    assert path.exists(), f"Missing required file: {path}"
    return pd.read_csv(path, dtype=str).fillna("")


@pytest.mark.parametrize("year", YEARS)
def test_combined_topic_lookup_contract(year):
    topics = load("bill_topic_lookup", year)
    required = {"Bill_id", "topic_name", "classification", "lis_subject_name", "lis_parent_subject",
                "source_file", "source_text_used", "rule_derived"}
    assert required <= set(topics.columns) and not topics.empty
    assert topics[["Bill_id", "topic_name", "classification"]].apply(lambda s: s.str.strip().ne("").all()).all()
    assert set(topics.classification) <= CLASSES
    assert not topics.duplicated().any()


@pytest.mark.parametrize("year", YEARS)
def test_every_known_bill_has_exactly_one_provenance_tier(year):
    bills = load("bill_lookup", year)
    topics = load("bill_topic_lookup", year)
    assert not bills.Bill_id.duplicated().any()
    assert set(topics.Bill_id) == set(bills.Bill_id)
    assert topics.groupby("Bill_id")["classification"].nunique().eq(1).all()


@pytest.mark.parametrize("year", YEARS)
def test_provenance_files_are_exact_projections(year):
    combined = load("bill_topic_lookup", year)
    key = ["Bill_id", "topic_name", "classification"]
    for name, classification in FILES.items():
        separate = load(name, year)
        assert set(separate.classification) == {classification}
        expected = combined.loc[combined.classification.eq(classification), key]
        assert set(map(tuple, separate[key].to_numpy())) == set(map(tuple, expected.to_numpy()))


@pytest.mark.parametrize("year", YEARS)
def test_official_subject_evidence_and_parent_rollup(year):
    official = load("official_lis_subjects", year)
    assert official.lis_subject_name.str.strip().ne("").all()
    assert official.source_file.eq("CIBillSubjects.csv").all()
    assert official.source_text_used.eq(official.lis_subject_name).all()
    assert official.rule_derived.str.lower().isin(["false", "0"]).all()
    expected = official.lis_parent_subject.where(official.lis_parent_subject.ne(""), official.lis_subject_name)
    assert official.topic_name.eq(expected).all()


@pytest.mark.parametrize("year", YEARS)
def test_derived_evidence_contract_and_official_priority(year):
    combined = load("bill_topic_lookup", year)
    official_bills = set(combined.loc[combined.classification.eq("Official LIS subject"), "Bill_id"])
    for name, classification, source in (
        ("derived_from_lis_bill_summary", "Derived from LIS bill summary", "Summaries.csv"),
        ("derived_from_lis_bill_description", "Derived from LIS bill description", "BILLS.CSV"),
    ):
        derived = load(name, year)
        assert set(derived.Bill_id).isdisjoint(official_bills)
        assert derived.source_file.eq(source).all()
        assert derived.source_text_used.str.strip().ne("").all()
        assert derived.rule_derived.str.lower().isin(["true", "1"]).all()
        assert derived.lis_subject_name.eq("").all() and derived.lis_parent_subject.eq("").all()


@pytest.mark.parametrize("year", YEARS)
def test_summary_precedes_description_and_unclassified(year):
    summary = set(load("derived_from_lis_bill_summary", year).Bill_id)
    description = set(load("derived_from_lis_bill_description", year).Bill_id)
    unclassified = load("unclassified_bills", year)
    assert summary.isdisjoint(description)
    assert summary.isdisjoint(set(unclassified.Bill_id))
    assert description.isdisjoint(set(unclassified.Bill_id))
    assert unclassified.groupby("Bill_id").size().eq(1).all()
    assert unclassified.topic_name.eq("Unclassified").all()


@pytest.mark.parametrize("year", YEARS)
def test_topic_coverage_reconciles_to_bill_partition(year):
    coverage = load("topic_coverage", year)
    topics = load("bill_topic_lookup", year)[["Bill_id", "classification"]].drop_duplicates()
    expected = topics.groupby("classification").Bill_id.nunique().to_dict()
    actual = pd.to_numeric(coverage.bill_count).groupby(coverage.classification).sum().to_dict()
    assert actual == expected
    assert coverage.classification.isin(CLASSES).all()
    assert pd.to_numeric(coverage.bill_percentage).sum() == pytest.approx(100.0, abs=0.02)
