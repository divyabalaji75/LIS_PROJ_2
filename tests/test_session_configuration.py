import pandas as pd
import pytest

from lis_common import (
    available_processed_years,
    configured_test_years,
    configured_years,
    environment_flag,
    relabel_comparison_years,
)
from lis_pipeline import get_session_code
from onboard_session import onboarding_environment, validate_year


def test_configured_years_uses_default(monkeypatch):
    monkeypatch.delenv("LIS_ANALYSIS_YEARS", raising=False)
    assert configured_years() == [2025, 2026]


def test_configured_years_accepts_future_sessions(monkeypatch):
    monkeypatch.setenv("LIS_ANALYSIS_YEARS", "2025, 2026, 2027, 2028")
    assert configured_years() == [2025, 2026, 2027, 2028]


@pytest.mark.parametrize(("year", "session_code"), [(2027, "20271"), (2028, "20281")])
def test_future_regular_session_code(year, session_code):
    assert get_session_code(year) == session_code


def test_test_years_are_independent_of_analysis_years(monkeypatch):
    monkeypatch.setenv("LIS_ANALYSIS_YEARS", "2027")
    monkeypatch.setenv("LIS_TEST_YEARS", "2028")
    assert configured_test_years() == [2028]


@pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
def test_environment_flag_accepts_true_values(monkeypatch, value):
    monkeypatch.setenv("LIS_DOWNLOAD", value)
    assert environment_flag("LIS_DOWNLOAD") is True


@pytest.mark.parametrize("value", ["0", "false", "NO", "off", ""])
def test_environment_flag_accepts_false_values(monkeypatch, value):
    monkeypatch.setenv("LIS_DOWNLOAD", value)
    assert environment_flag("LIS_DOWNLOAD", default=True) is False


def test_environment_flag_rejects_ambiguous_value(monkeypatch):
    monkeypatch.setenv("LIS_DOWNLOAD", "sometimes")
    with pytest.raises(ValueError, match="LIS_DOWNLOAD must be one of"):
        environment_flag("LIS_DOWNLOAD")


@pytest.mark.parametrize("year", [2027, 2028])
def test_validate_year_accepts_future_regular_sessions(year):
    validate_year(year)


@pytest.mark.parametrize("year", [1999, 2101])
def test_validate_year_rejects_out_of_range_values(year):
    with pytest.raises(ValueError, match="four-digit session year"):
        validate_year(year)


def test_onboarding_environment_targets_one_year_and_disables_redownload(monkeypatch):
    monkeypatch.setenv("LIS_DOWNLOAD", "1")
    environment = onboarding_environment(2027)
    assert environment["LIS_ANALYSIS_YEARS"] == "2027"
    assert environment["LIS_ANALYSIS_YEAR"] == "2027"
    assert environment["LIS_DOWNLOAD"] == "0"


def test_available_processed_years_discovers_future_sessions(tmp_path):
    for year in (2025, 2027, 2028):
        (tmp_path / f"vote_fact_{year}.csv").touch()
    (tmp_path / "vote_fact_notes.csv").touch()

    assert available_processed_years(tmp_path) == [2025, 2027, 2028]


def test_comparison_columns_are_relabelled_for_future_pair():
    frame = pd.DataFrame(
        {
            "cross_party_pct_2025": [1.0],
            "cross_party_pct_2026": [2.0],
            "member_status": ["2026 only"],
        }
    )

    result = relabel_comparison_years(frame, 2027, 2028)

    assert list(result.columns) == [
        "cross_party_pct_2027",
        "cross_party_pct_2028",
        "member_status",
    ]
    assert result.loc[0, "member_status"] == "2028 only"
