"""個別銘柄の終値・出来高ローダ。yfinance ベース、Parquet キャッシュ。"""
from __future__ import annotations

import time
from datetime import date

import pandas as pd

from .cache import CACHE_DIR, is_fresh, load_cached, save_cached


def _yf_symbol(code: str) -> str:
    return f"{code}.T"


def _fetch_one(code: str, start: date, end: date) -> pd.DataFrame | None:
    try:
        import yfinance as yf

        df = yf.download(
            _yf_symbol(code),
            start=start.isoformat(),
            end=end.isoformat(),
            progress=False,
            auto_adjust=True,
        )
        if df is None or df.empty:
            return None
        close = df["Close"]
        vol = df.get("Volume")
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        if isinstance(vol, pd.DataFrame):
            vol = vol.iloc[:, 0]
        out = pd.DataFrame({f"{code}_close": close})
        if vol is not None:
            out[f"{code}_volume"] = vol
        return out
    except Exception:
        return None


def get_stocks_data(codes: list[str], lookback_days: int = 400) -> tuple[pd.DataFrame, pd.DataFrame]:
    """指定銘柄群の (終値, 出来高) を取得。銘柄群ごとにキャッシュ。"""
    # キャッシュキーは銘柄リストのハッシュ
    key = "stocks_" + "_".join(sorted(codes))[:80] + f"_{len(codes)}_{lookback_days}d"
    if is_fresh(key, max_age_hours=12):
        cached = load_cached(key)
        if cached is not None and not cached.empty:
            return _split(cached)

    end = pd.Timestamp.now().normalize()
    start = end - pd.Timedelta(days=lookback_days)
    frames = []
    for code in codes:
        df = _fetch_one(code, start.date(), end.date())
        if df is not None and not df.empty:
            frames.append(df)
        time.sleep(0.1)

    if not frames:
        return pd.DataFrame(), pd.DataFrame()

    merged = pd.concat(frames, axis=1).sort_index()
    # 万一の重複コードに対する防御: 同名カラムが複数あれば最初のものを採用
    merged = merged.loc[:, ~merged.columns.duplicated()]
    merged.index = pd.to_datetime(merged.index).tz_localize(None)
    save_cached(key, merged)
    return _split(merged)


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    close_cols = [c for c in df.columns if c.endswith("_close")]
    vol_cols = [c for c in df.columns if c.endswith("_volume")]
    close = df[close_cols].rename(columns=lambda c: c.removesuffix("_close"))
    volume = df[vol_cols].rename(columns=lambda c: c.removesuffix("_volume"))
    return close, volume
