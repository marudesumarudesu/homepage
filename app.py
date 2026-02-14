import streamlit as st
import yfinance as yf
import pandas as pd
import yaml
from pathlib import Path
import streamlit.components.v1 as components
from PIL import Image
import plotly.express as px

# -----------------
# Config
# -----------------
DEFAULT_CONFIG = {
    "site": {
        "title": "まる | 日本株の学びと記録",
        "tagline": "株式投資と学びの記録をお届けします",
        "handle": "maru_update",
    },
    "links": {
        "note_profile": "",
        "shopify_store": "https://0shhwt-xp.myshopify.com",
        "instagram": "https://www.instagram.com/maru_update/",
        "threads": "https://www.threads.net/@maru_update",
        "study_form": "",
    },
    "embeds": {
        "shopify_html_path": "embeds/shopify_buy_button.html",
        "note_html_path": "embeds/note_embeds.html",
    },
    "market": {
        "period_default": "6mo",
        "items": [
            {"name": "日経平均", "ticker": "^N225"},
            {"name": "ドル円", "ticker": "JPY=X"},
            {"name": "日本10年（代替：国債ETF）", "ticker": "236A.T"},
        ],
    },
}

def load_config(path="content_config.yaml"):
    p = Path(path)
    if not p.exists():
        return DEFAULT_CONFIG
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out = DEFAULT_CONFIG.copy()
    for k in ("site", "links", "embeds", "market"):
        out[k] = {**DEFAULT_CONFIG.get(k, {}), **(cfg.get(k, {}) or {})}
    if isinstance(cfg.get("market", {}).get("items", None), list) and cfg["market"]["items"]:
        out["market"]["items"] = cfg["market"]["items"]
    return out

CFG = load_config()

