"""
Halal Stock Screener - Core Logic
Screens stocks against 6 major Islamic finance frameworks using:
  - Yahoo Finance (financial ratios)
  - Claude AI (business activity classification)
"""

import yfinance as yf
import anthropic
import json
from typing import Optional


# ─── Prohibited Business Activities by Standard ────────────────────────────────

PROHIBITED_ALWAYS = [
    "alcohol", "gambling", "pork", "pork products", "non-halal food production",
    "conventional banking", "conventional finance", "interest-based finance",
    "adult content", "pornography",
]

PROHIBITED_MOST_STANDARDS = [
    "tobacco", "vaping", "e-cigarettes",
    "weapons manufacturing", "defense manufacturing", "arms",
    "conventional insurance",
    "entertainment", "media", "music", "cinema", "hotels",
]

PROHIBITED_STRICT_ONLY = [
    "advertising of haram activities",
    "gold and silver deferred trading",
]

# Per-standard sector flag lists
STANDARD_EXTRA_EXCLUSIONS = {
    "Wahed / FTSE Yasaar": ["hotels", "weapons", "defense", "arms", "cinema", "music"],
    "SP Funds / S&P Shariah": ["advertising of haram", "gold silver deferred", "aerospace defense"],
    "Islamicly": ["advertising of haram", "gold silver deferred", "media entertainment"],
}


# ─── Financial Ratio Thresholds ────────────────────────────────────────────────

STANDARDS_CONFIG = {
    "AAOIFI": {
        "debt_denominator": "market_cap",
        "debt_threshold": 0.30,
        "cash_denominator": "market_cap",
        "cash_threshold": 0.30,
        "receivables_check": False,
        "impure_revenue_threshold": 0.05,
        "description": "AAOIFI Standard (adopted by Zoya & Musaffa) — strictest financial ratios",
    },
    "Zoya": {
        "debt_denominator": "market_cap",
        "debt_threshold": 0.30,
        "cash_denominator": "market_cap",
        "cash_threshold": 0.30,
        "receivables_check": False,
        "impure_revenue_threshold": 0.05,
        "description": "Zoya default (AAOIFI-based) — 30/30/5 framework, methodology switching available in Pro",
    },
    "Musaffa": {
        "debt_denominator": "market_cap",
        "debt_threshold": 0.30,
        "cash_denominator": "market_cap",
        "cash_threshold": 0.30,
        "receivables_check": False,
        "impure_revenue_threshold": 0.05,
        "description": "Musaffa (AAOIFI-based) — 30/30/5; older AAOIFI liquidity filter considered removed",
    },
    "Islamicly": {
        "debt_denominator": "market_cap",        # uses 36-month avg; we approximate with current
        "debt_threshold": 0.33,
        "cash_denominator": "market_cap",
        "cash_threshold": 0.33,
        "receivables_check": True,
        "receivables_threshold": 0.49,
        "receivables_denominator": "market_cap",
        "impure_revenue_threshold": 0.05,
        "description": "Islamicly — 33/33/49/5 using 36-month avg market equity (approximated here with current market cap); most granular qualitative rulebook",
    },
    "Wahed / FTSE Yasaar": {
        "debt_denominator": "total_assets",
        "debt_threshold": 0.33333,
        "cash_denominator": "total_assets",
        "cash_threshold": 0.33333,
        "receivables_check": True,
        "receivables_threshold": 0.50,
        "receivables_denominator": "total_assets",  # receivables + cash combined
        "receivables_combined_cash": True,
        "impure_revenue_threshold": 0.05,
        "description": "Wahed HLAL / FTSE Yasaar — 33.333% of total assets; explicit weapons/defense/hotels exclusion; quarterly review with 2-quarter buffer",
    },
    "SP Funds / S&P Shariah": {
        "debt_denominator": "total_assets",
        "debt_threshold": 0.33333,
        "cash_denominator": "total_assets",
        "cash_threshold": 0.33333,
        "receivables_check": True,
        "receivables_threshold": 0.50,
        "receivables_denominator": "total_assets",
        "receivables_combined_cash": True,
        "impure_revenue_threshold": 0.05,
        "description": "SP Funds / S&P Shariah (legal prospectus basis) — same asset tests as FTSE; extra sub-industry exclusions incl. Aerospace & Defense; monthly reconstitution",
    },
}


# ─── Data Fetching ─────────────────────────────────────────────────────────────

