from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import yaml


# =========================
# Paths
# =========================
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
EMBEDS_DIR = BASE_DIR / "embeds"
CONFIG_PATH = BASE_DIR / "content_config.yaml"

ICON_PATH = ASSETS_DIR / "icon.png"
CSS_PATH = ASSETS_DIR / "style.css"


# =========================
# Config Loading
# =========================
DEFAULT_CONFIG: Dict[str, Any] = {
    "site": {"title": "まる | 日本株の学びと記録", "tagline": "投資と学びの記録", "handle": "maru_update"},
    "links": {},
    "embeds": {"note_html_path": "embeds/note_embeds.html", "shopify_html_path": "embeds/shopify_buy_button.html"},
    "market": {
        "period_default": "6mo",
        "items": [
            {"name": "日経平均", "ticker_candidates": ["^N225"], "kind": "index"},
            {"name": "ドル円", "ticker_candidates": ["JPY=X"], "kind": "fx"},
        ],
    },
}

def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG
    try:
        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return DEFAULT_CONFIG
    
    out = DEFAULT_CONFIG.copy()
    for k in ("site", "links", "embeds", "market"):
        out[k] = {**DEFAULT_CONFIG.get(k, {}), **(cfg.get(k, {}) or {})}
    
    # itemsリストがあれば上書き
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
    if not url: return ""
    if url.startswith("http"): return url
    return "https://" + url

def img_to_data_uri(p: Path) -> str:
    if not p.exists(): return ""
    b = p.read_bytes()
    ext = p.suffix.lower().replace(".", "")
    mime = "png" if ext == "png" else "jpeg"
    encoded = base64.b64encode(b).decode("ascii")
    return f"data:image/{mime};base64,{encoded}"

ICON_URI = img_to_data_uri(ICON_PATH)


# =========================
# Data Logic
# =========================
@st.cache_data(ttl=60 * 15, show_spinner=False)
def get_market_data(ticker: str, period: str) -> pd.DataFrame:
    try:
        df = yf.download(
            tickers=ticker,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False, # 単一取得なのでFalseで安定させる
        )
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    # 整形: indexをDate列に
    df = df.reset_index()
    
    # MultiIndexカラムの解消 (yfinance v0.2系対応)
    if isinstance(df.columns, pd.MultiIndex):
        # ('Close', 'AAPL') -> 'Close' のように単純化
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    # カラム名統一
    if "Date" not in df.columns and "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})

    if "Close" not in df.columns:
        return pd.DataFrame()

    return df[["Date", "Close"]].dropna()

def pick_valid_ticker(candidates: List[str], period: str) -> Tuple[str, pd.DataFrame]:
    for t in candidates:
        df = get_market_data(t, period)
        if not df.empty and len(df) > 1:
            return t, df
    return (candidates[0] if candidates else ""), pd.DataFrame()

def calc_metrics(df: pd.DataFrame) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    if df.empty: return None, None, None
    
    # 最新と前回
    s = df["Close"].values
    last = float(s[-1])
    prev = float(s[-2]) if len(s) >= 2 else last
    
    delta = last - prev
    pct = (delta / prev) * 100 if prev != 0 else 0.0
    return last, delta, pct

def format_price(kind: str, val: float) -> str:
    if val is None: return "—"
    if kind == "fx": return f"{val:,.2f}"
    return f"{val:,.0f}" # 指数などは整数に近い方が見やすい場合が多いが、好みで.2fに

def sparkline_svg(series: pd.Series, height: int = 60) -> str:
    """レスポンシブ対応のためのSVG生成（widthを指定しない）"""
    data = series.values
    if len(data) < 2: return ""
    
    min_v, max_v = np.min(data), np.max(data)
    if max_v == min_v: max_v += 1e-5

    # SVGの内部座標系 (横幅1000として正規化)
    view_w = 1000
    xs = np.linspace(0, view_w, len(data))
    
    # Y座標の計算 (上端がmax_v)
    # マージンを少しとる (height-4)
    ys = (1 - (data - min_v) / (max_v - min_v)) * (height - 10) + 5
    
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    fill_points = f"{points} {view_w},{height} 0,{height}"

    return f"""
<svg viewBox="0 0 {view_w} {height}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg" class="spark-svg">
  <defs>
    <linearGradient id="grad" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="white" stop-opacity="0.2"/>
      <stop offset="100%" stop-color="white" stop-opacity="0.0"/>
    </linearGradient>
  </defs>
  <polyline points="{fill_points}" fill="url(#grad)" stroke="none"/>
  <polyline points="{points}" fill="none" stroke="rgba(255,255,255,0.9)" stroke-width="3" vector-effect="non-scaling-stroke"/>
</svg>
""".strip()


