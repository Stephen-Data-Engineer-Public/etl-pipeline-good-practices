"""
test_load.py
------------
Tests for the load layer, focusing on idempotency.

The most important property of the load layer is that running it
multiple times produces the same result. These tests verify that
explicitly rather than assuming it.
"""

import pytest
import pandas as pd
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.load import load, query_all, ensure_schema, get_connection


def _sample_df():
    return pd.DataFrame({
        "patient_id": ["1", "2"],
        "nhs_number": ["4857321690", "9876543210"],
        "ward_code": ["W01", "W02"],
        "admission_date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "discharge_date": pd.to_datetime(["2024-01-05", "2024-01-04"]),
        "diagnosis_code": ["J18.9", "I21.0"],
        "consultant_code": ["C001", "C002"],
        "nhs_number_valid": [True, True],
        "is_open_spell": [False, False],
    })


class TestLoad:
    def test_rows_written_on_first_load(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            count = load(_sample_df(), tmp.name)
            assert count == 2

    def test_idempotent_rerun_does_not_duplicate(self):
        """
        Re-running the load with identical data must not increase row count.
        This is the core idempotency guarantee.
        """
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            load(_sample_df(), tmp.name)
            load(_sample_df(), tmp.name)
            result = query_all(tmp.name)
            assert len(result) == 2

    def test_updated_row_is_replaced_not_duplicated(self):
        """
        If a row changes (e.g. discharge date updated), the load must
        update it in place — not append a second row.
        """
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            load(_sample_df(), tmp.name)

            updated = _sample_df().copy()
            updated.loc[0, "discharge_date"] = pd.Timestamp("2024-01-07")
            load(updated, tmp.name)

            result = query_all(tmp.name)
            assert len(result) == 2
            assert result[result["patient_id"] == "1"]["discharge_date"].iloc[0] == "2024-01-07"

    def test_schema_created_if_not_exists(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            conn = get_connection(tmp.name)
            ensure_schema(conn)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            assert "patient_activity" in table_names