st.set_page_config(
    page_title=CFG["site"]["title"],
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

css_path = Path("assets/style.css")
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

icon_path = Path("assets/icon.png")
ICON = Image.open(icon_path) if icon_path.exists() else None

def safe_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://" + url

@st.cache_data(ttl=60*10, show_spinner=False)
def yf_series(ticker: str, period: str = "6mo") -> pd.DataFrame:
    df = yf.download(tickers=ticker, period=period, interval="1d", auto_adjust=True, progress=False, threads=True)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.reset_index()
    if "Date" not in df.columns and "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})
    return df

def last_close_delta(df: pd.DataFrame):
    if df is None or df.empty or "Close" not in df.columns:
        return None, None, None
    s = df["Close"].dropna()
    if len(s) < 2:
        v = float(s.iloc[-1]) if len(s) else None
        return v, None, None
    last = float(s.iloc[-1])
    prev = float(s.iloc[-2])
    d = last - prev
    pct = (d / prev) * 100 if prev != 0 else None
    return last, d, pct

def sparkline(df: pd.DataFrame, height=90):
    if df.empty:
        return None
    fig = px.line(df, x="Date", y="Close")
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig

def render_embed_html(path: str, height: int = 900):
    p = Path(path)
    if not p.exists():
        st.info(f"埋め込みHTMLが見つからないよ：{path}")
        return
    html = p.read_text(encoding="utf-8")
    wrapped = f"""<div class="embed-wrap"><div class="embed-pad">{html}</div></div>"""
    components.html(wrapped, height=height, scrolling=True)

# -----------------
# Top (Hero)
# -----------------
c1, c2 = st.columns([1, 6], vertical_alignment="center")
with c1:
    if ICON:
        st.image(ICON, width=86)
with c2:
    st.markdown(
        f"""
        <div class="hero">
          <div>
            <div class="hero-title">{CFG["site"]["title"]}</div>
            <div class="hero-sub">{CFG["site"]["tagline"]}</div>
            <div class="small">@{CFG["site"]["handle"]} / 日本株・指数・学び</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

tabs = st.tabs(["Home", "Market", "note", "Shop", "Links/勉強会"])

# -----------------
# Home
# -----------------
with tabs[0]:
    links = CFG["links"]
    quick = [
        ("note", "記事", safe_url(links.get("note_profile")) or "https://note.com/", "n"),
        ("Shopify", "ショップ", safe_url(links.get("shopify_store")), "s"),
        ("Instagram", "@"+CFG["site"]["handle"], safe_url(links.get("instagram")), "i"),
        ("Threads", "@"+CFG["site"]["handle"], safe_url(links.get("threads")), "t"),
        ("勉強会", "申込", safe_url(links.get("study_form")), "e"),
    ]

    st.markdown('<div class="quick-grid">', unsafe_allow_html=True)
    for title, sub, url, ico in quick:
        if url:
            st.markdown(
                f"""
                <a class="quick" href="{url}" target="_blank">
                  <div class="quick-ico">{ico.upper()}</div>
                  <div>
                    <div class="quick-title">{title}</div>
                    <div class="quick-sub">{sub}</div>
                  </div>
                </a>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="quick" style="opacity:.55;">
                  <div class="quick-ico">{ico.upper()}</div>
                  <div>
                    <div class="quick-title">{title}</div>
                    <div class="quick-sub">未設定</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)

    # Market panel (mock寄せ)
    items = CFG["market"]["items"]
    period = CFG["market"].get("period_default", "6mo")
    st.markdown(
        """
        <div class="market-panel">
          <div class="market-tabs">
            <div class="market-tab">日本株</div>
            <div class="market-tab">決算</div>
            <div class="market-tab">マクロ</div>
            <div class="market-tab">指数</div>
          </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    for col, it in zip(cols, items[:3]):
        with col:
            df = yf_series(it["ticker"], period=period)
            last, d, pct = last_close_delta(df)
            last_txt = "—" if last is None else f"{last:,.2f}"
            delta_txt = "" if pct is None else f"{d:+.2f} ({pct:+.2f}%)"
            st.markdown(
                f"""
                <div class="market-card">
                  <div class="market-name">{it["name"]}</div>
                  <div class="market-val">{last_txt}</div>
                  <div class="market-delta">{delta_txt}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            fig = sparkline(df.tail(90), height=90)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    st.markdown('<div class="card"><div class="card-title">今日のメモ</div>', unsafe_allow_html=True)
    st.text_input("（自分用の一言メモ。公開するなら後で保存機能も付けられるよ）", value="", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    st.subheader("最新note（埋め込み）")
    render_embed_html(CFG["embeds"]["note_html_path"], height=1100)

# -----------------
# Market
# -----------------
with tabs[1]:
    st.subheader("Market Dashboard")
    period = st.selectbox("表示期間", ["1mo", "3mo", "6mo", "1y", "5y"], index=2)
    for it in CFG["market"]["items"]:
        df = yf_series(it["ticker"], period=period)
        if df.empty:
            st.markdown(f'<div class="card"><div class="card-title">{it["name"]}</div>データ取得失敗（{it["ticker"]}）</div>', unsafe_allow_html=True)
            continue
        fig = px.line(df, x="Date", y="Close", title=f'{it["name"]}（{it["ticker"]}）')
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

# -----------------
# note
# -----------------
with tabs[2]:
    st.subheader("note（埋め込み）")
    st.caption("追加は embeds/note_embeds.html に iframe を増やすだけ。")
    render_embed_html(CFG["embeds"]["note_html_path"], height=1300)

# -----------------
# Shop
# -----------------
with tabs[3]:
    st.subheader("Shopify（Buy Button）")
    st.caption("差し替えは embeds/shopify_buy_button.html を貼り替えるだけ。")
    render_embed_html(CFG["embeds"]["shopify_html_path"], height=900)

# -----------------
# Links / Study
# -----------------
with tabs[4]:
    st.subheader("Links / 勉強会")
    insta = safe_url(CFG["links"].get("instagram"))
    th = safe_url(CFG["links"].get("threads"))
    form = safe_url(CFG["links"].get("study_form"))

    st.markdown('<div class="card"><div class="card-title">SNS</div>', unsafe_allow_html=True)
    st.write(f"- Instagram：{insta if insta else '（未設定）'}")
    st.write(f"- Threads：{th if th else '（未設定）'}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    st.markdown('<div class="card"><div class="card-title">勉強会フォーム</div>', unsafe_allow_html=True)
    if form:
        st.link_button("勉強会に申し込む", form)
    else:
        st.warning("フォームURLは content_config.yaml の links.study_form に貼るだけで反映されるよ。")
    st.markdown("</div>", unsafe_allow_html=True)
