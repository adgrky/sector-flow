"""期間別の騰落率計算。"""
from __future__ import annotations

import pandas as pd

PERIODS_TRADING_DAYS: dict[str, int] = {
    "1日": 1,
    "1週": 5,
    "1ヶ月": 21,
    "3ヶ月": 63,
    "6ヶ月": 126,
    "YTD": -1,  # 特殊扱い
}


def period_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """各列(セクター)について、期間別の騰落率(%)テーブルを返す。

    行=列名(コード)、列=期間ラベル。
    """
    if prices.empty:
        return pd.DataFrame()

    last = prices.ffill().iloc[-1]
    out: dict[str, pd.Series] = {}
    for label, days in PERIODS_TRADING_DAYS.items():
        if label == "YTD":
            year_start = pd.Timestamp(year=prices.index[-1].year, month=1, day=1)
            mask = prices.index >= year_start
            if not mask.any():
                continue
            base = prices.loc[mask].ffill().iloc[0]
        else:
            if len(prices) <= days:
                continue
            base = prices.ffill().iloc[-1 - days]
        out[label] = (last / base - 1.0) * 100.0

    return pd.DataFrame(out)
