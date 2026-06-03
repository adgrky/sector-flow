"""日本株セクター資金フロー可視化アプリ - Streamlit エントリポイント。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.analytics.flow import compute_share, compute_turnover
from src.analytics.returns import PERIODS_TRADING_DAYS, period_returns
from src.analytics.rrg import compute_rrg
from src.data.constituents import get_constituents
from src.data.jpx_investor import get_investor_flow
from src.data.sectors import ALL_INDICES, TOPIX17_ETFS
from src.data.stock_loader import get_stocks_data
from src.data.stooq_loader import get_sector_data
from src.data.theme_loader import get_theme_data
from src.data.themes import THEME_NAMES
from src.views.drilldown import (
    build_drilldown_table,
    render_constituent_chart,
    render_drilldown_table,
)
from src.views.heatmap import render_heatmap
from src.views.mobile import render_mobile_digest
from src.views.investor_flow import (
    INVESTOR_ORDER,
    latest_summary,
    render_cumulative,
    render_net_bar,
)
from src.views.rrg_chart import render_rrg
from src.views.share_trend import render_share_trend, render_top_movers

st.set_page_config(
    page_title="セクター資金フロー",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(ttl=60 * 60 * 6)
def load_sector_data():
    return get_sector_data()


@st.cache_data(ttl=60 * 60 * 6)
def load_theme_data():
    return get_theme_data()


@st.cache_data(ttl=60 * 60 * 6)
def load_combined_data():
    """セクターETF + テーマ合成指数 を同一インデックスで結合した (close, volume)。"""
    sc, sv = load_sector_data()
    tc, tv = load_theme_data()
    if sc.empty and tc.empty:
        return pd.DataFrame(), pd.DataFrame()
    close = pd.concat([sc, tc], axis=1).sort_index() if not tc.empty else sc
    volume = pd.concat([sv, tv], axis=1).sort_index() if not tv.empty else sv
    # 重複日インデックス防御
    close = close[~close.index.duplicated(keep="last")]
    volume = volume[~volume.index.duplicated(keep="last")]
    return close, volume


@st.cache_data(ttl=60 * 60 * 6)
def cached_returns():
    close, _ = load_combined_data()
    return period_returns(close)


@st.cache_data(ttl=60 * 60 * 6)
def cached_rrg(window: int):
    close, _ = load_combined_data()
    return compute_rrg(close, window=window)


@st.cache_data(ttl=60 * 60 * 6)
def cached_share(smooth_days: int):
    # 売買代金シェアはセクターのみ (テーマと混ぜると重複カウントになる)
    close, volume = load_sector_data()
    turnover = compute_turnover(close, volume)
    return compute_share(turnover, smooth_days=smooth_days)


@st.cache_data(ttl=60 * 60 * 6)
def cached_constituents(code: str):
    constituents = get_constituents(code)
    codes = [c for c, _ in constituents]
    name_map = {c: n for c, n in constituents}
    close, vol = get_stocks_data(codes, lookback_days=200)
    return close, vol, name_map


@st.cache_data(ttl=60 * 60 * 6)
def cached_investor_flow(market: str, weeks: int):
    return get_investor_flow(max_weeks=weeks, market=market)


def main() -> None:
    st.title("📊 日本株セクター資金フロー")
    st.caption("TOPIX-17 業種別ETF + カスタムテーマ + 投資部門別売買状況による資金フロー可視化")

    with st.sidebar:
        st.header("設定")
        if st.button("🔄 全データを再取得"):
            load_sector_data.clear()
            load_theme_data.clear()
            load_combined_data.clear()
            cached_returns.clear()
            cached_rrg.clear()
            cached_share.clear()
            cached_constituents.clear()
            cached_investor_flow.clear()
            get_sector_data(force_refresh=True)
            st.rerun()
        st.markdown("---")
        st.markdown(
            "**ベンチマーク**: TOPIX-17 等加重\n\n"
            "**テーマ (★)**: 半導体/防衛/AI・DC/インバウンド の等加重合成指数\n\n"
            "**売買代金**: ETF出来高×終値による擬似値\n\n"
            "**投資部門別**: JPX公式週次データ\n\n"
            "データ: Yahoo Finance / Stooq / JPX"
        )

    tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📱 ダイジェスト",
        "🔥 ヒートマップ",
        "🌀 RRG",
        "💴 売買代金シェア",
        "🔍 セクタードリルダウン",
        "🌍 投資部門別フロー",
    ])

    with tab0:
        st.subheader("📱 今どこに資金が向かっているか")
        st.caption("スマホ向け1画面ダイジェスト。詳細は他のタブで。")
        ret_for_mobile = cached_returns()
        rs_r, rs_m = cached_rrg(14)
        inv = cached_investor_flow("TSE Prime", 8)
        close_for_mobile, _ = load_combined_data()
        last_d = close_for_mobile.index[-1] if not close_for_mobile.empty else None
        render_mobile_digest(ret_for_mobile, rs_r, rs_m, inv, last_d)

    with tab1:
        st.subheader("期間別騰落率ヒートマップ")
        st.write(
            "色が**緑=資金流入で上昇**、**赤=流出で下落**。★印=カスタムテーマ。"
            "Y軸の **↑↑/↑/→/↓/↓↓** は「1週ペース vs 1ヶ月ペース」の加速度判定。"
        )
        close_for_date, _ = load_combined_data()
        if not close_for_date.empty:
            st.caption(f"📅 データ最終日: {close_for_date.index[-1].date()}")
        with st.spinner("データ取得中..."):
            returns_df = cached_returns()
        if returns_df.empty:
            st.error("データ取得失敗。")
        else:
            available = [p for p in PERIODS_TRADING_DAYS if p in returns_df.columns]
            sort_by = st.selectbox("並べ替え基準", available, index=min(2, len(available) - 1))
            st.plotly_chart(render_heatmap(returns_df, sort_by=sort_by), use_container_width=True)
            with st.expander("生データ"):
                st.dataframe(returns_df.round(2))

    with tab2:
        st.subheader("Relative Rotation Graph (RRG)")
        st.write(
            "**Leading**=主導 / **Weakening**=ピークアウト / "
            "**Lagging**=出遅れ / **Improving**=底打ち反転。時計回り循環。"
            " ◆=テーマ、●=セクター。"
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            window = st.slider("RSウィンドウ (週)", 8, 26, 14, 1)
        with c2:
            tail = st.slider("軌跡の表示週数", 3, 20, 6, 1)
        with c3:
            dim_center = st.slider("中央近傍を薄表示する半径", 0.0, 3.0, 1.2, 0.2,
                                    help="この距離以内のセクターは半透明化")

        close_for_date, _ = load_combined_data()
        if not close_for_date.empty:
            st.caption(f"📅 データ最終日: {close_for_date.index[-1].date()}")
        with st.spinner("RRG計算中..."):
            rs_ratio, rs_mom = cached_rrg(window)
        if rs_ratio.empty:
            st.warning("データ不足。")
        else:
            # 表示対象セレクタ: デフォルトは中心からの距離が大きいTOP10
            last_x = rs_ratio.iloc[-1]
            last_y = rs_mom.iloc[-1]
            common = [c for c in last_x.index if c in last_y.index and c in ALL_INDICES]
            distances = pd.Series(
                {c: ((last_x[c] - 100) ** 2 + (last_y[c] - 100) ** 2) ** 0.5 for c in common}
            ).sort_values(ascending=False)
            default_sel = distances.head(10).index.tolist()
            options = list(distances.index)
            sel = st.multiselect(
                "表示するセクター/テーマ (中心からの距離が大きい順に既定選択)",
                options=options,
                default=default_sel,
                format_func=lambda c: f"{'★' if c.startswith('T') else '●'} {ALL_INDICES.get(c, c)}",
            )

            st.plotly_chart(
                render_rrg(rs_ratio, rs_mom, tail_weeks=tail,
                            selected_codes=sel, dim_center_radius=dim_center),
                use_container_width=True,
            )
            st.caption(f"最新基準週: {rs_ratio.index[-1].date()}")

    with tab3:
        st.subheader("売買代金シェア推移")
        st.write(
            "100%積み上げで「実弾(売買代金)がどのセクターに集まっているか」の時系列推移。"
            "セクターETFのみ集計 (テーマはセクターと重複するため除外)。"
        )
        c1, c2 = st.columns(2)
        with c1:
            lookback = st.selectbox("表示期間", ["1ヶ月", "3ヶ月", "6ヶ月", "1年"], index=1)
        with c2:
            smooth = st.slider("平滑化(日)", 1, 20, 5, 1)
        lookback_days = {"1ヶ月": 21, "3ヶ月": 63, "6ヶ月": 126, "1年": 252}[lookback]
        close_for_date, _ = load_sector_data()
        if not close_for_date.empty:
            st.caption(f"📅 データ最終日: {close_for_date.index[-1].date()}")
        with st.spinner("計算中..."):
            share = cached_share(smooth)
        if share.empty:
            st.warning("データなし。")
        else:
            st.plotly_chart(render_share_trend(share, lookback_days=lookback_days), use_container_width=True)
            st.markdown("##### 直近20営業日のシェア変化TOP")
            movers = render_top_movers(share, days=20)
            if not movers.empty:
                col_in, col_out = st.columns(2)
                with col_in:
                    st.markdown("**🔼 資金流入 (シェア増)**")
                    st.dataframe(movers.head(5), hide_index=True)
                with col_out:
                    st.markdown("**🔽 資金流出 (シェア減)**")
                    st.dataframe(movers.tail(5).iloc[::-1], hide_index=True)

    with tab4:
        st.subheader("セクター/テーマ内ドリルダウン")
        st.write("セクターまたはテーマを選んで、その中でどの銘柄が買われているかを確認。")

        # セクター + テーマを同じセレクタに統合
        sector_options = {f"●{TOPIX17_ETFS[c]} ({c})": c for c in TOPIX17_ETFS}
        theme_options = {f"★{THEME_NAMES[c]} ({c})": c for c in THEME_NAMES}
        all_options = {**theme_options, **sector_options}  # テーマを上に
        sel_label = st.selectbox("カテゴリを選択", list(all_options.keys()), index=0)
        code = all_options[sel_label]

        with st.spinner(f"{sel_label} の構成銘柄データ取得中..."):
            close_d, vol_d, name_map = cached_constituents(code)

        if close_d.empty:
            st.warning("データ取得に失敗しました。")
        else:
            st.caption(f"📅 データ最終日: {close_d.index[-1].date()}")
            table = build_drilldown_table(close_d, vol_d, name_map)
            sort_options = ["1日%", "1週%", "1ヶ月%", "3ヶ月%", "売買代金(直近5日平均)", "出来高変化%(vs 前5日)"]
            sort_by = st.selectbox("並べ替え基準", sort_options, index=1)
            sorted_table = render_drilldown_table(table, sort_by=sort_by)

            display = sorted_table.copy()
            for col in ["1日%", "1週%", "1ヶ月%", "3ヶ月%", "出来高変化%(vs 前5日)"]:
                if col in display.columns:
                    display[col] = display[col].round(2)
            if "売買代金(直近5日平均)" in display.columns:
                display["売買代金(直近5日平均)"] = (display["売買代金(直近5日平均)"] / 1e8).round(1).astype(str) + " 億円"
            if "終値" in display.columns:
                display["終値"] = display["終値"].round(1)

            st.dataframe(display, hide_index=True, use_container_width=True)

            st.markdown("##### 構成銘柄の正規化価格チャート (起点=100)")
            lookback_d = st.slider("表示期間 (営業日)", 20, 180, 60, 10, key="dd_lookback")
            st.plotly_chart(
                render_constituent_chart(close_d, name_map, lookback_days=lookback_d),
                use_container_width=True,
            )

    with tab5:
        st.subheader("投資部門別 ネット売買代金")
        st.write(
            "JPX公式の週次「投資部門別売買状況」から、誰が買って誰が売っているかを可視化。"
            "**海外投資家**は日本株最大プレイヤー、**個人**は逆張り傾向。"
        )
        c1, c2 = st.columns(2)
        with c1:
            market = st.selectbox("市場", ["TSE Prime", "TSE Standard", "TSE Growth"], index=0)
        with c2:
            weeks = st.slider("表示週数 (取得週数)", 4, 52, 26, 2)

        with st.spinner("JPX公式データ取得中（初回は時間がかかります）..."):
            flow = cached_investor_flow(market, weeks)

        if flow.empty:
            st.error("データ取得に失敗しました。サイドバーから再取得してください。")
        else:
            st.caption(f"取得済み週数: {len(flow)} | 期間: {flow.index[0].date()} 〜 {flow.index[-1].date()}")

            focus_default = ["海外投資家", "個人", "信託銀行", "投資信託", "事業法人"]
            focus = st.multiselect(
                "表示する投資部門",
                [c for c in INVESTOR_ORDER if c in flow.columns],
                default=[c for c in focus_default if c in flow.columns],
            )

            st.markdown("##### 週次ネット売買 (バー)")
            st.plotly_chart(render_net_bar(flow, focus=focus), use_container_width=True)

            st.markdown("##### 累積ネット買越額 (期間内累積)")
            st.plotly_chart(render_cumulative(flow, focus=focus), use_container_width=True)

            st.markdown("##### 直近週のサマリー")
            st.dataframe(latest_summary(flow), hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
