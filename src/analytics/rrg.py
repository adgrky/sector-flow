"""Relative Rotation Graph (RRG) の計算。

ベンチマーク = 全セクターETFの等加重リターン平均。
標準的な14週ローリングで RS-Ratio / RS-Momentum を算出。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.sectors import BENCHMARK_NAME

DEFAULT_WINDOW = 14  # 週


def to_weekly(prices: pd.DataFrame) -> pd.DataFrame:
    """日次終値を週次(金曜終値)に変換。"""
    return prices.resample("W-FRI").last().dropna(how="all")


def equal_weight_benchmark(prices: pd.DataFrame) -> pd.Series:
    """各セクターを正規化(=1.0スタート)した平均で等加重ベンチマークを生成。"""
    norm = prices.divide(prices.iloc[0])
    return norm.mean(axis=1).rename(BENCHMARK_NAME)


def compute_rrg(
    prices: pd.DataFrame,
    window: int = DEFAULT_WINDOW,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """RRGの (RS-Ratio, RS-Momentum) を週次で返す。

    両DataFrameはインデックス=週、列=セクターコード。
    100中心、>100=ベンチマーク優位、<100=劣後。
    """
    w = to_weekly(prices).ffill().dropna(how="all")
    bench = equal_weight_benchmark(w)

    # 相対強度
    rs = w.divide(bench, axis=0) * 100.0

    # JdK RS-Ratio: rsの正規化(平均100,標準偏差1中心)
    rs_mean = rs.rolling(window).mean()
    rs_std = rs.rolling(window).std()
    rs_ratio_raw = 100.0 + (rs - rs_mean) / rs_std
    # スムージング
    rs_ratio = rs_ratio_raw.rolling(window // 2 or 1).mean()

    # JdK RS-Momentum: RS-Ratio の前期比的変化を100中心で
    roc = rs_ratio.pct_change(periods=1) * 100.0
    rs_momentum = 100.0 + roc.rolling(window // 2 or 1).mean()

    return rs_ratio.dropna(how="all"), rs_momentum.dropna(how="all")
