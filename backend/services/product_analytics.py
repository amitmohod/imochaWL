"""Product intelligence analytics: feature gaps, integration gaps, persona needs."""

from typing import List, Optional, Dict
from collections import defaultdict
from services.data_source import get_deals, get_companies, get_contacts
from services.analytics import _pl_to_deal_value
from models.product_analysis import FeatureGap, IntegrationGap, PersonaNeed


TA_INTEGRATION_KEYWORDS = [
    ("Greenhouse ATS", ["greenhouse", "greenhouse ats"]),
    ("Workday Recruiting", ["workday recruit", "workday ats"]),
    ("iCIMS", ["icims"]),
    ("Lever", ["lever ats", " lever "]),
    ("ATS Integration (General)", ["ats integration", "ats gap", "deeper ats", "need ats"]),
]

SI_INTEGRATION_KEYWORDS = [
    ("Workday HCM", ["workday", "workday hcm", "workday integration"]),
    ("SAP SuccessFactors", ["sap", "successfactors", "sap integration"]),
    ("Oracle HCM", ["oracle hcm", "oracle integration"]),
    ("Cornerstone LMS", ["cornerstone", "lms integration"]),
    ("HCM Integration (General)", ["hcm", "hris integration", "integration gap with"]),
]

# Static concern labels for each seniority
_PERSONA_CONCERNS = {
    "C-Level": "Needs ROI proof and board-level reporting to justify investment",
    "VP": "Primary decision maker — focus on strategic value and integration",
    "Director": "Operational focus — needs implementation support and timeline clarity",
    "Manager": "Budget constrained, needs easy setup and quick ROI demonstration",
}


def compute_feature_gaps(product_line: Optional[str] = None) -> List[FeatureGap]:
    """Compute feature gaps from lost deals, grouped by loss_reason and objections."""
    deals = get_deals()
    pl_val = _pl_to_deal_value(product_line)
    if pl_val:
        deals = [d for d in deals if d.product_line == pl_val]
    companies = {c.id: c for c in get_companies()}

    lost_deals = [d for d in deals if d.stage == "closedlost"]

    # Gap dicts: name -> {deals, revenue, competitors, quotes}
    gap_data: Dict[str, dict] = defaultdict(lambda: {
        "deals": [],
        "revenue": 0.0,
        "competitors": set(),
        "quotes": [],
        "source": "objection",
    })

    # 1. Group by loss_reason
    for deal in lost_deals:
        if deal.loss_reason:
            key = deal.loss_reason
            gap_data[key]["deals"].append(deal.id)
            gap_data[key]["revenue"] += deal.amount
            gap_data[key]["source"] = "loss_reason"
            if deal.competitor:
                gap_data[key]["competitors"].add(deal.competitor)
            # Collect negative sentiment quotes
            for sig in deal.conversation_signals:
                if sig.sentiment == "negative" and sig.theme in (
                    "Product Gap", "Requirement Mismatch", "Competitive Pressure"
                ):
                    comp = companies.get(deal.company_id)
                    industry = comp.industry if comp else "Unknown"
                    gap_data[key]["quotes"].append((sig.quote, industry, deal.amount))

    # 2. Group by objections (merge into existing keys or create new)
    for deal in lost_deals:
        for obj in deal.objections:
            if obj in gap_data:
                # already exists from loss_reason — just add data if revenue is higher
                if deal.id not in gap_data[obj]["deals"]:
                    gap_data[obj]["deals"].append(deal.id)
                    gap_data[obj]["revenue"] += deal.amount
            else:
                gap_data[obj]["deals"].append(deal.id)
                gap_data[obj]["revenue"] += deal.amount
                gap_data[obj]["source"] = "objection"
            if deal.competitor:
                gap_data[obj]["competitors"].add(deal.competitor)
            for sig in deal.conversation_signals:
                if sig.sentiment == "negative" and sig.theme in (
                    "Product Gap", "Requirement Mismatch", "Competitive Pressure"
                ):
                    comp = companies.get(deal.company_id)
                    industry = comp.industry if comp else "Unknown"
                    gap_data[obj]["quotes"].append((sig.quote, industry, deal.amount))

    # 3. Build FeatureGap objects
    results = []
    for name, data in gap_data.items():
        unique_deals = list(set(data["deals"]))
        competitors = sorted(data["competitors"])

        # Pick best quote
        sample_quote = ""
        sample_quote_context = ""
        if data["quotes"]:
            # Prefer quote from largest deal
            data["quotes"].sort(key=lambda q: q[2], reverse=True)
            best = data["quotes"][0]
            sample_quote = best[0]
            sample_quote_context = f"Lost deal · {best[1]} · ${int(best[2] / 1000)}K"
        else:
            sample_quote = f"Recurring theme across {len(unique_deals)} lost deals."
            sample_quote_context = f"{len(unique_deals)} deals affected"

        results.append(FeatureGap(
            name=name,
            deals_affected=len(unique_deals),
            revenue_at_risk=data["revenue"],
            competitors=competitors,
            sample_quote=sample_quote,
            sample_quote_context=sample_quote_context,
            source=data["source"],
        ))

    # Sort by revenue descending, return top 8
    results.sort(key=lambda g: g.revenue_at_risk, reverse=True)
    return results[:8]


