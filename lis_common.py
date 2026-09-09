"""Shared configuration and CSV helpers for the LIS analysis scripts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import pandas as pd


RAW_ROOT = Path("data/raw")
REFERENCE_ROOT = Path("data/reference")
PROCESSED_ROOT = Path("data/processed")
QA_ROOT = Path("data/qa")


def configured_years(default: Iterable[int] = (2025, 2026)) -> list[int]:
    """Return years from LIS_ANALYSIS_YEARS, or the supplied defaults."""
    value = os.environ.get("LIS_ANALYSIS_YEARS", "").strip()
    years = [int(part.strip()) for part in value.split(",") if part.strip()]
    return years or list(default)


def configured_test_years(default: Iterable[int] = (2025, 2026)) -> list[int]:
    """Return full-data validation years independently of analysis settings."""
    value = os.environ.get("LIS_TEST_YEARS", "").strip()
    years = [int(part.strip()) for part in value.split(",") if part.strip()]
    return years or list(default)


def environment_flag(name: str, default: bool = False) -> bool:
    """Read a conventional true/false environment flag."""
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(
        f"{name} must be one of 1/0, true/false, yes/no, or on/off; got {value!r}."
    )


def require_columns(frame: pd.DataFrame, columns: Iterable[str], source: Path) -> None:
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{source} missing required columns: {sorted(missing)}")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return pd.read_csv(path, dtype=str)


def clean_text(values: pd.Series) -> pd.Series:
    return values.fillna("").astype(str).str.strip()


def clean_upper(values: pd.Series) -> pd.Series:
    return clean_text(values).str.upper()


def write_csv(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path
