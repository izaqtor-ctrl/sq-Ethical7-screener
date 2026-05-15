"""
Halal Stock Screener — Streamlit App
Screens individual stocks or a list of tickers against 6 major Islamic finance frameworks.
"""

import streamlit as st
from halal_screener import screen_ticker

# ─── Page Config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Halal Stock Screener",
    page_icon="🌙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:wght@400;600;700&family=DM+Sans:wght@300;400;500&display=swap');

/* Global */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

h1, h2, h3 {
    font-family: 'Lora', serif !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #0e1e12;
    border-right: 1px solid #1e3a22;
}
section[data-testid="stSidebar"] * {
    color: #c8dfc9 !important;
}

/* Main background */
.stApp {
    background-color: #0a1a0d;
    color: #d6e8d7;
}

/* Header strip */
.app-header {
    background: linear-gradient(135deg, #112214 0%, #1a3820 100%);
    border: 1px solid #2a4a2e;
    border-radius: 16px;
    padding: 32px 40px;
    margin-bottom: 28px;
    text-align: center;
}
.app-header h1 {
    font-family: 'Lora', serif;
    color: #c8a84b !important;
    font-size: 2.4rem;
    margin: 0;
}
.app-header p {
    color: #8aad8b;
    margin: 8px 0 0 0;
    font-size: 1rem;
}

/* Verdict badges */
.badge-halal {
    display: inline-block;
    background: linear-gradient(135deg, #1a4a1e, #204d24);
    color: #7dda82;
    border: 1px solid #3a7a3e;
    border-radius: 20px;
    padding: 6px 18px;
    font-weight: 600;
    font-size: 0.85rem;
    letter-spacing: 0.5px;
}
.badge-avoid {
    display: inline-block;
    background: linear-gradient(135deg, #4a1a1a, #4d2020);
    color: #da7d7d;
    border: 1px solid #7a3a3a;
    border-radius: 20px;
    padding: 6px 18px;
    font-weight: 600;
    font-size: 0.85rem;
    letter-spacing: 0.5px;
}
.badge-review {
    display: inline-block;
    background: linear-gradient(135deg, #4a3a1a, #4d3f20);
    color: #dab97d;
    border: 1px solid #7a6a3a;
    border-radius: 20px;
    padding: 6px 18px;
    font-weight: 600;
    font-size: 0.85rem;
    letter-spacing: 0.5px;
}

/* Ticker card */
.ticker-card {
    background: #0e1e12;
    border: 1px solid #1e3a22;
    border-radius: 14px;
    padding: 22px 26px;
    margin-bottom: 16px;
}
.ticker-name {
    font-family: 'Lora', serif;
    font-size: 1.3rem;
    color: #c8d8c8;
    font-weight: 600;
}
.ticker-meta {
    color: #6a8a6a;
    font-size: 0.82rem;
    margin-top: 4px;
}
.ticker-summary {
    color: #9ab09a;
    font-size: 0.9rem;
    margin-top: 10px;
    line-height: 1.5;
    border-left: 3px solid #2a4a2e;
    padding-left: 12px;
}

/* Standard check row */
.std-pass { color: #7dda82; font-weight: 500; }
.std-fail { color: #da7d7d; font-weight: 500; }
.std-review { color: #dab97d; font-weight: 500; }
.std-na { color: #6a8a6a; }

/* Check detail rows */
.check-row {
    display: flex;
    align-items: center;
    padding: 7px 0;
    border-bottom: 1px solid #1a2e1e;
    font-size: 0.87rem;
}
.check-row:last-child { border-bottom: none; }
.check-icon { width: 28px; flex-shrink: 0; }
.check-name { flex: 1; color: #9ab09a; }
.check-value { color: #c8d8c8; margin-right: 12px; font-family: monospace; font-size: 0.83rem; }
.check-thr { color: #6a8a6a; font-size: 0.8rem; }

/* Ratio box */
.ratio-box {
    background: #081208;
    border: 1px solid #162616;
    border-radius: 10px;
    padding: 14px 16px;
    font-size: 0.82rem;
}
.ratio-label { color: #6a8a6a; margin-bottom: 3px; }
.ratio-val { color: #c8d8c8; font-weight: 500; font-family: monospace; }

/* Disclaimer */
.disclaimer {
    background: #0e1e12;
    border: 1px solid #1e3a22;
    border-radius: 10px;
    padding: 14px 18px;
    margin-top: 20px;
    font-size: 0.8rem;
    color: #5a7a5a;
    line-height: 1.5;
}
</style>
""", unsafe_allow_html=True)

# ─── Helper Functions ──────────────────────────────────────────────────────────

def verdict_badge(verdict: str) -> str:
    if verdict == "POTENTIALLY_HALAL":
        return '<span class="badge-halal">✓ Potentially Halal</span>'
    elif verdict == "AVOID":
        return '<span class="badge-avoid">✗ Avoid</span>'
    else:
        return '<span class="badge-review">⚠ Needs Review</span>'


def check_icon(result: str) -> str:
    return {"PASS": "✅", "FAIL": "❌", "REVIEW": "⚠️", "N/A": "—"}.get(result, "—")


def fmt_money(val) -> str:
    if not val:
        return "N/A"
    if val >= 1e12:
        return f"${val/1e12:.2f}T"
    if val >= 1e9:
        return f"${val/1e9:.2f}B"
    if val >= 1e6:
        return f"${val/1e6:.2f}M"
    return f"${val:,.0f}"


def fmt_pct(val) -> str:
    if val is None:
        return "N/A"
    return f"{val*100:.1f}%"


def render_result(result: dict):
    """Render a single ticker result card."""
    if "error" in result:
        st.error(f"**{result['ticker']}** — {result['error']}")
        return

    verdict = result["overall"]
    ticker = result["ticker"]
    company = result["company_name"]
    sector = result["sector"]
    industry = result["industry"]
    summary = result["summary"]
    prohibited = result["prohibited_activities"]
    mkt_cap = fmt_money(result.get("market_cap"))

    # ── Top-level card ────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="ticker-card">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:10px;">
            <div>
                <span class="ticker-name">{ticker}</span>
                &nbsp;&nbsp;<code style="color:#6a8a6a;font-size:0.9rem;">{company}</code>
                <div class="ticker-meta">{sector} · {industry} · {mkt_cap}</div>
            </div>
            <div>{verdict_badge(verdict)}</div>
        </div>
        <div class="ticker-summary">{summary}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Expanded Details (expander) ────────────────────────────────────────────
    with st.expander(f"📋 View full screening details for {ticker}"):

        # Financial ratios at a glance
        st.markdown("#### 📊 Financial Ratios")
        ratios = result.get("ratios", {})
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            st.markdown(f"""
            <div class="ratio-box">
                <div class="ratio-label">Debt / Market Cap</div>
                <div class="ratio-val">{fmt_pct(ratios.get('debt_to_mktcap'))}</div>
            </div>""", unsafe_allow_html=True)
        with r2:
            st.markdown(f"""
            <div class="ratio-box">
                <div class="ratio-label">Debt / Total Assets</div>
                <div class="ratio-val">{fmt_pct(ratios.get('debt_to_assets'))}</div>
            </div>""", unsafe_allow_html=True)
        with r3:
            st.markdown(f"""
            <div class="ratio-box">
                <div class="ratio-label">Cash / Market Cap</div>
                <div class="ratio-val">{fmt_pct(ratios.get('cash_to_mktcap'))}</div>
            </div>""", unsafe_allow_html=True)
        with r4:
            st.markdown(f"""
            <div class="ratio-box">
                <div class="ratio-label">Rec. + Cash / Assets</div>
                <div class="ratio-val">{fmt_pct(ratios.get('receivables_plus_cash_to_assets'))}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # All 6 standards
        st.markdown("#### 📜 Results by Standard")
        std_cols = st.columns(2)

        for i, std in enumerate(result.get("standards", [])):
            col = std_cols[i % 2]
            with col:
                overall_color = {"PASS": "#7dda82", "FAIL": "#da7d7d", "REVIEW": "#dab97d"}.get(std["overall"], "#6a8a6a")
                st.markdown(f"""
                <div style="background:#0e1e12; border:1px solid #1e3a22; border-radius:12px; 
                            padding:16px; margin-bottom:14px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                        <strong style="color:#c8d8c8; font-size:0.95rem;">{std['name']}</strong>
                        <span style="color:{overall_color}; font-weight:700; font-size:0.9rem;">
                            {check_icon(std['overall'])} {std['overall']}
                        </span>
                    </div>
                    <div style="color:#5a7a5a; font-size:0.75rem; margin-bottom:10px; 
                                border-bottom:1px solid #1a2e1e; padding-bottom:8px;">
                        {std['description'][:120]}…
                    </div>
                """, unsafe_allow_html=True)

                for check in std.get("checks", []):
                    icon = check_icon(check["result"])
                    val_color = {"PASS": "#7dda82", "FAIL": "#da7d7d", "REVIEW": "#dab97d", "N/A": "#6a8a6a"}.get(check["result"], "#9ab09a")
                    st.markdown(f"""
                    <div style="display:flex; align-items:center; padding:5px 0; 
                                border-bottom:1px solid #121e12; font-size:0.82rem; gap:8px;">
                        <span style="width:22px;">{icon}</span>
                        <span style="flex:1; color:#9ab09a;">{check['name']}</span>
                        <span style="color:{val_color}; font-family:monospace; font-size:0.8rem;">{check.get('value','—')}</span>
                        <span style="color:#4a6a4a; font-size:0.75rem; white-space:nowrap;">vs {check.get('threshold','—')}</span>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

        # Business activity detail
        bs = result.get("business_screening", {})
        if bs.get("reasoning"):
            st.markdown("#### 🔍 AI Business Activity Assessment")
            st.info(f"**Primary business:** {bs.get('primary_business','')}\n\n{bs.get('reasoning','')}")

        if prohibited:
            st.error(f"⚠️ **Prohibited activities identified:** {', '.join(prohibited)}")

        # Raw data note
        st.markdown(f"""
        <div class="disclaimer">
            💡 <strong>Data sources:</strong> Financial ratios from Yahoo Finance (yfinance). Business activity classification by Claude AI.
            Impure revenue % is an estimate — manual review of annual reports recommended for accuracy.
            Islamicly's 36-month average market cap is approximated with current market cap in this concept version.
        </div>
        """, unsafe_allow_html=True)


# ─── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🌙 Halal Screener")
    st.markdown("---")

    st.markdown("---")
    st.markdown("#### 📋 Frameworks")
    st.markdown("""
    <small style="color:#6a8a6a; line-height:1.6;">
    This screener applies <strong style="color:#9ab09a">6 standards</strong> simultaneously:
    <br><br>
    🟢 <strong>AAOIFI</strong> — 30/30/5 (market cap)<br>
    🟢 <strong>Zoya</strong> — AAOIFI default<br>
    🟢 <strong>Musaffa</strong> — AAOIFI default<br>
    🟡 <strong>Islamicly</strong> — 33/33/49/5 (36mo avg)<br>
    🟡 <strong>Wahed / FTSE</strong> — 33.3/33.3/50 (assets)<br>
    🟡 <strong>SP Funds</strong> — same as FTSE (legal)
    </small>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### ⚠️ Disclaimer")
    st.markdown("""
    <small style="color:#5a7a5a; line-height:1.5;">
    This tool is for <strong>research and concept purposes only</strong>.
    It does not constitute a fatwa or religious ruling.
    Always consult a qualified Islamic finance scholar before making investment decisions.
    Financial data from Yahoo Finance may be delayed or incomplete.
    </small>
    <br><br>
    <small style="color:#4a6a4a; line-height:1.6; font-style:italic;">
    <strong style="color:#5a7a5a;">Educational Use Only.</strong>
    The information provided by this application is for general informational and educational purposes only.
    It is not intended to be, and does not constitute, financial advice, investment advice, trading advice,
    or any other type of advice. Nothing on this application should be construed as a solicitation,
    recommendation, or offer to buy or sell any security or financial instrument.
    <br><br>
    Past screening results do not guarantee future compliance status. Always conduct your own due diligence
    and consult with a qualified financial advisor and/or Islamic finance scholar before making any investment decision.
    You are solely responsible for your own investment decisions.
    </small>
    """, unsafe_allow_html=True)


# ─── Main Content ──────────────────────────────────────────────────────────────

st.markdown("""
<div class="app-header">
    <h1>🌙 Halal Stock Screener</h1>
    <p>Screen stocks against 6 major Islamic finance frameworks — AAOIFI · Zoya · Musaffa · Islamicly · Wahed / FTSE · SP Funds</p>
</div>
""", unsafe_allow_html=True)

# Input area
col_input, col_btn = st.columns([4, 1])

with col_input:
    ticker_input = st.text_input(
        "Enter ticker(s)",
        placeholder="AAPL, MSFT, TSLA — separate multiple tickers with commas",
        label_visibility="collapsed",
    )

with col_btn:
    screen_btn = st.button("🔍 Screen", type="primary", use_container_width=True)

# Quick examples
st.markdown("""
<div style="margin-top:-8px; margin-bottom:20px;">
    <small style="color:#4a6a4a;">
        Examples: &nbsp;
        <code style="color:#6a8a6a;">AAPL</code> &nbsp;·&nbsp;
        <code style="color:#6a8a6a;">MSFT, AMZN, GOOGL</code> &nbsp;·&nbsp;
        <code style="color:#6a8a6a;">JPM</code> (bank — likely FAIL) &nbsp;·&nbsp;
        <code style="color:#6a8a6a;">MO</code> (tobacco — FAIL)
    </small>
</div>
""", unsafe_allow_html=True)

# ─── Screening Logic ───────────────────────────────────────────────────────────

if screen_btn:
    if not ticker_input.strip():
        st.warning("Please enter at least one ticker symbol.")
    else:
        tickers = [t.strip().upper() for t in ticker_input.replace(" ", ",").split(",") if t.strip()]

        if len(tickers) > 10:
            st.warning(f"Screening up to 10 tickers at a time. Processing first 10 of {len(tickers)}.")
            tickers = tickers[:10]

        st.markdown(f"### Results for: `{', '.join(tickers)}`")
        st.markdown("---")

        # Screen each ticker with a progress bar
        progress = st.progress(0)
        status = st.empty()

        results = []
        for i, ticker in enumerate(tickers):
            status.markdown(f"*⏳ Screening {ticker}... ({i+1}/{len(tickers)})*")
            result = screen_ticker(ticker)
            results.append(result)
            progress.progress((i + 1) / len(tickers))

        progress.empty()
        status.empty()

        # Summary overview if multiple tickers
        if len(results) > 1:
            halal_count = sum(1 for r in results if r.get("overall") == "POTENTIALLY_HALAL")
            avoid_count = sum(1 for r in results if r.get("overall") == "AVOID")
            review_count = sum(1 for r in results if r.get("overall") == "REVIEW")
            err_count = sum(1 for r in results if "error" in r)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("✅ Potentially Halal", halal_count)
            c2.metric("❌ Avoid", avoid_count)
            c3.metric("⚠️ Needs Review", review_count)
            c4.metric("🔍 Screened", len(tickers) - err_count)
            st.markdown("---")

        # Render each result
        for result in results:
            render_result(result)

        # Overall disclaimer
        st.markdown("""
        <div class="disclaimer">
            <strong>Important:</strong> This concept screener uses Yahoo Finance data (which may be delayed, incomplete, or missing for some tickers) 
            and AI-based business activity classification. Results should be cross-referenced with official screening platforms (Zoya, Musaffa, Islamicly) 
            and verified with a qualified Islamic finance scholar before acting on them. 
            Purification calculations are not yet included in this concept version.
        </div>
        """, unsafe_allow_html=True)

# ─── Empty state ───────────────────────────────────────────────────────────────

elif not screen_btn:
    st.markdown("""
    <div style="text-align:center; padding:60px 20px; color:#3a5a3e;">
        <div style="font-size:3rem;">🔍</div>
        <div style="font-family:'Lora',serif; font-size:1.2rem; margin-top:16px; color:#4a7a4e;">
            Enter a ticker above to begin screening
        </div>
        <div style="font-size:0.85rem; margin-top:8px;">
            Each result shows a verdict, a one-line summary, and expandable details across all 6 standards.
        </div>
    </div>
    """, unsafe_allow_html=True)
