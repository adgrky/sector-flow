"""セクター別ヒートマップビュー。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..data.sectors import ALL_INDICES


def render_heatmap(returns_df: pd.DataFrame, sort_by: str = "1週") -> go.Figure:
    """期間別騰落率ヒートマップを返す。"""
    df = returns_df.copy()
    df = df.loc[df.index.isin(ALL_INDICES.keys())]
    df.index = [ALL_INDICES[c] for c in df.index]

    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False)

    text = df.round(2).astype(str) + "%"

    # 外れ値の影響を抑えるため 95 パーセンタイル基準（最低5%）
    import numpy as np
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
    # 行数に応じて高さを動的調整 (21行=セクター17+テーマ4を想定)
    row_count = len(df.index)
    fig.update_layout(
        height=max(620, 32 * row_count + 120),
        margin=dict(l=140, r=20, t=40, b=40),
        yaxis=dict(autorange="reversed"),
    )
    return fig
