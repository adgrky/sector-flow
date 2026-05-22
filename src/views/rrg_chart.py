"""RRG (Relative Rotation Graph) ビュー。

クラスター解消のため:
- 表示セクターを selected_codes でフィルタ可能
- 軸パディング控えめ、近傍ラベルは位置自動調整
- 中央近傍 (距離<1.5) のセクターは半透明化して埋もれを軽減
"""
from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go

from ..data.sectors import ALL_INDICES

QUADRANT_COLORS = {
    "Leading": "rgba(0, 180, 0, 0.08)",
    "Weakening": "rgba(220, 180, 0, 0.10)",
    "Lagging": "rgba(220, 0, 0, 0.08)",
    "Improving": "rgba(0, 100, 220, 0.08)",
}


def _palette(n: int) -> list[str]:
    base = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
        "#c49c94", "#f7b6d2", "#dbdb8d", "#9edae5", "#393b79",
        "#637939",
    ]
    return (base * ((n // len(base)) + 1))[:n]


def render_rrg(
    rs_ratio: pd.DataFrame,
    rs_momentum: pd.DataFrame,
    tail_weeks: int = 6,
    selected_codes: list[str] | None = None,
    dim_center_radius: float = 1.2,
) -> go.Figure:
    """直近 tail_weeks 週の軌跡を持つRRGを描画。

    selected_codes: 表示対象を絞る (None=全て)。
    dim_center_radius: この距離以内の最新点は半透明化 (0で無効)。
    """
    fig = go.Figure()

    if rs_ratio.empty or rs_momentum.empty:
        return fig

    last_ratio = rs_ratio.tail(tail_weeks)
    last_mom = rs_momentum.tail(tail_weeks)
    common_cols = [c for c in last_ratio.columns if c in last_mom.columns and c in ALL_INDICES]
    if selected_codes is not None:
        common_cols = [c for c in common_cols if c in selected_codes]
    if not common_cols:
        return fig

    # 軸範囲 (タイト目)
    x_all = last_ratio[common_cols].stack()
    y_all = last_mom[common_cols].stack()
    x_pad = max(1.0, (x_all.max() - x_all.min()) * 0.05)
    y_pad = max(1.0, (y_all.max() - y_all.min()) * 0.05)
    xr = [min(x_all.min() - x_pad, 99.0), max(x_all.max() + x_pad, 101.0)]
    yr = [min(y_all.min() - y_pad, 99.0), max(y_all.max() + y_pad, 101.0)]

    # 4象限の背景
    fig.add_shape(type="rect", x0=100, x1=xr[1], y0=100, y1=yr[1],
                  fillcolor=QUADRANT_COLORS["Leading"], line_width=0, layer="below")
    fig.add_shape(type="rect", x0=100, x1=xr[1], y0=yr[0], y1=100,
                  fillcolor=QUADRANT_COLORS["Weakening"], line_width=0, layer="below")
    fig.add_shape(type="rect", x0=xr[0], x1=100, y0=yr[0], y1=100,
                  fillcolor=QUADRANT_COLORS["Lagging"], line_width=0, layer="below")
    fig.add_shape(type="rect", x0=xr[0], x1=100, y0=100, y1=yr[1],
                  fillcolor=QUADRANT_COLORS["Improving"], line_width=0, layer="below")

    # 中心十字
    fig.add_hline(y=100, line=dict(color="gray", width=1, dash="dot"))
    fig.add_vline(x=100, line=dict(color="gray", width=1, dash="dot"))

    # 象限ラベル
    for label, x, y, color in [
        ("Improving", xr[0] + (100 - xr[0]) * 0.12, yr[1] - (yr[1] - 100) * 0.12, "#1565c0"),
        ("Leading", xr[1] - (xr[1] - 100) * 0.12, yr[1] - (yr[1] - 100) * 0.12, "#2e7d32"),
        ("Lagging", xr[0] + (100 - xr[0]) * 0.12, yr[0] + (100 - yr[0]) * 0.12, "#c62828"),
        ("Weakening", xr[1] - (xr[1] - 100) * 0.12, yr[0] + (100 - yr[0]) * 0.12, "#ef6c00"),
    ]:
        fig.add_annotation(x=x, y=y, text=label, showarrow=False,
                           font=dict(size=13, color=color))

    # 最新点座標と中心距離
    latest_points: list[tuple[str, float, float, float]] = []
    for code in common_cols:
        x = float(last_ratio[code].iloc[-1])
        y = float(last_mom[code].iloc[-1])
        dist = math.hypot(x - 100, y - 100)
        latest_points.append((code, x, y, dist))

    def _label_position(code: str, x: float, y: float) -> str:
        thresh_x = (xr[1] - xr[0]) * 0.05
        thresh_y = (yr[1] - yr[0]) * 0.07
        right = any(
            oc != code and abs(ox - x) < thresh_x and oy > y - thresh_y and ox > x
            for oc, ox, oy, _ in latest_points
        )
        above = any(
            oc != code and abs(ox - x) < thresh_x and oy > y and abs(oy - y) < thresh_y
            for oc, ox, oy, _ in latest_points
        )
        if right and above:
            return "bottom left"
        if right:
            return "middle left"
        if above:
            return "bottom center"
        return "top center"

    # テーマは破線で区別
    colors = _palette(len(common_cols))
    for color, (code, _, _, dist) in zip(colors, latest_points):
        xs = last_ratio[code].values
        ys = last_mom[code].values
        name = ALL_INDICES.get(code, code)
        is_theme = code.startswith("T")
        # 中央近傍は半透明 + マーカー縮小
        dim = dist < dim_center_radius
        line_opacity = 0.25 if dim else 1.0
        marker_opacity = 0.3 if dim else 0.75
        latest_marker_opacity = 0.4 if dim else 1.0

        line_style = dict(color=color, width=1.8, dash="dash" if is_theme else "solid")
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines+markers",
            line=line_style,
            marker=dict(size=[5 + i for i in range(len(xs))], opacity=marker_opacity),
            opacity=line_opacity,
            name=("★ " if is_theme else "") + name,
            legendgroup=code, showlegend=True,
            hovertemplate=(
                f"<b>{name}</b>{' (テーマ)' if is_theme else ''}<br>"
                "RS-Ratio=%{x:.2f}<br>RS-Mom=%{y:.2f}<extra></extra>"
            ),
        ))
        pos = _label_position(code, xs[-1], ys[-1])
        fig.add_trace(go.Scatter(
            x=[xs[-1]], y=[ys[-1]],
            mode="markers+text",
            marker=dict(
                color=color, size=16 if is_theme else 14,
                line=dict(color="black", width=1.5 if is_theme else 1),
                symbol="diamond" if is_theme else "circle",
                opacity=latest_marker_opacity,
            ),
            text=[name],
            textposition=pos,
            textfont=dict(size=11, color=color),
            opacity=latest_marker_opacity,
            legendgroup=code, showlegend=False,
            hoverinfo="skip",
        ))

    fig.update_layout(
        height=820,
        xaxis=dict(title="RS-Ratio (相対強度)", range=xr),
        yaxis=dict(title="RS-Momentum (モメンタム)", range=yr),
        hovermode="closest",
        margin=dict(l=60, r=20, t=40, b=60),
        legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.02),
    )
    return fig
