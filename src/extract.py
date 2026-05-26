"""
extract.py
----------
Responsible for reading raw source data into a pandas DataFrame.

Design decision: extraction is kept deliberately thin — no transformation
logic lives here. This makes the source easy to swap (CSV today, SQL
tomorrow) without touching the transform or load layers.
"""

import pandas as pd
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_csv(filepath: str | Path) -> pd.DataFrame:
    """
    Read a CSV file and return a raw DataFrame.

    Parameters
    ----------
    filepath : str or Path
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame
        Raw data exactly as it appears in the source.

    Raises
    ------
    FileNotFoundError
        If the file does not exist at the given path.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    df = pd.read_csv(path, dtype=str)  # read all as str — types applied in transform
    logger.info(f"Extracted {len(df)} rows from {path.name}")
    return df
