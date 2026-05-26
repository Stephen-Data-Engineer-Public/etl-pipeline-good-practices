"""
load.py
-------
Handles writing the transformed DataFrame to a SQLite database.

Design decision: idempotent upsert via INSERT OR REPLACE.
The pipeline can be re-run any number of times safely — the result
is always identical. This is enforced at the schema level by declaring
(patient_id, admission_date) as the PRIMARY KEY, not just at the
application level.

Why SQLite?
-----------
SQLite is used here for portability — no server required, works in
Codespaces and CI without any setup. In a production NHS context this
would be SQL Server with a proper MERGE statement.
"""

import sqlite3
import pandas as pd
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS patient_activity (
    patient_id         TEXT,
    nhs_number         TEXT,
    ward_code          TEXT,
    admission_date     TEXT,
    discharge_date     TEXT,
    diagnosis_code     TEXT,
    consultant_code    TEXT,
    nhs_number_valid   INTEGER,
    is_open_spell      INTEGER,
    loaded_at          TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (patient_id, admission_date)
);
"""

UPSERT_SQL = """
INSERT OR REPLACE INTO patient_activity (
    patient_id, nhs_number, ward_code, admission_date,
    discharge_date, diagnosis_code, consultant_code,
    nhs_number_valid, is_open_spell
) VALUES (
    :patient_id, :nhs_number, :ward_code, :admission_date,
    :discharge_date, :diagnosis_code, :consultant_code,
    :nhs_number_valid, :is_open_spell
);
"""


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Return a SQLite connection, creating the file if it does not exist."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the target table if it does not already exist."""
    conn.execute(DDL)
    conn.commit()


def load(df: pd.DataFrame, db_path: str | Path) -> int:
    """
    Upsert rows into the patient_activity table.

    Parameters
    ----------
    df : pd.DataFrame
        Transformed DataFrame.
    db_path : str or Path
        Path to the SQLite database file.

    Returns
    -------
    int
        Number of rows written.

    Design decision: we cast datetimes back to ISO strings before writing.
    SQLite stores everything as text; keeping a consistent format
    (YYYY-MM-DD) makes downstream queries predictable.
    """
    conn = get_connection(db_path)
    ensure_schema(conn)

    records = df.copy()
    for col in ["admission_date", "discharge_date"]:
        if col in records.columns:
            records[col] = records[col].dt.strftime("%Y-%m-%d").where(
                records[col].notna(), other=None
            )

    records["nhs_number_valid"] = records["nhs_number_valid"].astype(int)
    records["is_open_spell"] = records["is_open_spell"].astype(int)

    rows = records.to_dict(orient="records")
    conn.executemany(UPSERT_SQL, rows)
    conn.commit()

    row_count = conn.execute("SELECT COUNT(*) FROM patient_activity").fetchone()[0]
    logger.info(f"Load complete. Table now contains {row_count} rows.")
    conn.close()
    return len(rows)


def query_all(db_path: str | Path) -> pd.DataFrame:
    """Convenience function: return the full target table as a DataFrame."""
    conn = get_connection(db_path)
    df = pd.read_sql("SELECT * FROM patient_activity", conn)
    conn.close()
    return df
