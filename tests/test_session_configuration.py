import pandas as pd
import pytest

from lis_common import available_processed_years, configured_test_years, configured_years, environment_flag, relabel_comparison_years
from lis_pipeline import get_session_code
from onboard_session import onboarding_environment, validate_year


def test_year_configuration_supports_future_sessions(monkeypatch):
    monkeypatch.delenv("LIS_ANALYSIS_YEARS", raising=False)
    assert configured_years() == [2025, 2026]
    monkeypatch.setenv("LIS_ANALYSIS_YEARS", "2025, 2027, 2028")
    monkeypatch.setenv("LIS_TEST_YEARS", "2028")
    assert configured_years() == [2025, 2027, 2028]
    assert configured_test_years() == [2028]
    assert [get_session_code(y) for y in (2027, 2028)] == ["20271", "20281"]


@pytest.mark.parametrize(("value", "expected"), [("YES", True), ("on", True), ("0", False), ("false", False), ("", False)])
def test_environment_flag_parses_explicit_boolean_values(monkeypatch, value, expected):
    monkeypatch.setenv("LIS_DOWNLOAD", value)
    assert environment_flag("LIS_DOWNLOAD", default=True) is expected


def test_environment_flag_rejects_ambiguous_value(monkeypatch):
    monkeypatch.setenv("LIS_DOWNLOAD", "sometimes")
    with pytest.raises(ValueError, match="LIS_DOWNLOAD must be one of"):
        environment_flag("LIS_DOWNLOAD")


def test_onboarding_accepts_supported_years_and_disables_redownload():
    for year in (2027, 2028):
        validate_year(year)
    with pytest.raises(ValueError, match="four-digit session year"):
        validate_year(1999)
    environment = onboarding_environment(2027)
    assert {key: environment[key] for key in ("LIS_ANALYSIS_YEARS", "LIS_ANALYSIS_YEAR", "LIS_DOWNLOAD")} == {
        "LIS_ANALYSIS_YEARS": "2027", "LIS_ANALYSIS_YEAR": "2027", "LIS_DOWNLOAD": "0"
    }


def test_processed_year_discovery_ignores_unrelated_files(tmp_path):
    for name in ("vote_fact_2025.csv", "vote_fact_2028.csv", "vote_fact_notes.csv"):
        (tmp_path / name).touch()
    assert available_processed_years(tmp_path) == [2025, 2028]


def test_comparison_schema_and_status_are_relabelled():
    source = pd.DataFrame({"cross_party_pct_2025": [1.0], "cross_party_pct_2026": [2.0], "member_status": ["2026 only"]})
    result = relabel_comparison_years(source, 2027, 2028)
    assert list(result.columns) == ["cross_party_pct_2027", "cross_party_pct_2028", "member_status"]
    assert result.loc[0, "member_status"] == "2028 only"