def get_financial_data(ticker: str) -> dict:
    """Fetch all needed financial data from Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            # Try to detect invalid ticker
            if not info.get("longName") and not info.get("shortName"):
                return {"error": f"Ticker '{ticker}' not found or no data available."}

        market_cap = info.get("marketCap") or 0
        total_debt = info.get("totalDebt") or 0
        total_cash = info.get("totalCash") or 0
        total_assets = info.get("totalAssets") or 0
        total_revenue = info.get("totalRevenue") or 0
        interest_income = info.get("interestIncome") or 0

        # Try to get receivables from balance sheet
        receivables = 0
        try:
            bs = stock.balance_sheet
            if not bs.empty:
                for label in ["Net Receivables", "Receivables", "Accounts Receivable"]:
                    if label in bs.index:
                        val = bs.loc[label].iloc[0]
                        if val and not (val != val):  # not NaN
                            receivables = float(val)
                            break
        except Exception:
            pass

        if receivables == 0:
            receivables = info.get("netReceivables") or 0

        return {
            "ticker": ticker.upper(),
            "company_name": info.get("longName") or info.get("shortName") or ticker.upper(),
            "sector": info.get("sector") or "Unknown",
            "industry": info.get("industry") or "Unknown",
            "description": (info.get("longBusinessSummary") or "")[:800],
            "market_cap": market_cap,
            "total_debt": total_debt,
            "total_cash": total_cash,
            "total_assets": total_assets,
            "total_revenue": total_revenue,
            "interest_income": interest_income,
            "receivables": receivables,
            "website": info.get("website") or "",
            "country": info.get("country") or "",
            "employees": info.get("fullTimeEmployees") or 0,
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Business Activity Screening via Claude ────────────────────────────────────

def screen_business_activity(company_info: dict, api_key: str) -> dict:
    """
    Use Claude to classify business activities and estimate impure revenue %.
    Returns flags for prohibited activities + estimated impure revenue.
    """
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are an Islamic finance compliance analyst specializing in halal stock screening.

Analyze this company for prohibited business activities according to major Islamic screening frameworks (AAOIFI, FTSE Yasaar, S&P Shariah, Islamicly).

Company: {company_info.get('company_name')}
Ticker: {company_info.get('ticker')}
Sector: {company_info.get('sector')}
Industry: {company_info.get('industry')}
Description: {company_info.get('description')}
Website: {company_info.get('website')}

Prohibited activities to screen for:
ALWAYS prohibited: alcohol, gambling, pork/non-halal food production, conventional banking/interest-based finance, adult content/pornography
Usually prohibited: tobacco/vaping, weapons/defense manufacturing, conventional insurance, entertainment/music/cinema/hotels
Strictly prohibited (some standards): advertising of haram activities, gold/silver deferred trading

Respond ONLY with valid JSON in this exact format (no markdown, no extra text):
{{
  "prohibited_activities_found": ["list of specific prohibited activities found, empty if none"],
  "impure_revenue_pct_estimate": 0.0,
  "impure_revenue_confidence": "high/medium/low",
  "primary_business": "one sentence describing what the company primarily does",
  "business_activity_verdict": "PASS/FAIL/REVIEW",
  "reasoning": "2-3 sentences explaining your assessment"
}}

For impure_revenue_pct_estimate: estimate the percentage (0-100) of revenue that comes from non-permissible sources.
Use 0.0 if you are confident there are none, or if the company is clearly permissible.
Mark business_activity_verdict as REVIEW if the company touches gray areas but is not clearly prohibited."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        return {
            "prohibited_activities_found": [],
            "impure_revenue_pct_estimate": 0.0,
            "impure_revenue_confidence": "low",
            "primary_business": company_info.get("industry", "Unknown"),
            "business_activity_verdict": "REVIEW",
            "reasoning": f"Could not complete AI analysis: {str(e)}",
        }


# ─── Financial Ratio Calculations ──────────────────────────────────────────────

def calculate_ratios(fd: dict) -> dict:
    """Compute all relevant financial ratios from fetched data."""
    mc = fd.get("market_cap") or 0
    td = fd.get("total_debt") or 0
    tc = fd.get("total_cash") or 0
    ta = fd.get("total_assets") or 0
    tr = fd.get("total_revenue") or 0
    ii = fd.get("interest_income") or 0
    rec = fd.get("receivables") or 0

    def safe_div(num, den, label="ratio"):
        if not den or den == 0:
            return None
        return num / den

    return {
        # Market-cap denominator ratios (AAOIFI/Zoya/Musaffa/Islamicly)
        "debt_to_mktcap": safe_div(td, mc),
        "cash_to_mktcap": safe_div(tc, mc),
        "receivables_to_mktcap": safe_div(rec, mc),
        # Total-assets denominator ratios (Wahed/FTSE, SP Funds)
        "debt_to_assets": safe_div(td, ta),
        "cash_to_assets": safe_div(tc, ta),
        "receivables_to_assets": safe_div(rec, ta),
        "receivables_plus_cash_to_assets": safe_div(rec + tc, ta),
        # Revenue-based
        "interest_to_revenue": safe_div(ii, tr),
        # Raw values for display
        "market_cap": mc,
        "total_debt": td,
        "total_cash": tc,
        "total_assets": ta,
        "total_revenue": tr,
        "interest_income": ii,
        "receivables": rec,
    }


# ─── Per-Standard Compliance Checks ───────────────────────────────────────────

def _check(name: str, value, threshold: float, label_val: str, label_thr: str, invert=False) -> dict:
    """Helper: returns a single check result dict."""
    if value is None:
        return {"name": name, "result": "N/A", "value": "No data", "threshold": label_thr, "detail": "Data unavailable from Yahoo Finance"}
    passed = (value <= threshold) if not invert else (value >= threshold)
    return {
        "name": name,
        "result": "PASS" if passed else "FAIL",
        "value": label_val,
        "threshold": label_thr,
        "detail": f"{'✓ Within' if passed else '✗ Exceeds'} the {label_thr} limit",
    }


def apply_standard(std_name: str, cfg: dict, ratios: dict, business: dict) -> dict:
    """Apply a single standard's checks and return structured results."""
    checks = []

    # 1. Business Activity Check
    b_verdict = business.get("business_activity_verdict", "REVIEW")
    prohibited = business.get("prohibited_activities_found", [])
    checks.append({
        "name": "Business Activity",
        "result": b_verdict,
        "value": ", ".join(prohibited) if prohibited else "None identified",
        "threshold": "No prohibited sectors",
        "detail": business.get("reasoning", ""),
    })

    # Extra sector exclusions for specific standards
    extra_flags = []
    for sector_keyword in STANDARD_EXTRA_EXCLUSIONS.get(std_name, []):
        desc_lower = (business.get("primary_business", "") + " ".join(prohibited)).lower()
        if sector_keyword in desc_lower:
            extra_flags.append(sector_keyword)
    if extra_flags:
        checks.append({
            "name": f"Additional Exclusions ({std_name})",
            "result": "FAIL",
            "value": ", ".join(extra_flags),
            "threshold": "None of these sectors",
            "detail": f"{std_name} additionally excludes: {', '.join(extra_flags)}",
        })

    # 2. Impure Revenue Check
    impure_pct = business.get("impure_revenue_pct_estimate", 0.0)
    impure_threshold = cfg["impure_revenue_threshold"] * 100  # as %
    confidence = business.get("impure_revenue_confidence", "low")
    checks.append({
        "name": "Impure Revenue",
        "result": "PASS" if impure_pct <= impure_threshold else "FAIL",
        "value": f"~{impure_pct:.1f}% (AI est., {confidence} confidence)",
        "threshold": f"< {impure_threshold:.0f}%",
        "detail": f"Estimated non-permissible revenue share" + (" — manual review recommended for accuracy" if confidence in ["low", "medium"] else ""),
    })

    # 3. Debt Ratio Check
    denom = cfg["debt_denominator"]
    debt_ratio = ratios.get(f"debt_to_{denom.replace('market_cap','mktcap')}")
    thr = cfg["debt_threshold"]
    checks.append(_check(
        "Debt Ratio",
        debt_ratio,
        thr,
        f"{debt_ratio*100:.1f}%" if debt_ratio is not None else "N/A",
        f"< {thr*100:.1f}% of {'market cap' if denom=='market_cap' else 'total assets'}",
    ))

    # 4. Cash / Interest-Bearing Assets Check
    cash_ratio = ratios.get(f"cash_to_{denom.replace('market_cap','mktcap')}")
    checks.append(_check(
        "Cash & Interest-Bearing Assets",
        cash_ratio,
        cfg["cash_threshold"],
        f"{cash_ratio*100:.1f}%" if cash_ratio is not None else "N/A",
        f"< {cfg['cash_threshold']*100:.1f}% of {'market cap' if denom=='market_cap' else 'total assets'}",
    ))

    # 5. Receivables Check (some standards only)
    if cfg.get("receivables_check"):
        rec_denom = cfg.get("receivables_denominator", denom)
        combine_cash = cfg.get("receivables_combined_cash", False)
        if combine_cash:
            rec_ratio = ratios.get("receivables_plus_cash_to_assets")
            rec_label = "Receivables + Cash"
        else:
            rec_ratio = ratios.get(f"receivables_to_{rec_denom.replace('market_cap','mktcap')}")
            rec_label = "Receivables"
        rec_thr = cfg.get("receivables_threshold", 0.49)
        checks.append(_check(
            f"{rec_label} Ratio",
            rec_ratio,
            rec_thr,
            f"{rec_ratio*100:.1f}%" if rec_ratio is not None else "N/A",
            f"< {rec_thr*100:.1f}% of {'market cap' if rec_denom=='market_cap' else 'total assets'}",
        ))

    # ─── Compute overall standard result ───────────────────────────────────────
    results = [c["result"] for c in checks]
    if "FAIL" in results:
        overall = "FAIL"
    elif "REVIEW" in results:
        overall = "REVIEW"
    else:
        overall = "PASS"

    return {
        "name": std_name,
        "description": cfg["description"],
        "overall": overall,
        "checks": checks,
    }


