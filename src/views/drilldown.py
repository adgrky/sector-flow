"""セクター内ドリルダウンビュー。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def build_drilldown_table(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    name_map: dict[str, str],
) -> pd.DataFrame:
    """銘柄別の騰落率と擬似売買代金、相対勢いを集計したテーブル。"""
    if close.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    last_idx = -1
    last_close = close.ffill().iloc[last_idx]
    for code in close.columns:
        s = close[code].dropna()
        if s.empty:
            continue
        v = volume[code].dropna() if code in volume.columns else pd.Series(dtype=float)
        # 期間別騰落率
        def ret(days: int) -> float | None:
            if len(s) <= days:
                return None
            return float((s.iloc[-1] / s.iloc[-1 - days] - 1.0) * 100.0)

        r1, r5, r21, r63 = ret(1), ret(5), ret(21), ret(63)

        # 擬似売買代金 (直近5日平均) と前期比
        if not v.empty:
            turnover = (s * v).dropna()
            recent5 = turnover.tail(5).mean()
            prev5 = turnover.iloc[-10:-5].mean() if len(turnover) >= 10 else None
            vol_ratio = (recent5 / prev5 - 1.0) * 100.0 if prev5 and prev5 > 0 else None
        else:
            recent5 = None
            vol_ratio = None

        rows.append({
            "コード": code,
            "銘柄名": name_map.get(code, code),
            "終値": float(last_close.get(code, float("nan"))) if code in last_close.index else None,
            "1日%": r1, "1週%": r5, "1ヶ月%": r21, "3ヶ月%": r63,
            "売買代金(直近5日平均)": recent5,
            "出来高変化%(vs 前5日)": vol_ratio,
        })

    df = pd.DataFrame(rows)
    return df


def render_drilldown_table(df: pd.DataFrame, sort_by: str = "1週%") -> pd.DataFrame:
    """ソート済み表示用 DataFrame を返す。"""
    if df.empty or sort_by not in df.columns:
        return df
    return df.sort_values(sort_by, ascending=False).reset_index(drop=True)


def render_constituent_chart(
    close: pd.DataFrame,
    name_map: dict[str, str],
    lookback_days: int = 60,
) -> go.Figure:
    """構成銘柄を起点正規化(=100)した重ね描きチャート。"""
    fig = go.Figure()
    if close.empty:
        return fig
    df = close.tail(lookback_days).ffill()
    if df.empty:
        return fig
    norm = df.divide(df.iloc[0]) * 100.0
    palette = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
    ]
    for i, code in enumerate(norm.columns):
        fig.add_trace(go.Scatter(
            x=norm.index, y=norm[code], mode="lines",
            name=name_map.get(code, code),
            line=dict(color=palette[i % len(palette)], width=1.5),
            hovertemplate=f"{name_map.get(code, code)}: %{{y:.2f}}<extra></extra>",
        ))
    fig.add_hline(y=100, line=dict(color="gray", width=1, dash="dot"))
    fig.update_layout(
        height=500,
        yaxis=dict(title="正規化価格 (=100)"),
        xaxis=dict(title="日付"),
        hovermode="x unified",
        margin=dict(l=60, r=20, t=30, b=40),
        legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.02),
    )
    return fig
