from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import yaml


# =========================
# Paths (IMPORTANT)
# =========================
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
EMBEDS_DIR = BASE_DIR / "embeds"
CONFIG_PATH = BASE_DIR / "content_config.yaml"

ICON_PATH = ASSETS_DIR / "icon.png"
CSS_PATH = ASSETS_DIR / "style.css"


# =========================
# Config
# =========================
DEFAULT_CONFIG: Dict[str, Any] = {
    "site": {"title": "まる | 日本株の学びと記録", "tagline": "株式投資と学びの記録をお届けします", "handle": "maru_update"},
    "links": {
        "note_profile": "",
        "shopify_store": "https://0shhwt-xp.myshopify.com",
        "instagram": "https://www.instagram.com/maru_update/",
        "threads": "https://www.threads.net/@maru_update",
        "study_form": "",
    },
    "embeds": {"note_html_path": "embeds/note_embeds.html", "shopify_html_path": "embeds/shopify_buy_button.html"},
    "market": {
        "period_default": "6mo",
        "items": [
            {"name": "日経平均", "ticker_candidates": ["^N225"], "kind": "index"},
            {"name": "ドル円", "ticker_candidates": ["JPY=X"], "kind": "fx"},
            {"name": "日本10年債利回り", "ticker_candidates": ["^JP10Y", "^JPN10Y", "JP10Y=RR", "236A.T"], "kind": "yield_or_bond"},
        ],
    },
}


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    out = DEFAULT_CONFIG.copy()
    for k in ("site", "links", "embeds", "market"):
        out[k] = {**DEFAULT_CONFIG.get(k, {}), **(cfg.get(k, {}) or {})}
    # itemsは丸ごと置換
    items = (cfg.get("market", {}) or {}).get("items", None)
    if isinstance(items, list) and items:
        out["market"]["items"] = items
    return out


CFG = load_config()


