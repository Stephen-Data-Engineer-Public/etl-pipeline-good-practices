"""
transform.py
------------
All business logic and data quality rules live here.

Design decisions:
- Each rule is a small, independently testable function.
- A ValidationReport is returned alongside the clean DataFrame so the
  caller can decide how to handle issues (log, alert, halt) rather than
  transform.py making that call itself.
- No side effects — functions are pure: same input always produces the
  same output, making them safe to unit test and safe to re-run.
"""

import pandas as pd
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

NHS_NUMBER_LENGTH = 10


@dataclass
class ValidationReport:
    """Summary of data quality findings after transformation."""
    total_rows: int = 0
    missing_nhs_numbers: int = 0
    invalid_nhs_numbers: int = 0
    missing_discharge_dates: int = 0
    duplicate_admissions: int = 0
    rows_passed: int = 0
    issues: list = field(default_factory=list)

    @property
    def null_nhs_rate(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return round(self.missing_nhs_numbers / self.total_rows, 4)

    def exceeds_null_threshold(self, threshold: float = 0.10) -> bool:
        """
        Returns True if the NULL NHS number rate exceeds the threshold.

        Design decision: threshold is configurable so it can be tightened
        per environment (e.g. stricter in production than in UAT).
        """
        return self.null_nhs_rate > threshold


def validate_nhs_number(value: str | None) -> bool:
    """
    Basic structural validation: NHS numbers must be exactly 10 digits.

    Note: full Modulus 11 check is not implemented here — this is a
    structural guard, not a clinical validation service.
    """
    if pd.isna(value) or not str(value).strip():
        return False
    return str(value).strip().isdigit() and len(str(value).strip()) == NHS_NUMBER_LENGTH


def cast_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Cast string columns to datetime, coercing unparseable values to NaT.
    """
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def flag_missing_nhs_numbers(df: pd.DataFrame) -> pd.DataFrame:
    """Add a boolean column marking rows with missing or invalid NHS numbers."""
    df = df.copy()
    df["nhs_number_valid"] = df["nhs_number"].apply(validate_nhs_number)
    return df


def flag_open_spells(df: pd.DataFrame) -> pd.DataFrame:
    """Add a boolean column marking rows with no discharge date (open spells)."""
    df = df.copy()
    df["is_open_spell"] = df["discharge_date"].isna()
    return df


def deduplicate(df: pd.DataFrame, subset: list[str]) -> tuple[pd.DataFrame, int]:
    """
    Remove duplicate rows based on a natural key subset.

    Returns the deduplicated DataFrame and a count of rows removed.

    Design decision: keep='first' retains the earliest occurrence of a
    duplicate rather than the latest, as we treat the first ingestion as
    the source of truth. This is consistent with idempotent reload behaviour.
    """
    before = len(df)
    df = df.drop_duplicates(subset=subset, keep="first")
    removed = before - len(df)
    if removed > 0:
        logger.warning(f"Removed {removed} duplicate rows on key: {subset}")
    return df, removed


def transform(df: pd.DataFrame) -> tuple[pd.DataFrame, ValidationReport]:
    """
    Apply all transformation and validation rules.

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame from the extract layer.

    Returns
    -------
    tuple[pd.DataFrame, ValidationReport]
        Cleaned DataFrame and a ValidationReport describing data quality.
    """
    report = ValidationReport(total_rows=len(df))
    df = df.copy()

    # 1. Cast date columns
    df = cast_dates(df, ["admission_date", "discharge_date"])

    # 2. Flag NHS number quality
    df = flag_missing_nhs_numbers(df)
    report.missing_nhs_numbers = df["nhs_number_valid"].eq(False).sum()
    report.invalid_nhs_numbers = (
        df["nhs_number"].notna() & df["nhs_number_valid"].eq(False)
    ).sum()

    if report.missing_nhs_numbers > 0:
        report.issues.append(
            f"{report.missing_nhs_numbers} rows have missing or invalid NHS numbers "
            f"({report.null_nhs_rate:.1%} of total)"
        )

    # 3. Flag open spells
    df = flag_open_spells(df)
    report.missing_discharge_dates = df["is_open_spell"].sum()
    if report.missing_discharge_dates > 0:
        report.issues.append(
            f"{report.missing_discharge_dates} open spells (no discharge date)"
        )

    # 4. Deduplicate on natural key
    df, dupes_removed = deduplicate(df, subset=["patient_id", "admission_date"])
    report.duplicate_admissions = dupes_removed
    if dupes_removed > 0:
        report.issues.append(f"{dupes_removed} duplicate admissions removed")

    report.rows_passed = len(df)
    logger.info(
        f"Transform complete: {report.rows_passed} rows passed, "
        f"{len(report.issues)} issue(s) found"
    )
    return df, report