# =========================
# UI Component Builders
# =========================
def quick_card(title: str, subtitle: str, url: str, ico: str) -> str:
    # URLがない場合は非表示にするか、グレーアウトする
    if not url:
        return ""
    return f"""
<a class="quick-card" href="{url}" target="_blank" rel="noopener">
  <div class="quick-ico">{ico}</div>
  <div class="quick-info">
    <div class="quick-t">{title}</div>
    <div class="quick-s">{subtitle}</div>
  </div>
</a>
"""

def market_card(name: str, val_str: str, delta: float, pct: float, spark_html: str) -> str:
    d_sign = "+" if delta > 0 else ""
    color_class = "up" if delta >= 0 else "down"
    return f"""
<div class="mcard">
  <div class="mname">{name}</div>
  <div class="mval">{val_str}</div>
  <div class="mdelta {color_class}">
    {d_sign}{delta:,.2f} ({d_sign}{pct:.2f}%)
  </div>
  <div class="spark-wrap">{spark_html}</div>
</div>
"""

def read_html(rel_path: str) -> str:
    p = BASE_DIR / rel_path
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


# =========================
# Main Layout
# =========================

# 1. Header & Hero
site = CFG["site"]
links = CFG["links"]

# Quick Links HTML
q_links = [
    quick_card("note", "記事を読む", safe_url(links.get("note_profile")), "📝"),
    quick_card("My Shop", "ストアを見る", safe_url(links.get("shopify_store")), "🛍️"),
    quick_card("Instagram", "フォロー", safe_url(links.get("instagram")), "📸"),
    quick_card("Threads", "スレッズ", safe_url(links.get("threads")), "🧵"),
    quick_card("勉強会", "エントリー", safe_url(links.get("study_form")), "🗓️"),
]
q_html = "".join([q for q in q_links if q])

st.markdown(
    f"""
<div class="hero-container">
    <div class="profile-row">
        <div class="avatar"><img src="{ICON_URI}" /></div>
        <div class="profile-text">
            <h1 class="hero-title">{site.get("title")}</h1>
            <p class="hero-sub">{site.get("tagline")}</p>
        </div>
    </div>
    <div class="quick-grid">
        {q_html}
    </div>
</div>
""",
    unsafe_allow_html=True,
)


# 2. Market Section (Simplified)
# 固定期間 "6mo" で取得
items = CFG["market"].get("items", [])
cards = []

for item in items:
    name = item["name"]
    candidates = item["ticker_candidates"]
    kind = item.get("kind", "index")
    
    ticker, df = pick_valid_ticker(candidates, period="6mo")
    
    val, d, pct = calc_metrics(df)
    
    if val is not None:
        val_s = format_price(kind, val)
        # スパークラインは直近40営業日分くらいを表示
        svg = sparkline_svg(df["Close"].tail(60))
        cards.append(market_card(name, val_s, d, pct, svg))

# カードをGrid表示
st.markdown('<div class="market-grid">', unsafe_allow_html=True)
# Streamlitのcolumnsを使うと余白調整が難しいので、CSS Grid用のHTMLを一塊で書く
st.markdown("\n".join(cards), unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)


# 3. Memo Input
st.markdown(
    """
<div class="memo-box">
    <div class="memo-label">今日のメモ</div>
    <div class="memo-sub">（ここに自由にメモを残せます）</div>
</div>
""",
    unsafe_allow_html=True
)


# 4. Content Area (Note & Shop)
st.markdown("<div class='content-spacer'></div>", unsafe_allow_html=True)

col_note, col_shop = st.columns([1, 1], gap="medium")

with col_note:
    st.markdown("### 📝 New Articles")
    note_html = read_html(CFG["embeds"]["note_html_path"])
    if note_html:
        # divで囲ってスタイル調整しやすくする
        components.html(f'<div class="note-container">{note_html}</div>', height=1000, scrolling=True)
    else:
        st.info("embeds/note_embeds.html がありません")

with col_shop:
    st.markdown("### 🛍️ Official Store")
    shop_html = read_html(CFG["embeds"]["shopify_html_path"])
    if shop_html:
        # Shopifyは見切れやすいので少し高さを確保
        components.html(f'<div class="shop-container">{shop_html}</div>', height=1000, scrolling=True)
    else:
        st.info("embeds/shopify_buy_button.html がありません")