# =========================
# Page config
# =========================
st.set_page_config(
    page_title=CFG["site"]["title"],
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Load CSS
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def safe_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://" + url


def img_to_data_uri(p: Path) -> str:
    b = p.read_bytes()
    ext = p.suffix.lower().replace(".", "")
    mime = "png" if ext in ("png",) else "jpeg"
    encoded = base64.b64encode(b).decode("ascii")
    return f"data:image/{mime};base64,{encoded}"


ICON_URI = img_to_data_uri(ICON_PATH) if ICON_PATH.exists() else ""


# =========================
# yfinance helpers
# =========================
@st.cache_data(ttl=60 * 10, show_spinner=False)
def yf_download_one(ticker: str, period: str) -> pd.DataFrame:
    # group_by='column' でもMultiIndexが返る場合があるので、後段で必ず整形する
    df = yf.download(
        tickers=ticker,
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )
    if df is None or len(df) == 0:
        return pd.DataFrame()

    # index -> Date
    df = df.reset_index()

    # MultiIndex columns -> flat
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    # normalize Date column name
    if "Date" not in df.columns and "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})

    # Keep required
    keep = [c for c in ["Date", "Close", "Open", "High", "Low", "Volume"] if c in df.columns]
    df = df[keep].copy()
    return df


def pick_first_working_ticker(candidates: List[str], period: str) -> Tuple[str, pd.DataFrame]:
    for t in candidates:
        df = yf_download_one(t, period)
        if not df.empty and "Close" in df.columns and df["Close"].notna().any():
            return t, df
    return candidates[-1] if candidates else "", pd.DataFrame()


def last_and_delta(df: pd.DataFrame) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    if df.empty or "Close" not in df.columns:
        return None, None, None
    s = df["Close"].dropna()
    if len(s) == 0:
        return None, None, None
    last = float(s.iloc[-1].item() if hasattr(s.iloc[-1], "item") else s.iloc[-1])
    if len(s) == 1:
        return last, None, None
    prev = float(s.iloc[-2].item() if hasattr(s.iloc[-2], "item") else s.iloc[-2])
    d = last - prev
    pct = (d / prev) * 100 if prev != 0 else None
    return last, d, pct


def format_value(kind: str, value: Optional[float]) -> str:
    if value is None:
        return "—"
    if kind == "fx":
        return f"{value:,.2f}"
    if kind == "yield_or_bond":
        # 利回りっぽい値なら % として扱う（0〜20 を想定）
        if 0 <= value <= 20:
            return f"{value:.2f}%"
        return f"{value:,.2f}"
    # index / default
    return f"{value:,.2f}"


def format_delta(kind: str, delta: Optional[float], pct: Optional[float]) -> str:
    if delta is None or pct is None:
        return ""
    # kindによる丸め
    if kind == "yield_or_bond" and 0 <= abs(pct) <= 200:
        # 表示は小さめに
        return f"{delta:+.2f}  ({pct:+.2f}%)"
    return f"{delta:+.2f}  ({pct:+.2f}%)"


def sparkline_svg(series: pd.Series, width: int = 320, height: int = 92) -> str:
    s = series.dropna().astype(float)
    if len(s) < 2:
        return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"></svg>'

    y = s.values
    ymin, ymax = float(np.min(y)), float(np.max(y))
    if ymax - ymin < 1e-9:
        ymax = ymin + 1e-9

    xs = np.linspace(0, width, num=len(y))
    # invert y: high at top
    ys = (1 - (y - ymin) / (ymax - ymin)) * (height - 8) + 4

    pts = " ".join(f"{x:.1f},{yy:.1f}" for x, yy in zip(xs, ys))
    # fill under line
    fill_pts = pts + f" {width:.1f},{height:.1f} 0.0,{height:.1f}"

    return f"""
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <polyline points="{fill_pts}" fill="rgba(255,255,255,0.10)" stroke="none"/>
  <polyline points="{pts}" fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
""".strip()


def read_embed_html(rel_path: str) -> str:
    p = (BASE_DIR / rel_path).resolve()
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


# =========================
# UI builders (HTML)
# =========================
def quick_card(title: str, subtitle: str, url: str, ico: str) -> str:
    if url:
        return f"""
<a class="quick-card" href="{url}" target="_blank" rel="noopener">
  <div class="quick-ico">{ico}</div>
  <div>
    <div class="quick-t">{title}</div>
    <div class="quick-s">{subtitle}</div>
  </div>
</a>
""".strip()
    return f"""
<div class="quick-card" style="opacity:.55;">
  <div class="quick-ico">{ico}</div>
  <div>
    <div class="quick-t">{title}</div>
    <div class="quick-s">未設定</div>
  </div>
</div>
""".strip()


def market_card(name: str, val: str, delta: str, spark_svg: str) -> str:
    delta_html = f'<div class="mdelta">{delta}</div>' if delta else '<div class="mdelta" style="opacity:.0;">&nbsp;</div>'
    return f"""
<div class="mcard">
  <div class="mname">{name}</div>
  <div class="mval">{val}</div>
  {delta_html}
  <div class="spark">{spark_svg}</div>
</div>
""".strip()


# =========================
# Main
# =========================
site = CFG["site"]
links = CFG["links"]
market = CFG["market"]

# Period (fixed to match the mock)
period_key = "6M"
period = "6mo"

# Build quick cards (top row)
quick_html = "\n".join(
    [
        quick_card("note", "記事", safe_url(links.get("note_profile")) or "https://note.com/", "📝"),
        quick_card("My Shop", "オンラインショップ", safe_url(links.get("shopify_store")), "🛍️"),
        quick_card("Instagram", "フォローする", safe_url(links.get("instagram")), "📸"),
        quick_card("Threads", "スレッズ", safe_url(links.get("threads")), "🧵"),
        quick_card("勉強会申込", "勉強会エントリー", safe_url(links.get("study_form")), "🗓️"),
    ]
)

# Fetch market data (3 cards)
cards_html = []
used_tickers = []
for it in market.get("items", [])[:3]:
    candidates = it.get("ticker_candidates", [])
    kind = it.get("kind", "index")
    ticker, df = pick_first_working_ticker(candidates, period=period)
    used_tickers.append(ticker)

    last, d, pct = last_and_delta(df)
    val_txt = format_value(kind, last)
    delta_txt = format_delta(kind, d, pct)

    spark = ""
    if not df.empty and "Close" in df.columns:
        spark = sparkline_svg(df["Close"].tail(120))
    cards_html.append(market_card(it.get("name", ticker), val_txt, delta_txt, spark))

cards_html_joined = "\n".join(cards_html)

# Tabs (mock style; non-functional on purpose)
tabs_html = """
<div class="market-tabs">
  <div class="market-tab active">日本株</div>
  <div class="market-tab">決算</div>
  <div class="market-tab">マクロ</div>
  <div class="market-tab">指数</div>
</div>
""".strip()

period_buttons_html = f"""
<div class="period-row">
  <div class="period-btn {'active' if period_key=='1M' else ''}">1M</div>
  <div class="period-btn {'active' if period_key=='6M' else ''}">6M</div>
  <div class="period-btn {'active' if period_key=='1Y' else ''}">1Y</div>
  <div class="period-btn {'active' if period_key=='5Y' else ''}">5Y</div>
</div>
""".strip()

# Memo box (Streamlit input overlaid below)
st.markdown(
    f"""
<div class="hero-wrap">
  <div class="hero-inner">
    <div class="avatar">{f'<img src="{ICON_URI}" />' if ICON_URI else ''}</div>
    <div class="hero-text">
      <div class="hero-title">{site.get("title","")}</div>
      <div class="hero-sub">{site.get("tagline","")}</div>
      <div class="hero-en">Invest &amp; Learn with Maru.</div>
    </div>
  </div>

  <div class="quick-row">
    {quick_html}
  </div>
</div>

<div class="market-wrap">
  <div class="market-panel">
    {tabs_html}
    <div class="market-row">
      {cards_html_joined}
    </div>
    {period_buttons_html}
    <div class="memo">
      <div class="memo-title">今日のメモ：</div>
      <div class="memo-line"></div>
      <div class="small" style="opacity:.8;">（ここに一言メモを書けるようにしてるよ）</div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# Note embeds
st.markdown('<div class="embed-wrap"><div class="embed-pad">', unsafe_allow_html=True)
note_html = read_embed_html(CFG["embeds"]["note_html_path"])
if note_html:
    components.html(note_html, height=1200, scrolling=True)
else:
    st.info("note埋め込み: embeds/note_embeds.html を用意してね")
st.markdown("</div></div>", unsafe_allow_html=True)

# Shopify
st.markdown('<div class="embed-wrap"><div class="embed-pad">', unsafe_allow_html=True)
shop_html = read_embed_html(CFG["embeds"]["shopify_html_path"])
if shop_html:
    components.html(shop_html, height=820, scrolling=True)
else:
    st.info("Shopify埋め込み: embeds/shopify_buy_button.html を用意してね")
st.markdown("</div></div>", unsafe_allow_html=True)

