from __future__ import annotations

from pathlib import Path

import pandas as pd

TRAINING_COLUMNS = ["incident_number", "short_description", "group", "category"]
DAILY_COLUMNS = ["incident_number", "short_description"]


def load_training_incidents(path: str | Path) -> pd.DataFrame:
    df = _read_excel(path, TRAINING_COLUMNS)
    df = df.dropna(subset=["short_description", "group", "category"]).copy()
    df["short_description"] = df["short_description"].astype(str)
    df["group"] = df["group"].astype(str)
    df["category"] = df["category"].astype(str)
    df["label"] = df["group"] + "||" + df["category"]
    return df


def load_daily_incidents(path: str | Path) -> pd.DataFrame:
    df = _read_excel(path, DAILY_COLUMNS)
    df = df.dropna(subset=["short_description"]).copy()
    df["short_description"] = df["short_description"].astype(str)
    return df


def split_label(label: str) -> tuple[str, str]:
    group, category = label.split("||", maxsplit=1)
    return group, category


def _read_excel(path: str | Path, required_columns: list[str]) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    df = pd.read_excel(file_path)
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(
            f"{file_path} is missing required columns: {', '.join(missing)}"
        )
    return df[required_columns].copy()
