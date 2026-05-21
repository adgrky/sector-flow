"""JPX 投資部門別売買状況の取得・パース。

JPX サイトから週次 Excel をスクレイプし、投資部門別ネット売買代金(差引)を抽出。
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from .cache import CACHE_DIR, is_fresh, load_cached, save_cached

JPX_INDEX_URL = "https://www.jpx.co.jp/markets/statistics-equities/investor-type/index.html"
JPX_BASE = "https://www.jpx.co.jp"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ja,en;q=0.9",
}

# Excel 内 [行, 当週バランス列] のマッピング
# row は "売り" 行 (合計のbalance列が当週)
INVESTOR_ROW_MAP = {
    "法人": 23,
    "個人": 26,
    "海外投資家": 29,
    "証券会社": 32,
    "投資信託": 37,
    "事業法人": 40,
    "その他法人": 43,
    "金融機関": 46,
    "生保・損保": 51,
    "都銀・地銀等": 54,
    "信託銀行": 57,
}
BALANCE_COL_CURRENT = 10  # 当週の "差引き Balance"


def fetch_index() -> list[tuple[str, str]]:
    """インデックスページから (yymmnn, file_url) のリストを返す（売買代金=val のみ）。"""
    resp = requests.get(JPX_INDEX_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    pattern = re.compile(r'href="(/markets/statistics-equities/investor-type/[^"]*stock_val_1_(\d{6})\.xls)"')
    seen: dict[str, str] = {}
    for href, key in pattern.findall(resp.text):
        seen[key] = JPX_BASE + href
    items = sorted(seen.items(), key=lambda kv: kv[0], reverse=True)
    return items


def _parse_yymmnn(key: str) -> datetime | None:
    """260404 → 2026年4月第4週の金曜日近似（厳密でなくてもOK、表示用）。"""
    try:
        yy = int(key[0:2])
        mm = int(key[2:4])
        nn = int(key[4:6])
        year = 2000 + yy
        # 当該月のnn週目の金曜日近似
        first = datetime(year, mm, 1)
        # 第1週の金曜
        offset = (4 - first.weekday()) % 7
        friday = first.replace(day=1 + offset + (nn - 1) * 7)
        return friday
    except Exception:
        return None


def _download_xls(url: str, key: str) -> Path:
    cache_file = CACHE_DIR / f"jpx_{key}.xls"
    if cache_file.exists() and cache_file.stat().st_size > 1000:
        return cache_file
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    cache_file.write_bytes(resp.content)
    return cache_file


def _parse_xls(path: Path, sheet: str = "TSE Prime") -> dict[str, float]:
    """1ファイルから当週の投資部門別ネット売買代金(千円)を取り出す。

    JPX は「売越=売り行に負値、買越=買い行に正値」のため、
    売り行と買い行の両方を見て非NaN値を採用する。
    """
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    out: dict[str, float] = {}
    for name, row in INVESTOR_ROW_MAP.items():
        val = float("nan")
        for r in (row, row + 1):
            try:
                v = df.iat[r, BALANCE_COL_CURRENT]
                if pd.isna(v):
                    continue
                if isinstance(v, str):
                    v = v.replace(",", "").strip()
                    if not v:
                        continue
                val = float(v)
                break
            except Exception:
                continue
        out[name] = val
    return out


def get_investor_flow(
    max_weeks: int = 26,
    market: str = "TSE Prime",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """投資部門別ネット売買代金時系列を累積取得。

    JPX インデックスページに掲載されるのは直近5週のみだが、
    既存キャッシュがある場合は新規週のみ追加することで長期蓄積する。

    返り値: index=週(金曜)、列=投資部門、値=ネット売買代金(千円)
    """
    cache_name = f"jpx_investor_{market.replace(' ', '_')}"

    # 既存累積キャッシュ
    existing: pd.DataFrame = pd.DataFrame()
    if not force_refresh:
        cached = load_cached(cache_name)
        if cached is not None and not cached.empty:
            existing = cached
            # インデックス再取得は6時間に1度に制限
            if is_fresh(cache_name, max_age_hours=6):
                return existing.tail(max_weeks)

    # JPX インデックスから利用可能な週リストを取得
    try:
        items = fetch_index()
    except Exception:
        return existing.tail(max_weeks) if not existing.empty else pd.DataFrame()

    # 既存と重複しない週のみ処理
    existing_keys: set[str] = set()
    if "_key" in existing.columns:
        existing_keys = set(existing["_key"].astype(str).tolist())

    new_rows: list[dict] = []
    for key, url in items:
        if key in existing_keys:
            continue
        try:
            path = _download_xls(url, key)
            row = _parse_xls(path, sheet=market)
            row["週"] = _parse_yymmnn(key)
            row["_key"] = key
            new_rows.append(row)
        except Exception:
            continue
        time.sleep(0.3)

    if not new_rows and existing.empty:
        return pd.DataFrame()

    new_df = pd.DataFrame(new_rows)
    if not new_df.empty:
        new_df = new_df.dropna(subset=["週"]).set_index("週")
    # 既存とマージ
    if not existing.empty and not new_df.empty:
        df = pd.concat([existing, new_df])
        df = df[~df.index.duplicated(keep="last")].sort_index()
    elif not new_df.empty:
        df = new_df.sort_index()
    else:
        df = existing.sort_index()

    save_cached(cache_name, df)
    return df.drop(columns=["_key"], errors="ignore").tail(max_weeks)
