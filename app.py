import streamlit as st
import yfinance as yf
import pandas as pd
import yaml
from pathlib import Path
import streamlit.components.v1 as components
from PIL import Image

DEFAULT_CONFIG = {
    "site": {
        "title": "まる | 日本株の学びと記録",
        "tagline": "株式投資と学びの記録をお届けします",
        "handle": "maru_update",
        "accent": "#0E6A6B",
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
            {"name": "TOPIX", "ticker": "^TOPX"},
            {"name": "ドル円", "ticker": "JPY=X"},
            {"name": "日本国債(7-10年)ETF（利回りの代替）", "ticker": "236A.T"},
        ],
    },
}

def load_config(path: str = "content_config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        return DEFAULT_CONFIG
    try:
        cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return DEFAULT_CONFIG

    out = DEFAULT_CONFIG.copy()
    for k in ("site", "links", "embeds", "market"):
        out[k] = {**DEFAULT_CONFIG.get(k, {}), **(cfg.get(k, {}) or {})}

    if isinstance(cfg.get("market", {}).get("items", None), list) and cfg["market"]["items"]:
        out["market"]["items"] = cfg["market"]["items"]
    return out

CFG = load_config()

st.set_page_config(page_title=CFG["site"]["title"], page_icon="📈", layout="wide")

css_path = Path("assets/style.css")
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

icon_path = Path("assets/icon.png")
ICON = None
if icon_path.exists():
    try:
        ICON = Image.open(icon_path)
    except Exception:
        ICON = None

def safe_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://" + url

def pill(title: str, subtitle: str, url: str):
    url = safe_url(url)
    if url:
        st.markdown(
            f"""<a class="pill" href="{url}" target="_blank">
                    <b>{title}</b><span>{subtitle}</span>
                  </a>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""<span class="pill" style="opacity:.55; cursor:not-allowed;">
                    <b>{title}</b><span>{subtitle}</span>
                  </span>""",
            unsafe_allow_html=True,
        )

@st.cache_data(ttl=60*10, show_spinner=False)
def yf_series(ticker: str, period: str = "6mo") -> pd.DataFrame:
    df = yf.download(
        tickers=ticker,
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
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
    delta = last - prev
    pct = (delta / prev) * 100 if prev != 0 else None
    return last, delta, pct

def render_embed_html(path: str, height: int = 720):
    p = Path(path)
    if not p.exists():
        st.info(f"埋め込みHTMLが見つからないよ：{path}")
        return
    html = p.read_text(encoding="utf-8")
    wrapped = f"""<div class="embed-wrap"><div class="embed-pad">{html}</div></div>"""
    components.html(wrapped, height=height, scrolling=True)

# ---- hero ----
left, right = st.columns([1, 5], vertical_alignment="center")
with left:
    if ICON is not None:
        st.image(ICON, width=84)
with right:
    st.markdown(
        f"""<div class="hero">
                <div>
                  <div class="title">{CFG["site"]["title"]}</div>
                  <div class="tagline">{CFG["site"]["tagline"]}</div>
                  <div class="small-muted">@{CFG["site"]["handle"]} / 日本株・指数・学び</div>
                </div>
              </div>""",
        unsafe_allow_html=True,
    )

st.write("")

page = st.sidebar.radio("メニュー", ["Home", "Market", "note", "Shop", "Links / 勉強会"], index=0)

if page == "Home":
    st.subheader("入口")
    st.markdown('<div class="pills">', unsafe_allow_html=True)
    pill("note", "記事を読む", CFG["links"].get("note_profile", "") or "https://note.com/")
    pill("Shopify", "ショップ", CFG["links"].get("shopify_store", ""))
    pill("Instagram", "@" + CFG["site"]["handle"], CFG["links"].get("instagram", ""))
    pill("Threads", "@" + CFG["site"]["handle"], CFG["links"].get("threads", ""))
    pill("勉強会申込", "フォーム", CFG["links"].get("study_form", ""))
    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    colA, colB = st.columns([2, 1], gap="large")
    with colA:
        st.markdown('<div class="card"><div class="card-title">このサイトでできること</div>', unsafe_allow_html=True)
        st.markdown(
            "- note / Shop / SNS / 勉強会への導線を、迷わずまとめて見れる\n"
            "- 日経平均・TOPIX・ドル円などの動きを、軽くチェックできる\n"
            "- 日本株に特化した個人サイトだと一目で分かる設計"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with colB:
        st.markdown('<div class="card"><div class="card-title">更新しやすさ</div>', unsafe_allow_html=True)
        st.markdown(
            "リンクや埋め込みは **content_config.yaml と embeds/ のHTML** を編集するだけ。\n"
            "コードを触らなくても追加しやすい形にしてあるよ。"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    st.subheader("今日の指数（さくっと）")

    period = CFG["market"].get("period_default", "6mo")
    items = CFG["market"].get("items", [])
    top_items = items[:3] if len(items) >= 3 else items
    cols = st.columns(len(top_items)) if top_items else []
    for col, it in zip(cols, top_items):
        with col:
            df = yf_series(it["ticker"], period=period)
            last, delta, pct = last_close_delta(df)
            if last is None:
                st.metric(it["name"], "—")
            else:
                if pct is None:
                    st.metric(it["name"], f"{last:,.2f}")
                else:
                    st.metric(it["name"], f"{last:,.2f}", f"{delta:+.2f} ({pct:+.2f}%)")

    st.caption("※無料データ（Yahoo Finance / yfinance）なので遅延や欠損があり得るよ。")

    st.divider()
    st.subheader("最新note（埋め込み）")
    with st.expander("表示する", expanded=True):
        render_embed_html(CFG["embeds"]["note_html_path"], height=980)

elif page == "Market":
    st.subheader("Market Dashboard")
    st.caption("日経・TOPIX・ドル円などを、同じ画面でチェック。")

    period = st.selectbox("表示期間", ["1mo", "3mo", "6mo", "1y", "5y"], index=2)
    items = CFG["market"].get("items", [])
    if not items:
        st.warning("market.items が空だよ。content_config.yaml を見てね。")
        st.stop()

    first3 = items[:3]
    cols = st.columns(3, gap="medium")
    for i in range(3):
        if i >= len(first3):
            break
        it = first3[i]
        with cols[i]:
            df = yf_series(it["ticker"], period=period)
            last, delta, pct = last_close_delta(df)
            if last is None:
                st.metric(it["name"], "—")
            else:
                if pct is None:
                    st.metric(it["name"], f"{last:,.2f}")
                else:
                    st.metric(it["name"], f"{last:,.2f}", f"{delta:+.2f} ({pct:+.2f}%)")

    st.write("")
    import plotly.express as px

    for it in items:
        df = yf_series(it["ticker"], period=period)
        if df.empty:
            st.markdown(
                f'<div class="card"><div class="card-title">{it["name"]}</div>'
                f'データ取得に失敗したみたい（{it["ticker"]}）。</div>',
                unsafe_allow_html=True,
            )
            continue

        fig = px.line(df, x="Date", y="Close", title=f'{it["name"]}（{it["ticker"]}）')
        fig.update_layout(height=330, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

    st.info("日本10年債の“利回りそのもの”を出す場合は別データソース追加が必要。今はyfinanceで取れる日本国債ETFを代替にしてるよ。")

elif page == "note":
    st.subheader("note（埋め込み）")
    st.caption("追加したいときは embeds/note_embeds.html に iframe を増やすだけでOK。")
    render_embed_html(CFG["embeds"]["note_html_path"], height=1200)

elif page == "Shop":
    st.subheader("Shopify（商品表示）")
    st.caption("差し替えは embeds/shopify_buy_button.html を貼り替えるだけ。")
    render_embed_html(CFG["embeds"]["shopify_html_path"], height=860)

else:
    st.subheader("Links / 勉強会")

    st.markdown('<div class="card"><div class="card-title">SNS</div>', unsafe_allow_html=True)
    insta = safe_url(CFG["links"].get("instagram", ""))
    th = safe_url(CFG["links"].get("threads", ""))
    st.write(f"- Instagram：{insta if insta else '（未設定）'}")
    st.write(f"- Threads：{th if th else '（未設定）'}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    st.markdown('<div class="card"><div class="card-title">勉強会フォーム</div>', unsafe_allow_html=True)
    form = safe_url(CFG["links"].get("study_form", ""))
    if form:
        st.success("申込フォームはこちら：")
        st.link_button("勉強会に申し込む", form)
        st.caption("フォームURL変更は content_config.yaml の links.study_form を更新してね。")
    else:
        st.warning("まだフォームURLが入ってないよ。content_config.yaml の links.study_form に貼るだけで反映される。")
    st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    st.markdown('<div class="card"><div class="card-title">管理メモ</div>', unsafe_allow_html=True)
    st.markdown(
        "- リンク追加：content_config.yaml\n"
        "- note追加：embeds/note_embeds.html に iframe を追加\n"
        "- Shopify差し替え：embeds/shopify_buy_button.html を貼り替え"
    )
    st.markdown("</div>", unsafe_allow_html=True)
