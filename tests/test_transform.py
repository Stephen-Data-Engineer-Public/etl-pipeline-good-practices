"""
test_transform.py
-----------------
Unit tests for the transform layer.

Each test is small and tests exactly one behaviour. This makes failures
easy to diagnose and ensures the test suite stays fast.
"""

import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.transform import (
    validate_nhs_number,
    cast_dates,
    flag_missing_nhs_numbers,
    flag_open_spells,
    deduplicate,
    transform,
    ValidationReport,
)


class TestValidateNhsNumber:
    def test_valid_10_digit_number(self):
        assert validate_nhs_number("4857321690") is True

    def test_too_short(self):
        assert validate_nhs_number("123456789") is False

    def test_too_long(self):
        assert validate_nhs_number("12345678901") is False

    def test_none_value(self):
        assert validate_nhs_number(None) is False

    def test_empty_string(self):
        assert validate_nhs_number("") is False

    def test_contains_letters(self):
        assert validate_nhs_number("485ABC1690") is False

    def test_nan_value(self):
        assert validate_nhs_number(float("nan")) is False


class TestCastDates:
    def test_valid_date_is_cast(self):
        df = pd.DataFrame({"admission_date": ["2024-01-01"]})
        result = cast_dates(df, ["admission_date"])
        assert pd.api.types.is_datetime64_any_dtype(result["admission_date"])

    def test_invalid_date_becomes_nat(self):
        df = pd.DataFrame({"admission_date": ["not-a-date"]})
        result = cast_dates(df, ["admission_date"])
        assert pd.isna(result["admission_date"].iloc[0])

    def test_missing_column_is_ignored(self):
        df = pd.DataFrame({"other_col": ["2024-01-01"]})
        result = cast_dates(df, ["admission_date"])
        assert "admission_date" not in result.columns


class TestFlagMissingNhsNumbers:
    def test_valid_nhs_number_flagged_true(self):
        df = pd.DataFrame({"nhs_number": ["4857321690"]})
        result = flag_missing_nhs_numbers(df)
        assert bool(result["nhs_number_valid"].iloc[0]) is True

    def test_missing_nhs_number_flagged_false(self):
        df = pd.DataFrame({"nhs_number": [None]})
        result = flag_missing_nhs_numbers(df)
        assert bool(result["nhs_number_valid"].iloc[0]) is False


class TestFlagOpenSpells:
    def test_open_spell_flagged(self):
        df = pd.DataFrame({"discharge_date": [pd.NaT]})
        result = flag_open_spells(df)
        assert bool(result["is_open_spell"].iloc[0]) is True

    def test_closed_spell_not_flagged(self):
        df = pd.DataFrame({"discharge_date": [pd.Timestamp("2024-01-05")]})
        result = flag_open_spells(df)
        assert bool(result["is_open_spell"].iloc[0]) is False


class TestDeduplicate:
    def test_duplicate_removed(self):
        df = pd.DataFrame({
            "patient_id": ["1", "1"],
            "admission_date": ["2024-01-01", "2024-01-01"],
            "ward_code": ["W01", "W01"],
        })
        result, count = deduplicate(df, subset=["patient_id", "admission_date"])
        assert len(result) == 1
        assert count == 1

    def test_no_duplicates_unchanged(self):
        df = pd.DataFrame({
            "patient_id": ["1", "2"],
            "admission_date": ["2024-01-01", "2024-01-02"],
        })
        result, count = deduplicate(df, subset=["patient_id", "admission_date"])
        assert len(result) == 2
        assert count == 0


class TestTransformIntegration:
    def _make_df(self):
        return pd.DataFrame({
            "patient_id": ["1", "2", "3"],
            "nhs_number": ["4857321690", None, "INVALID"],
            "ward_code": ["W01", "W02", "W03"],
            "admission_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "discharge_date": ["2024-01-05", None, "2024-01-06"],
            "diagnosis_code": ["J18.9", "I21.0", "K80.2"],
            "consultant_code": ["C001", "C002", "C003"],
        })

    def test_returns_dataframe_and_report(self):
        df, report = transform(self._make_df())
        assert isinstance(df, pd.DataFrame)
        assert isinstance(report, ValidationReport)

    def test_report_counts_missing_nhs(self):
        df, report = transform(self._make_df())
        assert report.missing_nhs_numbers == 2  # None and "INVALID"

    def test_report_counts_open_spells(self):
        df, report = transform(self._make_df())
        assert report.missing_discharge_dates == 1

    def test_null_threshold_detection(self):
        df, report = transform(self._make_df())
        assert bool(report.exceeds_null_threshold(threshold=0.10)) is True

    def test_null_threshold_not_exceeded_on_clean_data(self):
        clean_df = pd.DataFrame({
            "patient_id": ["1"],
            "nhs_number": ["4857321690"],
            "ward_code": ["W01"],
            "admission_date": ["2024-01-01"],
            "discharge_date": ["2024-01-05"],
            "diagnosis_code": ["J18.9"],
            "consultant_code": ["C001"],
        })
        df, report = transform(clean_df)
        assert bool(report.exceeds_null_threshold(threshold=0.10)) is False
