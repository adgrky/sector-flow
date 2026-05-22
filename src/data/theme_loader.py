"""テーマバスケットから等加重合成指数を生成。

各テーマの構成銘柄を yfinance/Stooq 経由で取得し、
銘柄ごとの初値で正規化した平均(=等加重指数)を「擬似ETF」として扱う。
これによりヒートマップ・RRG・売買代金シェアに統合表示可能になる。
"""
from __future__ import annotations

import pandas as pd

from .stock_loader import get_stocks_data
from .themes import THEMES


def _equal_weight_index(close: pd.DataFrame) -> pd.Series:
    """各銘柄を最初の有効値で正規化し平均(=等加重)。base ≈ 100。"""
    df = close.ffill().dropna(how="all", axis=1)
    if df.empty:
        return pd.Series(dtype=float)
    # 各列ごとの最初の非NaN値を起点に正規化
    first = df.bfill().iloc[0]
    first = first.replace(0, pd.NA)
    norm = df.divide(first) * 100.0
    return norm.mean(axis=1, skipna=True)


def _aggregate_pseudo_volume(close: pd.DataFrame, volume: pd.DataFrame) -> pd.Series:
    """構成銘柄の (close × volume) の合計 ÷ 平均終値 ≈ 出来高代理値。"""
    if close.empty or volume.empty:
        return pd.Series(dtype=float)
    common_cols = [c for c in close.columns if c in volume.columns]
    if not common_cols:
        return pd.Series(dtype=float)
    turnover = (close[common_cols] * volume[common_cols]).sum(axis=1, skipna=True)
    mean_close = close[common_cols].mean(axis=1, skipna=True).replace(0, pd.NA)
    return (turnover / mean_close).dropna()


def get_theme_data(lookback_days: int = 400) -> tuple[pd.DataFrame, pd.DataFrame]:
    """全テーマの (合成終値, 合成出来高) を返す。

    列名 = テーマコード (T01..T04)
    """
    close_frames: dict[str, pd.Series] = {}
    vol_frames: dict[str, pd.Series] = {}
    for theme_code, theme in THEMES.items():
        codes = [c for c, _ in theme["constituents"]]
        try:
            c_df, v_df = get_stocks_data(codes, lookback_days=lookback_days)
        except Exception:
            continue
        if c_df.empty:
            continue
        synthetic_close = _equal_weight_index(c_df)
        if synthetic_close.empty:
            continue
        close_frames[theme_code] = synthetic_close
        pv = _aggregate_pseudo_volume(c_df, v_df)
        if not pv.empty:
            vol_frames[theme_code] = pv

    close_df = pd.DataFrame(close_frames).sort_index() if close_frames else pd.DataFrame()
    vol_df = pd.DataFrame(vol_frames).sort_index() if vol_frames else pd.DataFrame()
    if not close_df.empty:
        close_df.index = pd.to_datetime(close_df.index).tz_localize(None)
    if not vol_df.empty:
        vol_df.index = pd.to_datetime(vol_df.index).tz_localize(None)
    return close_df, vol_df
