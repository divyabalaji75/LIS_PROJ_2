"""Download, validate, and process one new Virginia LIS regular session."""

from __future__ import annotations

import argparse
from datetime import datetime
from email.utils import parsedate_to_datetime
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import requests

from lis_common import available_processed_years
from lis_pipeline import BASE_URL, FILES, RAW_ROOT, download_file, get_session_code


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_TESTS = [
    "tests/test_vote_fact.py",
    "tests/test_vote_bill_bridge.py",
    "tests/test_party_join.py",
    "tests/test_reconciliation.py",
    "tests/test_source_sample.py",
    "tests/test_topic_classification.py",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Onboard one regular-session year without copying scripts or changing "
            "the established analytical rules."
        )
    )
    parser.add_argument("year", type=int, help="Four-digit regular-session year, such as 2027.")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Use already retained files under data/raw/<year>.",
    )
    parser.add_argument(
        "--skip-party",
        action="store_true",
        help="Use an already validated data/reference/party_<year>.csv.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip the new year's full-data tests (not recommended for a final run).",
    )
    parser.add_argument(
        "--compare-with",
        type=int,
        help=(
            "Build a comparison against this year. If omitted, the latest earlier "
            "processed regular session is selected automatically."
        ),
    )
    return parser.parse_args()


def validate_year(year: int) -> None:
    if year < 2000 or year > 2100:
        raise ValueError(f"Expected a four-digit session year; got {year}.")


