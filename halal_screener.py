"""
Halal Stock Screener — Core Logic
Screens stocks against 6 major Islamic finance frameworks using Yahoo Finance data only.
No external API key required.
"""

import yfinance as yf


# ─── Prohibited Sector Keyword Rules ──────────────────────────────────────────
# Matched against: sector, industry, and longBusinessSummary from yfinance

PROHIBITED_RULES = [
    {
        "activity": "Alcohol",
        "keywords": ["alcohol", "brewery", "brewing", "beer", "wine", "spirits", "distill", "liquor", "winery", "beverage alcohol"],
        "industry_match": ["Beverages—Brewers", "Beverages—Wineries & Distilleries"],
        "standards": "all",
    },
    {
        "activity": "Gambling / Casinos",
        "keywords": ["gambling", "casino", "lottery", "wagering", "betting", "sportsbook"],
        "industry_match": ["Gambling"],
        "exclude_keywords": ["video game", "game studio", "game develop", "game software"],
        "standards": "all",
    },
    {
        "activity": "Pork / Non-Halal Food",
        "keywords": ["pork", "swine", "pig farm", "hog farm", "bacon produc", "ham processing"],
        "standards": "all",
    },
    {
        "activity": "Conventional Banking / Interest Finance",
        "keywords": ["commercial bank", "retail bank", "investment bank", "mortgage bank", "consumer lending", "payday loan"],
        "industry_match": ["Banks—Regional", "Banks—Diversified", "Mortgage Finance", "Credit Services"],
        "standards": "all",
        "note": "Islamic banks and fully Shariah-compliant financial institutions are exempt.",
    },
    {
        "activity": "Conventional Insurance",
        "keywords": ["life insurance", "property insurance", "casualty insurance", "reinsurance company"],
        "industry_match": ["Insurance—Life", "Insurance—Property & Casualty", "Insurance—Diversified", "Insurance—Specialty", "Reinsurance"],
        "standards": ["Islamicly", "Wahed / FTSE Yasaar", "SP Funds / S&P Shariah"],
        "note": "Takaful (Islamic insurance) is exempt.",
    },
    {
        "activity": "Adult Content / Pornography",
        "keywords": ["adult content", "pornograph", "adult entertainment", "adult video", "explicit content"],
        "standards": "all",
    },
    {
        "activity": "Tobacco / Vaping",
        "keywords": ["tobacco", "cigarette", "cigar", "vaping", "e-cigarette", "nicotine product"],
        "industry_match": ["Tobacco"],
        "standards": "all",
    },
    {
        "activity": "Weapons / Defense Manufacturing",
        "keywords": ["weapons manufacturer", "arms manufacturer", "defense contractor", "ammunition manufacturer", "firearms manufacturer"],
        "industry_match": ["Aerospace & Defense"],
        "standards": ["AAOIFI", "Zoya", "Musaffa", "Wahed / FTSE Yasaar", "SP Funds / S&P Shariah"],
        "note": "Islamicly does not explicitly list weapons/defense in its public rulebook.",
    },
    {
        "activity": "Hotels / Entertainment (select standards)",
        "keywords": ["hotel chain", "casino resort", "nightclub"],
        "industry_match": ["Hotels & Motels", "Resorts & Casinos"],
        "standards": ["Islamicly", "Wahed / FTSE Yasaar", "SP Funds / S&P Shariah", "Musaffa"],
    },
]

CONVENTIONAL_FINANCE_INDUSTRIES = {
    "Banks—Regional", "Banks—Diversified", "Mortgage Finance",
    "Credit Services", "Financial Conglomerates",
}


# ─── Standards Config ──────────────────────────────────────────────────────────

