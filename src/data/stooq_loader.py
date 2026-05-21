"""Stooq から TOPIX-17 セクターETFの日次株価を取得する。

優先: Stooq の CSV 直ダウンロード → フォールバック: yfinance
"""
from __future__ import annotations

import io
import time
from datetime import date

import pandas as pd
import requests

from .cache import is_fresh, load_cached, save_cached
from .sectors import TOPIX17_ETFS

STOOQ_CSV_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"
HEADERS = {"User-Agent": "Mozilla/5.0 (sector-flow research tool)"}


def _stooq_symbol(code: str) -> str:
    return f"{code}.jp"


def _yf_symbol(code: str) -> str:
    return f"{code}.T"


def _fetch_one_stooq(code: str) -> pd.DataFrame | None:
    try:
        url = STOOQ_CSV_URL.format(symbol=_stooq_symbol(code))
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200 or not resp.text or "No data" in resp.text[:50]:
            return None
        df = pd.read_csv(io.StringIO(resp.text))
        if df.empty or "Close" not in df.columns or "Date" not in df.columns:
            return None
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        cols = {"Close": f"{code}_close"}
        if "Volume" in df.columns:
            cols["Volume"] = f"{code}_volume"
        return df.rename(columns=cols)[list(cols.values())]
    except Exception:
        return None


def _fetch_one_yf(code: str, start: date, end: date) -> pd.DataFrame | None:
    try:
        import yfinance as yf

        df = yf.download(
            _yf_symbol(code),
            start=start.isoformat(),
            end=end.isoformat(),
            progress=False,
            auto_adjust=True,
        )
        if df is None or df.empty:
            return None
        close = df["Close"]
        vol = df.get("Volume")
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        if isinstance(vol, pd.DataFrame):
            vol = vol.iloc[:, 0]
        out = pd.DataFrame({f"{code}_close": close})
        if vol is not None:
            out[f"{code}_volume"] = vol
        return out
    except Exception:
        return None


def fetch_ohlcv(
    codes: list[str],
    start: date,
    end: date,
) -> pd.DataFrame:
    """指定コードの終値・出来高を取得。yfinance 優先、Stooq フォールバック。"""
    frames: list[pd.DataFrame] = []
    for code in codes:
        s = _fetch_one_yf(code, start, end)
        if s is None or s.empty:
            s = _fetch_one_stooq(code)
        if s is not None and not s.empty:
            frames.append(s)
        time.sleep(0.2)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, axis=1).sort_index()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    out = out[(out.index >= pd.Timestamp(start)) & (out.index <= pd.Timestamp(end))]
    return out


def _split_close_volume(ohlcv: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    close_cols = [c for c in ohlcv.columns if c.endswith("_close")]
    vol_cols = [c for c in ohlcv.columns if c.endswith("_volume")]
    close = ohlcv[close_cols].rename(columns=lambda c: c.removesuffix("_close"))
    volume = ohlcv[vol_cols].rename(columns=lambda c: c.removesuffix("_volume"))
    return close, volume


def get_sector_data(force_refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """TOPIX-17 セクターETFの (終値, 出来高) を返す。"""
    cache_name = "sector_ohlcv"
    if not force_refresh and is_fresh(cache_name):
        cached = load_cached(cache_name)
        if cached is not None and not cached.empty:
            return _split_close_volume(cached)

    codes = list(TOPIX17_ETFS.keys())
    end = pd.Timestamp.now().normalize()
    start = end - pd.Timedelta(days=3 * 365 + 30)
    df = fetch_ohlcv(codes, start.date(), end.date())
    if not df.empty:
        save_cached(cache_name, df)
    return _split_close_volume(df)


def get_sector_prices(force_refresh: bool = False) -> pd.DataFrame:
    """後方互換: 終値のみ返す。"""
    close, _ = get_sector_data(force_refresh=force_refresh)
    return close