def run_python(label: str, arguments: list[str], environment: dict[str, str]) -> None:
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    subprocess.run(
        [sys.executable, *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
    )


def download_sources(year: int) -> None:
    failures: list[str] = []
    print(f"\nDownloading official LIS files for {year} ({get_session_code(year)})...")
    for filename in FILES:
        try:
            path = download_file(year, filename)
            print(f"  OK {filename}: {path.stat().st_size:,} bytes")
        except Exception as error:  # report every source failure together
            failures.append(f"{filename}: {error}")
            print(f"  FAILED {filename}: {error}")
    if failures:
        raise RuntimeError("One or more required LIS downloads failed:\n" + "\n".join(failures))


def remote_modified(year: int, filename: str) -> datetime | None:
    url = f"{BASE_URL}/{get_session_code(year)}/{filename}"
    try:
        response = requests.head(url, timeout=30)
        response.raise_for_status()
        value = response.headers.get("Last-Modified", "")
        return parsedate_to_datetime(value) if value else None
    except (requests.RequestException, TypeError, ValueError):
        return None


def inspect_sources(year: int) -> list[str]:
    year_root = RAW_ROOT / str(year)
    missing = [filename for filename in FILES if not (year_root / filename).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing required {year} LIS files under {year_root}: {', '.join(missing)}"
        )

    rows: list[dict[str, object]] = []
    modified: dict[str, datetime | None] = {}
    for filename in FILES:
        path = year_root / filename
        try:
            row_count = len(pd.read_csv(path, dtype=str))
        except Exception as error:
            raise ValueError(f"Could not parse {path}: {error}") from error
        modified[filename] = remote_modified(year, filename)
        rows.append(
            {
                "file": filename,
                "rows": row_count,
                "bytes": path.stat().st_size,
                "LIS last modified": (
                    modified[filename].date().isoformat() if modified[filename] else "unavailable"
                ),
            }
        )

    print(f"\n{year} source inventory")
    print(pd.DataFrame(rows).to_string(index=False))

    bills = pd.read_csv(year_root / "BILLS.CSV", dtype=str)
    subjects = pd.read_csv(year_root / "CIBillSubjects.csv", dtype=str)
    bill_count = bills["Bill_id"].dropna().str.strip().nunique()
    official_bill_count = subjects["Bill_Number"].dropna().str.strip().nunique()
    subject_coverage = 100 * official_bill_count / bill_count if bill_count else 0.0

    warnings: list[str] = []
    if subject_coverage < 5:
        warnings.append(
            f"CIBillSubjects.csv covers only {official_bill_count:,} of {bill_count:,} bills "
            f"({subject_coverage:.2f}%). Confirm that LIS has published a complete export."
        )
    bill_modified = modified.get("BILLS.CSV")
    subject_modified = modified.get("CIBillSubjects.csv")
    if bill_modified and subject_modified and (bill_modified - subject_modified).days > 30:
        warnings.append(
            "CIBillSubjects.csv is more than 30 days older than BILLS.CSV "
            f"({subject_modified.date()} versus {bill_modified.date()})."
        )

    if warnings:
        print("\nSOURCE READINESS WARNINGS")
        for warning in warnings:
            print(f"  WARNING: {warning}")
    else:
        print("\nNo source freshness or sparse-subject warning was triggered.")
    return warnings


def onboarding_environment(year: int) -> dict[str, str]:
    environment = os.environ.copy()
    environment["LIS_ANALYSIS_YEARS"] = str(year)
    environment["LIS_ANALYSIS_YEAR"] = str(year)
    environment["LIS_DOWNLOAD"] = "0"
    return environment


def previous_processed_year(year: int) -> int | None:
    """Return the latest retained regular session before the onboarding year."""
    earlier_years = [candidate for candidate in available_processed_years() if candidate < year]
    return max(earlier_years) if earlier_years else None


def main() -> None:
    args = parse_args()
    validate_year(args.year)
    os.chdir(PROJECT_ROOT)

    if not args.skip_download:
        download_sources(args.year)
    warnings = inspect_sources(args.year)

    environment = onboarding_environment(args.year)
    if not args.skip_party:
        run_python("Build and validate party reference", ["member_party.py"], environment)
    elif not (PROJECT_ROOT / "data" / "reference" / f"party_{args.year}.csv").exists():
        raise FileNotFoundError(
            f"--skip-party was used, but data/reference/party_{args.year}.csv does not exist."
        )

    run_python("Build canonical and analytical outputs", ["lis_pipeline.py"], environment)
    run_python("Build consolidated topic audit", ["topic_validation_audit.py"], environment)

    if not args.skip_tests:
        test_environment = os.environ.copy()
        test_environment["LIS_TEST_YEARS"] = str(args.year)
        test_environment.pop("LIS_ANALYSIS_YEARS", None)
        test_environment.pop("LIS_ANALYSIS_YEAR", None)
        test_environment["LIS_DOWNLOAD"] = "0"
        run_python(
            f"Run full-data validations for {args.year}",
            ["-m", "pytest", "-q", *DATA_TESTS],
            test_environment,
        )

    comparison_year = (
        args.compare_with if args.compare_with is not None else previous_processed_year(args.year)
    )
    if comparison_year is not None:
        validate_year(comparison_year)
        comparison_environment = os.environ.copy()
        comparison_environment["LIS_ANALYSIS_YEARS"] = f"{comparison_year},{args.year}"
        comparison_environment["LIS_DOWNLOAD"] = "0"
        run_python(
            "Build topic behavior for the comparison pair",
            ["topic_stance_analysis.py"],
            comparison_environment,
        )
        run_python(
            "Build year-over-year comparison",
            ["year_over_year_analysis.py"],
            comparison_environment,
        )

    print(f"\n{'=' * 70}\nSESSION ONBOARDING COMPLETE\n{'=' * 70}")
    print(f"Processed year: {args.year}")
    print(
        "Year-over-year comparison: "
        + (f"{comparison_year} -> {args.year}" if comparison_year else "not available")
    )
    print(f"Source readiness warnings: {len(warnings)}")
    print(
        "Dashboard command:\n"
        f'$env:LIS_ANALYSIS_YEARS = "2025,2026,{args.year}"; .\\run_dashboard.ps1'
    )
    if warnings:
        print("Resolve or document the warnings before treating the session as publication-ready.")


if __name__ == "__main__":
    main()
