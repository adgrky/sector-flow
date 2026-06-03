"""スマホ向けダイジェストビュー。

縦長レイアウト、グラフ最小、テキスト・テーブル中心。
「今どこに資金が向いているか」を1画面で把握できる構成。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..data.sectors import ALL_INDICES


def _format_pct(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v:+.2f}%"


def _name_with_mark(code: str) -> str:
    prefix = "★" if code.startswith("T") else ""
    return f"{prefix}{ALL_INDICES.get(code, code)}"


def render_mobile_digest(
    returns_df: pd.DataFrame,
    rs_ratio: pd.DataFrame,
    rs_mom: pd.DataFrame,
    investor_flow: pd.DataFrame,
    last_date: pd.Timestamp | None,
) -> None:
    """スマホ用1画面ダイジェスト。Streamlitに直接出力する。"""
    if last_date is not None:
        st.caption(f"📅 {last_date.date()} 時点")

    # --- 1. 強弱TOP / BOTTOM (1週ベース) ---
    st.markdown("### 🔥 今週の強弱 (1週騰落率)")
    if returns_df.empty or "1週" not in returns_df.columns:
        st.info("データなし")
    else:
        ranked = returns_df["1週"].dropna().sort_values(ascending=False)
        top5 = ranked.head(5)
        bot5 = ranked.tail(5).iloc[::-1]

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🟢 強い TOP5**")
            for code, val in top5.items():
                st.markdown(f"`{_format_pct(val):>8}` {_name_with_mark(code)}")
        with col2:
            st.markdown("**🔴 弱い TOP5**")
            for code, val in bot5.items():
                st.markdown(f"`{_format_pct(val):>8}` {_name_with_mark(code)}")

    st.markdown("---")

    # --- 2. 加速度ランキング ---
    st.markdown("### ⚡ 加速度 (1週ペース vs 1月ペース)")
    if returns_df.empty or "1週" not in returns_df.columns or "1ヶ月" not in returns_df.columns:
        st.info("データなし")
    else:
        accel = (returns_df["1週"] / 5 - returns_df["1ヶ月"] / 21).dropna().sort_values(ascending=False)
        up3 = accel.head(3)
        dn3 = accel.tail(3).iloc[::-1]
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**↑↑ 加速TOP3**")
            for code, val in up3.items():
                st.markdown(f"`{val:+.2f}` {_name_with_mark(code)}")
            st.caption("単位: %/日 差")
        with col2:
            st.markdown("**↓↓ 減速TOP3**")
            for code, val in dn3.items():
                st.markdown(f"`{val:+.2f}` {_name_with_mark(code)}")
            st.caption("単位: %/日 差")

    st.markdown("---")

    # --- 3. RRG 象限別リスト ---
    st.markdown("### 🌀 RRG 象限分布")
    if rs_ratio.empty or rs_mom.empty:
        st.info("データなし")
    else:
        last_x = rs_ratio.iloc[-1]
        last_y = rs_mom.iloc[-1]
        common = [c for c in last_x.index if c in last_y.index and c in ALL_INDICES]

        leading: list[tuple[str, float]] = []
        improving: list[tuple[str, float]] = []
        weakening: list[tuple[str, float]] = []
        lagging: list[tuple[str, float]] = []
        for c in common:
            x, y = float(last_x[c]), float(last_y[c])
            dist = ((x - 100) ** 2 + (y - 100) ** 2) ** 0.5
            if x >= 100 and y >= 100:
                leading.append((c, dist))
            elif x < 100 and y >= 100:
                improving.append((c, dist))
            elif x >= 100 and y < 100:
                weakening.append((c, dist))
            else:
                lagging.append((c, dist))

        def _render_quad(label: str, color_dot: str, items: list[tuple[str, float]],
                         hint: str) -> None:
            st.markdown(f"**{color_dot} {label}** _{hint}_")
            if not items:
                st.markdown("  _なし_")
                return
            items.sort(key=lambda t: t[1], reverse=True)
            st.markdown(", ".join(_name_with_mark(c) for c, _ in items))

        _render_quad("Leading", "🟢", leading, "主導・買い継続候補")
        _render_quad("Improving", "🔵", improving, "底打ち反転・初動候補")
        _render_quad("Weakening", "🟡", weakening, "利確検討")
        _render_quad("Lagging", "🔴", lagging, "敬遠")

    st.markdown("---")

    # --- 4. 投資部門別 直近週 ---
    st.markdown("### 🌍 直近週の投資部門 (TSE Prime)")
    if investor_flow is None or investor_flow.empty:
        st.info("データなし")
    else:
        latest = investor_flow.iloc[-1]
        week = investor_flow.index[-1].date()
        st.caption(f"基準週: {week}")
        focus_order = ["海外投資家", "個人", "信託銀行", "投資信託", "事業法人"]
        for name in focus_order:
            if name not in latest.index:
                continue
            v = latest[name]
            if pd.isna(v):
                continue
            # JPX は千円単位 → 億円換算
            oku = v / 1e5
            arrow = "🟢買越" if oku > 0 else ("🔴売越" if oku < 0 else "—")
            st.markdown(f"- **{name}**: {arrow} `{oku:+,.0f}億円`")

    st.markdown("---")
    st.caption(
        "💡 他のタブで詳細を確認: ヒートマップ/RRG/売買代金シェア/ドリルダウン/投資部門別"
    )