# ─── Summary Generation ────────────────────────────────────────────────────────

def generate_summary(ticker: str, company_name: str, overall: str, standards: list, business: dict, api_key: str) -> str:
    """Generate a concise 2-sentence screening summary using Claude."""
    client = anthropic.Anthropic(api_key=api_key)

    pass_count = sum(1 for s in standards if s["overall"] == "PASS")
    fail_count = sum(1 for s in standards if s["overall"] == "FAIL")
    review_count = sum(1 for s in standards if s["overall"] == "REVIEW")
    prohibited = business.get("prohibited_activities_found", [])
    primary = business.get("primary_business", "")

    prompt = f"""Write exactly 2 clear, concise sentences summarizing a halal stock screening result.

Company: {company_name} ({ticker})
Primary business: {primary}
Overall verdict: {overall}
Standards passed: {pass_count}/6 | Failed: {fail_count}/6 | Needs review: {review_count}/6
Prohibited activities found: {', '.join(prohibited) if prohibited else 'None'}

Rules:
- Sentence 1: State the verdict and the main reason (business activity or financial ratio issue)
- Sentence 2: Note which standards pass/fail and any key caveats
- Be direct and factual. No fluff. No "According to our analysis..."
- Do NOT use markdown. Plain text only."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        if overall == "POTENTIALLY_HALAL":
            return f"{company_name} passed {pass_count} of 6 screening standards with no prohibited business activities identified. Financial ratios are within acceptable thresholds for most frameworks — review individual standard results for details."
        elif overall == "AVOID":
            return f"{company_name} failed {fail_count} of 6 screening standards due to {'prohibited activities: ' + ', '.join(prohibited) if prohibited else 'financial ratio breaches'}. This stock should be avoided under most Islamic finance frameworks."
        else:
            return f"{company_name} returned mixed results across {len(standards)} screening standards, passing {pass_count} and flagging {review_count} for further review. Manual verification is recommended before making an investment decision."


# ─── Main Screener ─────────────────────────────────────────────────────────────

def screen_ticker(ticker: str, api_key: str) -> dict:
    """
    Full screening pipeline for a single ticker.
    Returns a structured result dict ready for display.
    """
    ticker = ticker.strip().upper()

    # 1. Fetch financial data
    fd = get_financial_data(ticker)
    if "error" in fd:
        return {"ticker": ticker, "error": fd["error"]}

    # 2. Business activity screening via Claude
    business = screen_business_activity(fd, api_key)

    # 3. Calculate financial ratios
    ratios = calculate_ratios(fd)

    # 4. Apply all 6 standards
    standards = []
    for std_name, cfg in STANDARDS_CONFIG.items():
        std_result = apply_standard(std_name, cfg, ratios, business)
        standards.append(std_result)

    # 5. Compute overall verdict
    any_fail = any(s["overall"] == "FAIL" for s in standards)
    any_review = any(s["overall"] == "REVIEW" for s in standards)
    all_pass = all(s["overall"] == "PASS" for s in standards)

    if any_fail:
        overall = "AVOID"
    elif any_review:
        overall = "REVIEW"
    else:
        overall = "POTENTIALLY_HALAL"

    # 6. Generate 2-sentence summary
    summary = generate_summary(ticker, fd["company_name"], overall, standards, business, api_key)

    return {
        "ticker": ticker,
        "company_name": fd["company_name"],
        "sector": fd["sector"],
        "industry": fd["industry"],
        "market_cap": fd["market_cap"],
        "country": fd.get("country", ""),
        "primary_business": business.get("primary_business", ""),
        "prohibited_activities": business.get("prohibited_activities_found", []),
        "overall": overall,
        "summary": summary,
        "standards": standards,
        "ratios": ratios,
        "business_screening": business,
    }


def screen_multiple_tickers(tickers: list, api_key: str) -> list:
    """Screen a list of tickers, returning a list of results."""
    return [screen_ticker(t, api_key) for t in tickers if t.strip()]
