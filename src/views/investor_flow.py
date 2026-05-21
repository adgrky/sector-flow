"""投資部門別売買フロー ビュー。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# 主要表示順と色
INVESTOR_ORDER = [
    "海外投資家", "個人", "信託銀行", "投資信託",
    "事業法人", "金融機関", "生保・損保", "都銀・地銀等",
    "証券会社", "その他法人", "法人",
]
INVESTOR_COLORS = {
    "海外投資家": "#1f77b4",
    "個人": "#ff7f0e",
    "信託銀行": "#2ca02c",
    "投資信託": "#9467bd",
    "事業法人": "#8c564b",
    "金融機関": "#7f7f7f",
    "生保・損保": "#bcbd22",
    "都銀・地銀等": "#17becf",
    "証券会社": "#c5b0d5",
    "その他法人": "#e377c2",
    "法人": "#aec7e8",
}


def _to_oku(df: pd.DataFrame) -> pd.DataFrame:
    """千円 → 億円 (=10万千円)。"""
    return df / 100_000.0


def render_net_bar(flow: pd.DataFrame, focus: list[str] | None = None) -> go.Figure:
    """週次のネット売買代金バーチャート(億円)。"""
    fig = go.Figure()
    if flow.empty:
        return fig
    df = _to_oku(flow)
    cols = focus or [c for c in INVESTOR_ORDER if c in df.columns]

    for c in cols:
        fig.add_trace(go.Bar(
            x=df.index, y=df[c], name=c,
            marker_color=INVESTOR_COLORS.get(c, "#999999"),
            hovertemplate=f"<b>{c}</b><br>%{{x|%Y-%m-%d}}<br>%{{y:,.0f}} 億円<extra></extra>",
        ))

    fig.update_layout(
        height=520,
        barmode="group",
        yaxis=dict(title="ネット売買代金 (億円)  ※プラス=買越 / マイナス=売越", zeroline=True),
        xaxis=dict(title="週(金曜)"),
        hovermode="x unified",
        margin=dict(l=60, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.add_hline(y=0, line=dict(color="black", width=1))
    return fig


def render_cumulative(flow: pd.DataFrame, focus: list[str] | None = None) -> go.Figure:
    """累積ネット買越額の推移ライン(億円)。"""
    fig = go.Figure()
    if flow.empty:
        return fig
    df = _to_oku(flow).fillna(0).cumsum()
    cols = focus or [c for c in INVESTOR_ORDER if c in df.columns]
    for c in cols:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[c], mode="lines+markers", name=c,
            line=dict(color=INVESTOR_COLORS.get(c, "#999999"), width=2),
            hovertemplate=f"<b>{c}</b><br>%{{x|%Y-%m-%d}}<br>累積 %{{y:,.0f}} 億円<extra></extra>",
        ))
    fig.update_layout(
        height=520,
        yaxis=dict(title="累積ネット買越額 (億円)"),
        xaxis=dict(title="週(金曜)"),
        hovermode="x unified",
        margin=dict(l=60, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.add_hline(y=0, line=dict(color="black", width=1))
    return fig


def latest_summary(flow: pd.DataFrame) -> pd.DataFrame:
    """直近週の投資部門別ランキング表(億円)。"""
    if flow.empty:
        return pd.DataFrame()
    df = _to_oku(flow)
    last = df.iloc[-1].dropna().sort_values(ascending=False)
    out = pd.DataFrame({
        "投資部門": last.index,
        "ネット売買 (億円)": last.values.round(0),
        "状態": ["🟢 買越" if v > 0 else "🔴 売越" for v in last.values],
    }).reset_index(drop=True)
    return out
