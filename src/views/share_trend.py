"""売買代金シェア推移ビュー。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..data.sectors import TOPIX17_ETFS


def render_share_trend(share: pd.DataFrame, lookback_days: int = 90) -> go.Figure:
    """100%積み上げエリアチャート。"""
    df = share.tail(lookback_days).copy()
    cols = [c for c in df.columns if c in TOPIX17_ETFS]
    df = df[cols]

    # 直近の平均シェアでセクターを並べ替え（多い順を下に）
    recent_mean = df.tail(20).mean().sort_values()
    df = df[recent_mean.index]

    fig = go.Figure()
    palette = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
        "#c49c94", "#f7b6d2",
    ]
    for color, code in zip(palette, df.columns):
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df[code],
            mode="lines",
            stackgroup="one",
            groupnorm="percent",
            name=TOPIX17_ETFS[code],
            line=dict(width=0.5, color=color),
            hovertemplate=f"{TOPIX17_ETFS[code]}: %{{y:.1f}}%<extra></extra>",
        ))

    fig.update_layout(
        height=620,
        yaxis=dict(title="売買代金シェア (%)", ticksuffix="%", range=[0, 100]),
        xaxis=dict(title="日付"),
        hovermode="x unified",
        margin=dict(l=60, r=20, t=40, b=40),
        legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.02),
    )
    return fig


def render_top_movers(share: pd.DataFrame, days: int = 20) -> pd.DataFrame:
    """直近 N 日でシェアが増加/減少したセクターTOP5を返す。"""
    if share.empty or len(share) < days + 1:
        return pd.DataFrame()
    cols = [c for c in share.columns if c in TOPIX17_ETFS]
    recent = share[cols].tail(days).mean()
    prev = share[cols].iloc[-2 * days:-days].mean()
    delta = (recent - prev).rename("シェア変化(pt)")
    out = pd.DataFrame({
        "セクター": [TOPIX17_ETFS[c] for c in delta.index],
        "現シェア(%)": recent.round(2).values,
        "前期シェア(%)": prev.round(2).values,
        "変化(pt)": delta.round(2).values,
    }).sort_values("変化(pt)", ascending=False).reset_index(drop=True)
    return out
