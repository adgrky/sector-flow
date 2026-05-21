"""売買代金シェアの計算。

JPX公式CSVが入手できないため、各セクターETFの「終値×出来高」を
擬似売買代金として用い、セクター別シェア(%)を時系列で算出する。
ETFの実弾流入を捉える指標として機能する。
"""
from __future__ import annotations

import pandas as pd


def compute_turnover(close: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    """終値×出来高 を擬似売買代金として返す。"""
    common = sorted(set(close.columns) & set(volume.columns))
    return (close[common] * volume[common]).fillna(0.0)


def compute_share(turnover: pd.DataFrame, smooth_days: int = 5) -> pd.DataFrame:
    """日次セクターシェア(%)。短期ノイズ除去のためローリング平均を適用。"""
    smoothed = turnover.rolling(smooth_days, min_periods=1).mean()
    total = smoothed.sum(axis=1).replace(0, pd.NA)
    share = smoothed.divide(total, axis=0) * 100.0
    return share.dropna(how="all")