STANDARDS_CONFIG = {
    "AAOIFI": {
        "debt_denominator": "market_cap",
        "debt_threshold": 0.30,
        "cash_denominator": "market_cap",
        "cash_threshold": 0.30,
        "receivables_check": False,
        "impure_revenue_threshold": 0.05,
        "description": "30% debt / market cap · 30% cash / market cap · 5% impure revenue",
    },
    "Zoya": {
        "debt_denominator": "market_cap",
        "debt_threshold": 0.30,
        "cash_denominator": "market_cap",
        "cash_threshold": 0.30,
        "receivables_check": False,
        "impure_revenue_threshold": 0.05,
        "description": "AAOIFI-based default · 30/30/5 · methodology switching available in Pro",
    },
    "Musaffa": {
        "debt_denominator": "market_cap",
        "debt_threshold": 0.30,
        "cash_denominator": "market_cap",
        "cash_threshold": 0.30,
        "receivables_check": False,
        "impure_revenue_threshold": 0.05,
        "description": "AAOIFI-based · 30/30/5 · older AAOIFI liquidity filter considered removed",
    },
    "Islamicly": {
        "debt_denominator": "market_cap",
        "debt_threshold": 0.33,
        "cash_denominator": "market_cap",
        "cash_threshold": 0.33,
        "receivables_check": True,
        "receivables_threshold": 0.49,
        "receivables_denominator": "market_cap",
        "receivables_combined_cash": False,
        "impure_revenue_threshold": 0.05,
        "description": "33% debt · 33% cash · 49% receivables (vs market cap, 36-mo avg approx.) · 5% impure revenue",
    },
    "Wahed / FTSE Yasaar": {
        "debt_denominator": "total_assets",
        "debt_threshold": 0.33333,
        "cash_denominator": "total_assets",
        "cash_threshold": 0.33333,
        "receivables_check": True,
        "receivables_threshold": 0.50,
        "receivables_denominator": "total_assets",
        "receivables_combined_cash": True,
        "impure_revenue_threshold": 0.05,
        "description": "33.3% debt / assets · 33.3% cash / assets · rec+cash < 50% assets · quarterly review",
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
        "description": "Asset-based tests same as FTSE · extra exclusions incl. Aerospace & Defense · monthly reconstitution",
    },
}


# ─── Data Fetching ─────────────────────────────────────────────────────────────

