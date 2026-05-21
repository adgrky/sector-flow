"""RRG (Relative Rotation Graph) ビュー。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..data.sectors import TOPIX17_ETFS

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
        "#c49c94", "#f7b6d2",
    ]
    return (base * ((n // len(base)) + 1))[:n]


def render_rrg(
    rs_ratio: pd.DataFrame,
    rs_momentum: pd.DataFrame,
    tail_weeks: int = 10,
) -> go.Figure:
    """直近 tail_weeks 週の軌跡を持つRRGを描画。"""
    fig = go.Figure()

    if rs_ratio.empty or rs_momentum.empty:
        return fig

    # 軸範囲
    last_ratio = rs_ratio.tail(tail_weeks)
    last_mom = rs_momentum.tail(tail_weeks)
    common_cols = [c for c in last_ratio.columns if c in last_mom.columns and c in TOPIX17_ETFS]

    x_all = last_ratio[common_cols].stack()
    y_all = last_mom[common_cols].stack()
    x_pad = max(2.0, (x_all.max() - x_all.min()) * 0.1)
    y_pad = max(2.0, (y_all.max() - y_all.min()) * 0.1)
    xr = [x_all.min() - x_pad, x_all.max() + x_pad]
    yr = [y_all.min() - y_pad, y_all.max() + y_pad]

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
        ("Improving", xr[0] + (100 - xr[0]) * 0.1, yr[1] - (yr[1] - 100) * 0.1, "#1565c0"),
        ("Leading", xr[1] - (xr[1] - 100) * 0.1, yr[1] - (yr[1] - 100) * 0.1, "#2e7d32"),
        ("Lagging", xr[0] + (100 - xr[0]) * 0.1, yr[0] + (100 - yr[0]) * 0.1, "#c62828"),
        ("Weakening", xr[1] - (xr[1] - 100) * 0.1, yr[0] + (100 - yr[0]) * 0.1, "#ef6c00"),
    ]:
        fig.add_annotation(x=x, y=y, text=label, showarrow=False,
                           font=dict(size=12, color=color))

    # セクター名衝突回避: 最新点座標を集めて、近い相手にはラベルをずらす
    latest_points: list[tuple[str, float, float]] = [
        (code, float(last_ratio[code].iloc[-1]), float(last_mom[code].iloc[-1]))
        for code in common_cols
    ]

    def _label_position(idx: int, code: str, x: float, y: float) -> str:
        """近い点が右側にあるなら左寄せ、上にあるなら下寄せ。"""
        thresh_x = (xr[1] - xr[0]) * 0.05
        thresh_y = (yr[1] - yr[0]) * 0.07
        right = any(
            other_code != code and abs(ox - x) < thresh_x and oy > y - thresh_y and ox > x
            for other_code, ox, oy in latest_points
        )
        above = any(
            other_code != code and abs(ox - x) < thresh_x and oy > y and abs(oy - y) < thresh_y
            for other_code, ox, oy in latest_points
        )
        if right and above:
            return "bottom left"
        if right:
            return "middle left"
        if above:
            return "bottom center"
        return "top center"

    # セクターごとに軌跡
    colors = _palette(len(common_cols))
    for idx, (color, code) in enumerate(zip(colors, common_cols)):
        xs = last_ratio[code].values
        ys = last_mom[code].values
        name = TOPIX17_ETFS[code]
        # 軌跡(線)
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines+markers",
            line=dict(color=color, width=1.5),
            marker=dict(size=[6 + i for i in range(len(xs))], opacity=0.6),
            name=name, legendgroup=code, showlegend=True,
            hovertemplate=f"<b>{name}</b><br>RS-Ratio=%{{x:.2f}}<br>RS-Mom=%{{y:.2f}}<extra></extra>",
        ))
        # 最新点(ラベル付き、位置を動的調整)
        pos = _label_position(idx, code, xs[-1], ys[-1])
        fig.add_trace(go.Scatter(
            x=[xs[-1]], y=[ys[-1]],
            mode="markers+text",
            marker=dict(color=color, size=14, line=dict(color="black", width=1)),
            text=[name], textposition=pos,
            textfont=dict(size=10, color=color),
            legendgroup=code, showlegend=False,
            hoverinfo="skip",
        ))

    fig.update_layout(
        height=720,
        xaxis=dict(title="RS-Ratio (相対強度)", range=xr),
        yaxis=dict(title="RS-Momentum (モメンタム)", range=yr),
        hovermode="closest",
        margin=dict(l=60, r=20, t=40, b=60),
    )
    return fig