def compute_integration_gaps(product_line: Optional[str] = None) -> List[IntegrationGap]:
    """Compute integration gaps from lost deals by scanning text for integration keywords."""
    deals = get_deals()
    pl_val = _pl_to_deal_value(product_line)
    if pl_val:
        deals = [d for d in deals if d.product_line == pl_val]

    lost_deals = [d for d in deals if d.stage == "closedlost"]

    # Choose keyword set based on product_line
    if pl_val == "TA":
        keyword_groups = TA_INTEGRATION_KEYWORDS
    elif pl_val == "Skills Intelligence":
        keyword_groups = SI_INTEGRATION_KEYWORDS
    else:
        # all or full_platform — combine both
        keyword_groups = TA_INTEGRATION_KEYWORDS + SI_INTEGRATION_KEYWORDS

    results = []
    for display_name, keywords in keyword_groups:
        matched_deals = []
        for deal in lost_deals:
            text_blob = " ".join([
                " ".join(deal.objections),
                deal.loss_reason or "",
                " ".join(sig.quote for sig in deal.conversation_signals),
            ]).lower()
            if any(kw.lower() in text_blob for kw in keywords):
                matched_deals.append(deal)

        # Deduplicate by deal id
        seen_ids = set()
        unique_deals = []
        for deal in matched_deals:
            if deal.id not in seen_ids:
                seen_ids.add(deal.id)
                unique_deals.append(deal)

        if not unique_deals:
            continue

        revenue = sum(d.amount for d in unique_deals)
        severity = "high" if len(unique_deals) >= 4 else "medium"
        results.append(IntegrationGap(
            name=display_name,
            deals_affected=len(unique_deals),
            revenue_at_risk=revenue,
            severity=severity,
        ))

    # Sort by revenue, return top 6
    results.sort(key=lambda g: g.revenue_at_risk, reverse=True)
    return results[:6]


def compute_persona_needs(product_line: Optional[str] = None) -> List[PersonaNeed]:
    """Compute buyer persona needs from deal data grouped by contact seniority."""
    deals = get_deals()
    pl_val = _pl_to_deal_value(product_line)
    if pl_val:
        deals = [d for d in deals if d.product_line == pl_val]
    contacts = {c.id: c for c in get_contacts()}

    seniority_data: Dict[str, dict] = defaultdict(lambda: {
        "won": 0, "total": 0,
        "objection_counts": defaultdict(int),
    })

    for deal in deals:
        contact = contacts.get(deal.contact_id)
        if not contact:
            continue
        sen = contact.seniority
        seniority_data[sen]["total"] += 1
        if deal.stage == "closedwon":
            seniority_data[sen]["won"] += 1
        elif deal.stage == "closedlost":
            for obj in deal.objections:
                seniority_data[sen]["objection_counts"][obj] += 1

    results = []
    for seniority, data in seniority_data.items():
        if data["total"] < 5:
            continue

        win_rate = round(data["won"] / data["total"] * 100, 1) if data["total"] else 0.0

        # Top 3 objections by frequency from lost deals
        obj_sorted = sorted(
            data["objection_counts"].items(),
            key=lambda x: x[1], reverse=True
        )
        top_asks = [obj for obj, _ in obj_sorted[:3]]

        concern = _PERSONA_CONCERNS.get(
            seniority,
            "Focused on business value and implementation quality"
        )

        results.append(PersonaNeed(
            title=seniority,
            win_rate=win_rate,
            top_asks=top_asks,
            deal_count=data["total"],
            concern=concern,
        ))

    # Sort by win_rate descending
    results.sort(key=lambda p: p.win_rate, reverse=True)
    return results