def get_financial_data(ticker: str) -> dict:
    """Fetch all needed financial data from Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or (not info.get("longName") and not info.get("shortName")):
            return {"error": f"Ticker '{ticker}' not found or returned no data."}

        receivables = 0
        try:
            bs = stock.balance_sheet
            if not bs.empty:
                for label in ["Net Receivables", "Receivables", "Accounts Receivable"]:
                    if label in bs.index:
                        val = bs.loc[label].iloc[0]
                        if val == val and val:  # not NaN
                            receivables = float(val)
                            break
        except Exception:
            pass
        if not receivables:
            receivables = info.get("netReceivables") or 0

        return {
            "ticker": ticker.upper(),
            "company_name": info.get("longName") or info.get("shortName") or ticker.upper(),
            "sector": info.get("sector") or "Unknown",
            "industry": info.get("industry") or "Unknown",
            "description": (info.get("longBusinessSummary") or "")[:1000],
            "market_cap": info.get("marketCap") or 0,
            "total_debt": info.get("totalDebt") or 0,
            "total_cash": info.get("totalCash") or 0,
            "total_assets": info.get("totalAssets") or 0,
            "total_revenue": info.get("totalRevenue") or 0,
            "interest_income": info.get("interestIncome") or 0,
            "receivables": receivables,
            "website": info.get("website") or "",
            "country": info.get("country") or "",
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Business Activity Screening (Keyword-Based) ───────────────────────────────

def screen_business_activity(fd: dict) -> dict:
    """
    Keyword scan across sector, industry, and business description.
    No external API — works entirely with Yahoo Finance data.
    """
    industry = fd.get("industry", "")
    full_text = " ".join([
        fd.get("sector", ""),
        industry,
        fd.get("description", ""),
        fd.get("company_name", ""),
    ]).lower()

    prohibited_found = []
    notes = []

    for rule in PROHIBITED_RULES:
        exclude_kw = rule.get("exclude_keywords", [])
        if any(ex in full_text for ex in exclude_kw):
            continue

        hit = (
            any(kw in full_text for kw in rule.get("keywords", []))
            or industry in rule.get("industry_match", [])
        )

        if hit:
            prohibited_found.append(rule["activity"])
            if rule.get("note"):
                notes.append(rule["note"])

    # Impure revenue: use interest income / total revenue from yfinance
    tr = fd.get("total_revenue") or 0
    ii = fd.get("interest_income") or 0
    if tr > 0 and ii > 0:
        impure_pct = (ii / tr) * 100
        impure_confidence = "high"
        impure_note = "Calculated from reported interest income / total revenue (Yahoo Finance)."
    else:
        impure_pct = 0.0
        impure_confidence = "low"
        impure_note = "Interest income not reported — verify non-permissible revenue in annual report."

    if prohibited_found:
        verdict = "FAIL"
        reasoning = (
            f"Prohibited activity detected: {', '.join(prohibited_found)}. "
            f"Based on sector '{fd.get('sector')}', industry '{fd.get('industry')}', and description scan."
        )
    elif industry in CONVENTIONAL_FINANCE_INDUSTRIES or fd.get("sector") == "Financial Services":
        verdict = "REVIEW"
        reasoning = (
            f"Operates in Financial Services ({industry}). "
            f"Manual review needed to confirm this is not a conventional bank or lender. Islamic banks are exempt."
        )
    else:
        verdict = "PASS"
        reasoning = (
            f"No prohibited activities found in sector ({fd.get('sector')}), "
            f"industry ({industry}), or business description."
        )

    return {
        "prohibited_activities_found": prohibited_found,
        "impure_revenue_pct_estimate": impure_pct,
        "impure_revenue_confidence": impure_confidence,
        "impure_revenue_note": impure_note,
        "primary_business": f"{fd.get('sector')} — {industry}",
        "business_activity_verdict": verdict,
        "reasoning": reasoning,
        "notes": notes,
    }


# ─── Financial Ratio Calculations ──────────────────────────────────────────────

def calculate_ratios(fd: dict) -> dict:
    mc  = fd.get("market_cap") or 0
    td  = fd.get("total_debt") or 0
    tc  = fd.get("total_cash") or 0
    ta  = fd.get("total_assets") or 0
    tr  = fd.get("total_revenue") or 0
    ii  = fd.get("interest_income") or 0
    rec = fd.get("receivables") or 0

    def pct(n, d): return (n / d) if d else None

    return {
        "debt_to_mktcap":                  pct(td, mc),
        "cash_to_mktcap":                  pct(tc, mc),
        "receivables_to_mktcap":           pct(rec, mc),
        "debt_to_assets":                  pct(td, ta),
        "cash_to_assets":                  pct(tc, ta),
        "receivables_to_assets":           pct(rec, ta),
        "receivables_plus_cash_to_assets": pct(rec + tc, ta),
        "interest_to_revenue":             pct(ii, tr),
        "market_cap": mc, "total_debt": td, "total_cash": tc,
        "total_assets": ta, "total_revenue": tr,
        "interest_income": ii, "receivables": rec,
    }


# ─── Per-Standard Checks ───────────────────────────────────────────────────────

def _ratio_check(name, value, threshold, val_label, thr_label):
    if value is None:
        return {"name": name, "result": "N/A", "value": "No data",
                "threshold": thr_label, "detail": "Not reported by Yahoo Finance"}
    passed = value <= threshold
    return {
        "name": name,
        "result": "PASS" if passed else "FAIL",
        "value": val_label,
        "threshold": thr_label,
        "detail": f"{'Within' if passed else 'Exceeds'} the {thr_label} limit",
    }


def apply_standard(std_name: str, cfg: dict, ratios: dict, business: dict) -> dict:
    checks = []

    # 1. Business Activity — filter rules to this standard
    prohibited_all = business["prohibited_activities_found"]
    std_prohibited = [
        rule["activity"] for rule in PROHIBITED_RULES
        if rule["activity"] in prohibited_all
        and (rule.get("standards") == "all" or std_name in rule.get("standards", []))
    ]
    b_base = business["business_activity_verdict"]
    std_verdict = "FAIL" if std_prohibited else ("REVIEW" if b_base == "REVIEW" else "PASS")

    checks.append({
        "name": "Business Activity",
        "result": std_verdict,
        "value": ", ".join(std_prohibited) if std_prohibited else "None identified",
        "threshold": "No prohibited sectors",
        "detail": business["reasoning"],
    })

    # 2. Impure Revenue
    impure_pct = business["impure_revenue_pct_estimate"]
    impure_thr = cfg["impure_revenue_threshold"] * 100
    checks.append({
        "name": "Impure Revenue",
        "result": "PASS" if impure_pct <= impure_thr else "FAIL",
        "value": f"{impure_pct:.1f}% ({business['impure_revenue_confidence']} confidence)",
        "threshold": f"< {impure_thr:.0f}%",
        "detail": business["impure_revenue_note"],
    })

    # 3. Debt Ratio
    denom = cfg["debt_denominator"]
    ratio_key = "debt_to_mktcap" if denom == "market_cap" else "debt_to_assets"
    denom_label = "market cap" if denom == "market_cap" else "total assets"
    val = ratios.get(ratio_key)
    thr = cfg["debt_threshold"]
    checks.append(_ratio_check("Debt Ratio", val, thr,
        f"{val*100:.1f}%" if val is not None else "N/A",
        f"< {thr*100:.1f}% of {denom_label}"))

    # 4. Cash / Interest-Bearing Assets
    cash_key = "cash_to_mktcap" if denom == "market_cap" else "cash_to_assets"
    val = ratios.get(cash_key)
    thr = cfg["cash_threshold"]
    checks.append(_ratio_check("Cash & Interest-Bearing Assets", val, thr,
        f"{val*100:.1f}%" if val is not None else "N/A",
        f"< {thr*100:.1f}% of {denom_label}"))

    # 5. Receivables (select standards)
    if cfg.get("receivables_check"):
        combine = cfg.get("receivables_combined_cash", False)
        rec_key = "receivables_plus_cash_to_assets" if combine else (
            "receivables_to_mktcap" if denom == "market_cap" else "receivables_to_assets")
        rec_label = "Receivables + Cash" if combine else "Receivables"
        val = ratios.get(rec_key)
        thr = cfg.get("receivables_threshold", 0.49)
        checks.append(_ratio_check(f"{rec_label} Ratio", val, thr,
            f"{val*100:.1f}%" if val is not None else "N/A",
            f"< {thr*100:.1f}% of {denom_label}"))

    results = [c["result"] for c in checks]
    overall = "FAIL" if "FAIL" in results else ("REVIEW" if "REVIEW" in results else "PASS")

    return {"name": std_name, "description": cfg["description"], "overall": overall, "checks": checks}


# ─── Summary ───────────────────────────────────────────────────────────────────

def generate_summary(fd: dict, overall: str, standards: list, business: dict) -> str:
    company = fd["company_name"]
    ticker = fd["ticker"]
    pass_count = sum(1 for s in standards if s["overall"] == "PASS")
    fail_count = sum(1 for s in standards if s["overall"] == "FAIL")
    prohibited = business.get("prohibited_activities_found", [])

    if overall == "AVOID":
        reason = f"prohibited activities ({', '.join(prohibited)})" if prohibited else "financial ratio breaches"
        return (
            f"{company} ({ticker}) does not pass Islamic screening due to {reason}. "
            f"It failed {fail_count} of 6 frameworks and should be avoided under most Islamic finance standards."
        )
    elif overall == "REVIEW":
        return (
            f"{company} ({ticker}) passed {pass_count} of 6 standards but has areas flagged for manual review, "
            f"likely due to financial sector classification or borderline ratio values. "
            f"Consult a qualified Islamic finance scholar before investing."
        )
    else:
        return (
            f"{company} ({ticker}) passed all {pass_count} of 6 screening standards with no prohibited activities identified. "
            f"Financial ratios are within acceptable thresholds — always verify with a qualified scholar before investing."
        )


# ─── Main Entry Point ──────────────────────────────────────────────────────────

def screen_ticker(ticker: str) -> dict:
    """Full screening pipeline. No API key required."""
    ticker = ticker.strip().upper()

    fd = get_financial_data(ticker)
    if "error" in fd:
        return {"ticker": ticker, "error": fd["error"]}

    business = screen_business_activity(fd)
    ratios = calculate_ratios(fd)
    standards = [apply_standard(n, c, ratios, business) for n, c in STANDARDS_CONFIG.items()]

    any_fail   = any(s["overall"] == "FAIL"   for s in standards)
    any_review = any(s["overall"] == "REVIEW" for s in standards)
    overall = "AVOID" if any_fail else ("REVIEW" if any_review else "POTENTIALLY_HALAL")

    return {
        "ticker": ticker,
        "company_name": fd["company_name"],
        "sector": fd["sector"],
        "industry": fd["industry"],
        "market_cap": fd["market_cap"],
        "country": fd.get("country", ""),
        "primary_business": business["primary_business"],
        "prohibited_activities": business["prohibited_activities_found"],
        "overall": overall,
        "summary": generate_summary(fd, overall, standards, business),
        "standards": standards,
        "ratios": ratios,
        "business_screening": business,
    }
