"""Parquetベースのローカルキャッシュ層。"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.parquet"


def load_cached(name: str) -> pd.DataFrame | None:
    path = cache_path(name)
    if not path.exists():
        return None
    return pd.read_parquet(path)


def save_cached(name: str, df: pd.DataFrame) -> None:
    df.to_parquet(cache_path(name))


def is_fresh(name: str, max_age_hours: int = 12) -> bool:
    path = cache_path(name)
    if not path.exists():
        return False
    age = pd.Timestamp.now() - pd.Timestamp(path.stat().st_mtime, unit="s")
    return age < pd.Timedelta(hours=max_age_hours)
