"""セクター別ヒートマップビュー。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..data.sectors import ALL_INDICES


def _acceleration_symbol(pace_week: float, pace_month: float) -> str:
    """1週ペースと1ヶ月ペースの差分(%/日)から加速/減速マーカーを返す。

    ↑↑: 強い加速 / ↑: 加速 / →: 横ばい / ↓: 減速 / ↓↓: 強い減速
    """
    if pd.isna(pace_week) or pd.isna(pace_month):
        return "  "
    accel = pace_week - pace_month  # %/日 単位の差
    if accel > 0.15:
        return "↑↑"
    if accel > 0.05:
        return "↑ "
    if accel < -0.15:
        return "↓↓"
    if accel < -0.05:
        return "↓ "
    return "→ "


def render_heatmap(returns_df: pd.DataFrame, sort_by: str = "1週") -> go.Figure:
    """期間別騰落率ヒートマップを返す。

    Y軸ラベルに「加速/減速」マーカーを併記:
    - 1週の平均ペース (% / 日) と 1ヶ月の平均ペース (% / 日) の差で判定
    """
    df = returns_df.copy()
    df = df.loc[df.index.isin(ALL_INDICES.keys())]

    # 加速判定: %/日ペース差
    pace_week = df["1週"] / 5 if "1週" in df.columns else pd.Series(np.nan, index=df.index)
    pace_month = df["1ヶ月"] / 21 if "1ヶ月" in df.columns else pd.Series(np.nan, index=df.index)

    sym = {idx: _acceleration_symbol(pace_week.get(idx, np.nan), pace_month.get(idx, np.nan))
           for idx in df.index}

    # 表示用ラベル: "↑↑ 半導体" (テーマには★)
    def _label(code: str) -> str:
        name = ALL_INDICES[code]
        prefix = "★ " if code.startswith("T") else ""
        return f"{sym[code]} {prefix}{name}"

    df.index = [_label(c) for c in df.index]

    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False)

    text = df.round(2).astype(str) + "%"

    # 外れ値の影響を抑えるため 95 パーセンタイル基準（最低5%）
    flat = df.values.flatten()
    flat = flat[~np.isnan(flat)]
    if flat.size:
        abs_max = max(float(np.percentile(np.abs(flat), 95)), 5.0)
    else:
        abs_max = 5.0

    fig = go.Figure(
        data=go.Heatmap(
            z=df.values,
            x=df.columns,
            y=df.index,
            colorscale="RdYlGn",
            zmid=0,
            zmin=-abs_max,
            zmax=abs_max,
            text=text.values,
            texttemplate="%{text}",
            textfont={"size": 11},
            colorbar={"title": "騰落率 (%)"},
        )
    )
    row_count = len(df.index)
    fig.update_layout(
        height=max(620, 32 * row_count + 120),
        margin=dict(l=200, r=20, t=40, b=40),
        yaxis=dict(autorange="reversed", tickfont=dict(family="monospace", size=12)),
    )
    return fig
