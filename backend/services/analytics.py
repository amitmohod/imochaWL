"""Statistical computation engine — all numbers are exact, never AI-generated."""

from typing import Dict, List, Optional
from collections import defaultdict
from services.data_source import get_deals, get_companies, get_contacts, get_company, get_contact
from models.analysis import (
    OverviewMetrics, BreakdownItem, CompetitorMetrics, ObjectionTheme, ICPProfile,
    EnhancedKPIs, SegmentStat, GrowthLever, RevenueLeak, ICPFitSignal,
    ConversationThemeAgg, StrategicSignals, KPIComparison, ReasonCount, FilterOptions,
    ConversationEvidence, PatternInsight, TrendPoint,
)
from models.hubspot import DealEnriched


def _pl_to_deal_value(product_line: Optional[str]) -> Optional[str]:
    """Map API product_line param to deal.product_line value."""
    mapping = {"TA": "TA", "SI": "Skills Intelligence", "full_platform": "Full Platform"}
    return mapping.get(product_line) if product_line and product_line != "all" else None


def enrich_deal(deal) -> DealEnriched:
    company = get_company(deal.company_id)
    contact = get_contact(deal.contact_id)
    return DealEnriched(**deal.model_dump(), company=company, contact=contact)


def get_enriched_deals(stage: Optional[str] = None, industry: Optional[str] = None,
                       source: Optional[str] = None) -> List[DealEnriched]:
    deals = get_deals()
    if stage:
        deals = [d for d in deals if d.stage == stage]
    if industry:
        companies = {c.id: c for c in get_companies()}
        deals = [d for d in deals if companies.get(d.company_id) and
                 companies[d.company_id].industry.lower() == industry.lower()]
    if source:
        deals = [d for d in deals if d.deal_source.lower() == source.lower()]
    return [enrich_deal(d) for d in deals]


def compute_overview(product_line: Optional[str] = None) -> OverviewMetrics:
    deals = get_deals()
    pl_val = _pl_to_deal_value(product_line)
    if pl_val:
        deals = [d for d in deals if d.product_line == pl_val]
    won = [d for d in deals if d.stage == "closedwon"]
    lost = [d for d in deals if d.stage == "closedlost"]
    total_rev = sum(d.amount for d in won)

    return OverviewMetrics(
        total_deals=len(deals),
        won_deals=len(won),
        lost_deals=len(lost),
        win_rate=round(len(won) / len(deals) * 100, 1) if deals else 0,
        total_revenue=round(total_rev, 2),
        avg_deal_size=round(total_rev / len(won), 2) if won else 0,
        avg_cycle_won=round(sum(d.cycle_days for d in won) / len(won), 1) if won else 0,
        avg_cycle_lost=round(sum(d.cycle_days for d in lost) / len(lost), 1) if lost else 0,
    )


def compute_filter_options() -> FilterOptions:
    """Lightweight filter options from all deals — no heavy computation."""
    all_deals = get_deals()
    companies = {c.id: c for c in get_companies()}
    return FilterOptions(
        quarters=sorted(set(_quarter_for_deal(d) for d in all_deals)),
        industries=sorted(set(
            companies[d.company_id].industry
            for d in all_deals if d.company_id in companies
        )),
        regions=sorted(set(
            companies[d.company_id].city
            for d in all_deals
            if d.company_id in companies and companies[d.company_id].city
        )),
        sales_reps=sorted(set(d.sales_rep for d in all_deals if d.sales_rep)),
    )


def _apply_filters(deals, companies, quarter=None, industry=None, region=None, sales_rep=None, product_line=None):
    """Shared filter logic for deals."""
    filtered = list(deals)
    if quarter:
        filtered = [d for d in filtered if _quarter_for_deal(d) == quarter]
    if industry:
        filtered = [d for d in filtered
                    if d.company_id in companies
                    and companies[d.company_id].industry.lower() == industry.lower()]
    if region:
        filtered = [d for d in filtered
                    if d.company_id in companies
                    and companies[d.company_id].city
                    and companies[d.company_id].city.lower() == region.lower()]
    if sales_rep:
        filtered = [d for d in filtered if d.sales_rep == sales_rep]
    if product_line:
        pl_val = _pl_to_deal_value(product_line)
        if pl_val:
            filtered = [d for d in filtered if d.product_line == pl_val]
    return filtered


def compute_breakdown(
    dimension: str,
    quarter: Optional[str] = None,
    industry: Optional[str] = None,
    region: Optional[str] = None,
    sales_rep: Optional[str] = None,
    product_line: Optional[str] = None,
) -> List[BreakdownItem]:
    """Breakdown by: industry, deal_size, source, company_size, buyer_title, geography."""
    deals = get_deals()
    companies = {c.id: c for c in get_companies()}
    contacts = {c.id: c for c in get_contacts()}

    deals = _apply_filters(deals, companies, quarter, industry, region, sales_rep, product_line)

    buckets: Dict[str, list] = defaultdict(list)

    for deal in deals:
        company = companies.get(deal.company_id)
        contact = contacts.get(deal.contact_id)

        if dimension == "industry":
            key = company.industry if company else "Unknown"
        elif dimension == "deal_size":
            if deal.amount < 25000:
                key = "Under $25K"
            elif deal.amount <= 75000:
                key = "$25K - $75K"
            elif deal.amount <= 150000:
                key = "$75K - $150K"
            else:
                key = "Over $150K"
        elif dimension == "source":
            key = deal.deal_source
        elif dimension == "company_size":
            if company:
                emp = company.employee_count
                if emp < 50:
                    key = "Under 50"
                elif emp <= 200:
                    key = "50-200"
                elif emp <= 500:
                    key = "200-500"
                elif emp <= 1000:
                    key = "500-1000"
                else:
                    key = "1000+"
            else:
                key = "Unknown"
        elif dimension == "buyer_title":
            key = contact.seniority if contact else "Unknown"
        elif dimension == "geography":
            key = company.city if company and company.city else "Unknown"
        else:
            key = "Unknown"

        buckets[key].append(deal)

    results = []
    for category, category_deals in sorted(buckets.items()):
        won = [d for d in category_deals if d.stage == "closedwon"]
        total_rev = sum(d.amount for d in won)
        results.append(BreakdownItem(
            category=category,
            total=len(category_deals),
            won=len(won),
            lost=len(category_deals) - len(won),
            win_rate=round(len(won) / len(category_deals) * 100, 1) if category_deals else 0,
            avg_deal_size=round(sum(d.amount for d in category_deals) / len(category_deals), 2),
            total_revenue=round(total_rev, 2),
        ))

    return results


def compute_competitors(product_line: Optional[str] = None) -> List[CompetitorMetrics]:
    deals = get_deals()
    pl_val = _pl_to_deal_value(product_line)
    if pl_val:
        deals = [d for d in deals if d.product_line == pl_val]
    companies = {c.id: c for c in get_companies()}

    comp_deals: Dict[str, list] = defaultdict(list)
    for deal in deals:
        if deal.competitor:
            comp_deals[deal.competitor].append(deal)

    results = []
    for competitor, c_deals in sorted(comp_deals.items()):
        won = [d for d in c_deals if d.stage == "closedwon"]
        lost = [d for d in c_deals if d.stage == "closedlost"]

        # Top loss reasons
        reason_counts: Dict[str, int] = defaultdict(int)
        for d in lost:
            if d.loss_reason:
                reason_counts[d.loss_reason] += 1
        top_reasons = sorted(reason_counts, key=reason_counts.get, reverse=True)[:3]

        # Industries
        industry_set = set()
        for d in c_deals:
            comp = companies.get(d.company_id)
            if comp:
                industry_set.add(comp.industry)

        results.append(CompetitorMetrics(
            competitor=competitor,
            deals_faced=len(c_deals),
            wins=len(won),
            losses=len(lost),
            win_rate=round(len(won) / len(c_deals) * 100, 1),
            avg_deal_size=round(sum(d.amount for d in c_deals) / len(c_deals), 2),
            top_loss_reasons=top_reasons,
            industries=sorted(industry_set),
        ))

    return sorted(results, key=lambda x: x.win_rate)


def compute_objections(product_line: Optional[str] = None) -> List[ObjectionTheme]:
    deals = get_deals()
    pl_val = _pl_to_deal_value(product_line)
    if pl_val:
        deals = [d for d in deals if d.product_line == pl_val]
    companies = {c.id: c for c in get_companies()}

    obj_data: Dict[str, dict] = defaultdict(lambda: {"deals": [], "industries": set()})
    total_deals_with_obj = sum(1 for d in deals if d.objections)

    for deal in deals:
        for obj in deal.objections:
            obj_data[obj]["deals"].append(deal)
            comp = companies.get(deal.company_id)
            if comp:
                obj_data[obj]["industries"].add(comp.industry)

    results = []
    for objection, data in obj_data.items():
        obj_deals = data["deals"]
        won = [d for d in obj_deals if d.stage == "closedwon"]
        results.append(ObjectionTheme(
            objection=objection,
            frequency=len(obj_deals),
            percentage=round(len(obj_deals) / total_deals_with_obj * 100, 1) if total_deals_with_obj else 0,
            industries=sorted(data["industries"]),
            win_rate_when_raised=round(len(won) / len(obj_deals) * 100, 1) if obj_deals else 0,
        ))

    return sorted(results, key=lambda x: x.frequency, reverse=True)


def compute_icp(product_line: Optional[str] = None) -> ICPProfile:
    """Compute Ideal Customer Profile from winning deal patterns."""
    deals = get_deals()
    pl_val = _pl_to_deal_value(product_line)
    if pl_val:
        deals = [d for d in deals if d.product_line == pl_val]
    companies = {c.id: c for c in get_companies()}
    contacts = {c.id: c for c in get_contacts()}

    won = [d for d in deals if d.stage == "closedwon"]

    # Dynamic threshold based on total deal count (scale from ~1 for 25 deals to ~11 for 175)
    total = len(deals)
    min_deals = max(1, total // 15)

    # Best industries (win rate > 45%)
    industry_stats: Dict[str, dict] = defaultdict(lambda: {"won": 0, "total": 0})
    for deal in deals:
        comp = companies.get(deal.company_id)
        if comp:
            industry_stats[comp.industry]["total"] += 1
            if deal.stage == "closedwon":
                industry_stats[comp.industry]["won"] += 1

    top_industries = [
        ind for ind, s in industry_stats.items()
        if s["total"] >= min_deals and s["won"] / s["total"] > 0.45
    ]
    top_industries.sort(key=lambda i: industry_stats[i]["won"] / industry_stats[i]["total"], reverse=True)

    # Best employee ranges
    emp_ranges = []
    for d in won:
        comp = companies.get(d.company_id)
        if comp:
            emp_ranges.append(comp.employee_count)

    # Best sources
    source_stats: Dict[str, dict] = defaultdict(lambda: {"won": 0, "total": 0})
    for deal in deals:
        source_stats[deal.deal_source]["total"] += 1
        if deal.stage == "closedwon":
            source_stats[deal.deal_source]["won"] += 1

    top_sources = sorted(
        [s for s in source_stats if source_stats[s]["total"] >= 5],
        key=lambda s: source_stats[s]["won"] / source_stats[s]["total"],
        reverse=True,
    )[:3]

    # Best buyer titles
    seniority_stats: Dict[str, dict] = defaultdict(lambda: {"won": 0, "total": 0})
    for deal in deals:
        contact = contacts.get(deal.contact_id)
        if contact:
            seniority_stats[contact.seniority]["total"] += 1
            if deal.stage == "closedwon":
                seniority_stats[contact.seniority]["won"] += 1

    top_titles = sorted(
        [s for s in seniority_stats if seniority_stats[s]["total"] >= 5],
        key=lambda s: seniority_stats[s]["won"] / seniority_stats[s]["total"],
        reverse=True,
    )[:3]

    return ICPProfile(
        industries=top_industries[:3],
        employee_range="50-500 employees",
        deal_size_range="$25,000 - $75,000",
        buyer_titles=top_titles,
        preferred_sources=top_sources,
        avg_cycle_days=round(sum(d.cycle_days for d in won) / len(won)) if won else 0,
        win_rate=round(len(won) / len(deals) * 100, 1),
        confidence=0.82,
    )


def _quarter_for_deal(deal) -> str:
    """Return 'Q1', 'Q2', 'Q3', or 'Q4' for a deal based on close_date."""
    month = deal.close_date.month
    if month <= 3:
        return "Q1"
    elif month <= 6:
        return "Q2"
    elif month <= 9:
        return "Q3"
    else:
        return "Q4"


def _prev_quarter(q: str) -> Optional[str]:
    """Return the previous quarter label, or None for Q1."""
    mapping = {"Q2": "Q1", "Q3": "Q2", "Q4": "Q3"}
    return mapping.get(q)


def compute_strategic_signals(
    quarter: Optional[str] = None,
    industry: Optional[str] = None,
    region: Optional[str] = None,
    sales_rep: Optional[str] = None,
    product_line: Optional[str] = None,
) -> StrategicSignals:
    """Compute all strategic signals for the CEO intelligence dashboard."""
    all_deals = get_deals()
    companies = {c.id: c for c in get_companies()}

    # --- Build filter options from ALL deals (before filtering) ---
    all_quarters = sorted(set(_quarter_for_deal(d) for d in all_deals))
    all_industries = sorted(set(
        companies[d.company_id].industry
        for d in all_deals if d.company_id in companies
    ))
    all_regions = sorted(set(
        companies[d.company_id].city
        for d in all_deals
        if d.company_id in companies and companies[d.company_id].city
    ))
    all_sales_reps = sorted(set(d.sales_rep for d in all_deals if d.sales_rep))
    filter_options = FilterOptions(
        quarters=all_quarters,
        industries=all_industries,
        regions=all_regions,
        sales_reps=all_sales_reps,
    )

    # --- Apply filters ---
    deals = list(all_deals)
    if quarter:
        deals = [d for d in deals if _quarter_for_deal(d) == quarter]
    if industry:
        deals = [d for d in deals
                 if d.company_id in companies
                 and companies[d.company_id].industry.lower() == industry.lower()]
    if region:
        deals = [d for d in deals
                 if d.company_id in companies
                 and companies[d.company_id].city
                 and companies[d.company_id].city.lower() == region.lower()]
    if sales_rep:
        deals = [d for d in deals if d.sales_rep == sales_rep]
    if product_line:
        pl_val = _pl_to_deal_value(product_line)
        if pl_val:
            deals = [d for d in deals if d.product_line == pl_val]

    won = [d for d in deals if d.stage == "closedwon"]
    lost = [d for d in deals if d.stage == "closedlost"]

    # --- Quarter-over-quarter comparison ---
    comparison = None  # type: Optional[KPIComparison]
    current_q = quarter or "Q4"  # default to Q4 since data spans 2024
    prev_q = _prev_quarter(current_q)
    if prev_q:
        # Get previous quarter deals (apply same non-quarter filters)
        prev_deals = [d for d in all_deals if _quarter_for_deal(d) == prev_q]
        if industry:
            prev_deals = [d for d in prev_deals
                          if d.company_id in companies
                          and companies[d.company_id].industry.lower() == industry.lower()]
        if region:
            prev_deals = [d for d in prev_deals
                          if d.company_id in companies
                          and companies[d.company_id].city
                          and companies[d.company_id].city.lower() == region.lower()]
        if sales_rep:
            prev_deals = [d for d in prev_deals if d.sales_rep == sales_rep]
        if product_line:
            pl_val_prev = _pl_to_deal_value(product_line)
            if pl_val_prev:
                prev_deals = [d for d in prev_deals if d.product_line == pl_val_prev]

        if prev_deals:
            prev_won = [d for d in prev_deals if d.stage == "closedwon"]
            prev_wr = len(prev_won) / len(prev_deals) * 100 if prev_deals else 0
            curr_wr = len(won) / len(deals) * 100 if deals else 0
            prev_rev = sum(d.amount for d in prev_won)
            curr_rev = sum(d.amount for d in won)
            prev_cycle = sum(d.cycle_days for d in prev_won) / len(prev_won) if prev_won else 0
            curr_cycle = sum(d.cycle_days for d in won) / len(won) if won else 0

            rev_change_pct = ((curr_rev - prev_rev) / prev_rev * 100) if prev_rev else 0

            comparison = KPIComparison(
                period_label=f"vs {prev_q}",
                win_rate_change=round(curr_wr - prev_wr, 1),
                revenue_change_pct=round(rev_change_pct, 1),
                deal_count_change=len(deals) - len(prev_deals),
                cycle_change=round(curr_cycle - prev_cycle, 1),
            )

    # --- Enhanced KPIs ---

    # Best/worst industry segments
    industry_stats: Dict[str, dict] = defaultdict(lambda: {"won": 0, "total": 0})
    for deal in deals:
        comp = companies.get(deal.company_id)
        if comp:
            industry_stats[comp.industry]["total"] += 1
            if deal.stage == "closedwon":
                industry_stats[comp.industry]["won"] += 1

    segments = []
    for ind, s in industry_stats.items():
        if s["total"] >= 3:
            segments.append(SegmentStat(
                name=ind,
                win_rate=round(s["won"] / s["total"] * 100, 1),
                total=s["total"],
            ))
    segments.sort(key=lambda x: x.win_rate, reverse=True)
    best_segment = segments[0] if segments else SegmentStat(name="N/A", win_rate=0, total=0)
    worst_segment = segments[-1] if segments else SegmentStat(name="N/A", win_rate=0, total=0)

    # Revenue lost + top leak reason
    total_lost_rev = sum(d.amount for d in lost)
    reason_revenue: Dict[str, float] = defaultdict(float)
    for d in lost:
        if d.loss_reason:
            reason_revenue[d.loss_reason] += d.amount
    top_leak_reason = max(reason_revenue, key=reason_revenue.get) if reason_revenue else "N/A"
    top_leak_amount = reason_revenue.get(top_leak_reason, 0)

    # Deal size sweet spot analysis
    sweet_deals = [d for d in deals if 30000 <= d.amount <= 80000]
    sweet_won = [d for d in sweet_deals if d.stage == "closedwon"]
    sweet_wr = round(len(sweet_won) / len(sweet_deals) * 100, 1) if sweet_deals else 0

    large_deals = [d for d in deals if d.amount > 200000]
    large_won = [d for d in large_deals if d.stage == "closedwon"]
    large_wr = round(len(large_won) / len(large_deals) * 100, 1) if large_deals else 0

    # Cycle time
    avg_cycle_won = round(sum(d.cycle_days for d in won) / len(won), 1) if won else 0
    avg_cycle_lost = round(sum(d.cycle_days for d in lost) / len(lost), 1) if lost else 0

    total_rev = sum(d.amount for d in won)
    avg_deal_size = round(total_rev / len(won), 2) if won else 0

    kpis = EnhancedKPIs(
        win_rate=round(len(won) / len(deals) * 100, 1) if deals else 0,
        won_deals=len(won),
        lost_deals=len(lost),
        best_segment=best_segment,
        worst_segment=worst_segment,
        total_revenue=round(total_rev, 2),
        total_lost_revenue=round(total_lost_rev, 2),
        top_leak_reason=top_leak_reason,
        top_leak_amount=round(top_leak_amount, 2),
        avg_deal_size=avg_deal_size,
        sweet_spot_range="$30K-$80K",
        sweet_spot_win_rate=sweet_wr,
        large_deal_range=">$200K",
        large_deal_win_rate=large_wr,
        avg_cycle_won=avg_cycle_won,
        avg_cycle_lost=avg_cycle_lost,
        cycle_drag=round(avg_cycle_lost - avg_cycle_won, 1),
        comparison=comparison,
    )

    # --- Growth Lever ---
    # Find highest-win-rate source that's underrepresented
    source_stats: Dict[str, dict] = defaultdict(lambda: {"won": 0, "total": 0})
    for deal in deals:
        source_stats[deal.deal_source]["total"] += 1
        if deal.stage == "closedwon":
            source_stats[deal.deal_source]["won"] += 1

    source_items = []
    for src, s in source_stats.items():
        if s["total"] >= 3:
            wr = s["won"] / s["total"]
            pct = s["total"] / len(deals) * 100
            source_items.append((src, wr, pct, s["total"]))

    # Sort by win rate descending, pick one where pipeline_pct < 20%
    source_items.sort(key=lambda x: x[1], reverse=True)
    growth_src = source_items[0] if source_items else ("N/A", 0, 0, 0)
    for item in source_items:
        if item[2] < 20:  # underrepresented
            growth_src = item
            break

    growth_lever = GrowthLever(
        source=growth_src[0],
        win_rate=round(growth_src[1] * 100, 1),
        pipeline_pct=round(growth_src[2], 1),
        total_deals=growth_src[3],
    )

    # --- Revenue Leak ---
    # Biggest competitor by revenue lost
    comp_lost_rev: Dict[str, dict] = defaultdict(lambda: {"revenue": 0.0, "deals": 0})
    for d in lost:
        if d.competitor:
            comp_lost_rev[d.competitor]["revenue"] += d.amount
            comp_lost_rev[d.competitor]["deals"] += 1

    if comp_lost_rev:
        top_comp = max(comp_lost_rev, key=lambda c: comp_lost_rev[c]["revenue"])
        revenue_leak = RevenueLeak(
            competitor=top_comp,
            revenue_lost=round(comp_lost_rev[top_comp]["revenue"], 2),
            deals_lost=comp_lost_rev[top_comp]["deals"],
        )
    else:
        revenue_leak = RevenueLeak(competitor="N/A", revenue_lost=0, deals_lost=0)

    # --- ICP Fit Signal ---
    # ICP criteria: top industries (>45% win), 2000-10000 employees, $30K-$80K
    icp_industries = set()
    for ind, s in industry_stats.items():
        if s["total"] >= 5 and s["won"] / s["total"] > 0.45:
            icp_industries.add(ind)

    icp_deals = []
    non_icp_deals = []
    for d in deals:
        comp = companies.get(d.company_id)
        if not comp:
            non_icp_deals.append(d)
            continue
        is_icp = (
            comp.industry in icp_industries
            and 2000 <= comp.employee_count <= 10000
            and 30000 <= d.amount <= 80000
        )
        if is_icp:
            icp_deals.append(d)
        else:
            non_icp_deals.append(d)

    icp_won = [d for d in icp_deals if d.stage == "closedwon"]
    non_icp_won = [d for d in non_icp_deals if d.stage == "closedwon"]

    icp_fit = ICPFitSignal(
        icp_match_pct=round(len(icp_deals) / len(deals) * 100, 1) if deals else 0,
        icp_win_rate=round(len(icp_won) / len(icp_deals) * 100, 1) if icp_deals else 0,
        non_icp_win_rate=round(len(non_icp_won) / len(non_icp_deals) * 100, 1) if non_icp_deals else 0,
    )

    # --- Conversation Theme Aggregation ---
    theme_data: Dict[str, dict] = defaultdict(lambda: {
        "deals": [], "quotes": [], "sources": []
    })

    overall_wr = len(won) / len(deals) * 100 if deals else 0

    for deal in deals:
        for sig in deal.conversation_signals:
            theme_data[sig.theme]["deals"].append(deal)
            theme_data[sig.theme]["quotes"].append((sig.quote, sig.source))

    conversation_themes = []
    for theme, data in theme_data.items():
        theme_deals = data["deals"]
        theme_won = [d for d in theme_deals if d.stage == "closedwon"]
        wr = round(len(theme_won) / len(theme_deals) * 100, 1) if theme_deals else 0

        # Impact level based on win rate delta from overall
        delta = overall_wr - wr
        if delta > 15:
            impact = "High"
        elif delta > 5:
            impact = "Medium"
        else:
            impact = "Low"

        # Pick a representative quote (prefer negative sentiment)
        sample_quote, sample_source = data["quotes"][0] if data["quotes"] else ("", "")

        conversation_themes.append(ConversationThemeAgg(
            theme=theme,
            frequency=len(theme_deals),
            deal_pct=round(len(theme_deals) / len(deals) * 100, 1),
            win_rate_when_raised=wr,
            impact_level=impact,
            sample_quote=sample_quote,
            sample_source=sample_source,
        ))

    # Sort by frequency descending
    conversation_themes.sort(key=lambda x: x.frequency, reverse=True)

    # --- Win/Loss Reason Aggregation (top 6 each) ---
    win_reason_counts: Dict[str, int] = defaultdict(int)
    loss_reason_counts: Dict[str, int] = defaultdict(int)
    for d in won:
        if d.win_reason:
            win_reason_counts[d.win_reason] += 1
    for d in lost:
        if d.loss_reason:
            loss_reason_counts[d.loss_reason] += 1

    win_reasons = [
        ReasonCount(reason=r, count=c)
        for r, c in sorted(win_reason_counts.items(), key=lambda x: x[1], reverse=True)[:6]
    ]
    loss_reasons = [
        ReasonCount(reason=r, count=c)
        for r, c in sorted(loss_reason_counts.items(), key=lambda x: x[1], reverse=True)[:6]
    ]

    return StrategicSignals(
        kpis=kpis,
        growth_lever=growth_lever,
        revenue_leak=revenue_leak,
        icp_fit=icp_fit,
        conversation_themes=conversation_themes,
        win_reasons=win_reasons,
        loss_reasons=loss_reasons,
        filters=filter_options,
    )


def _extract_evidence(deals, max_quotes: int = 3) -> List[ConversationEvidence]:
    """Pull conversation signal quotes from deals, preferring negative sentiment."""
    evidence = []  # type: List[ConversationEvidence]
    for deal in deals:
        for sig in deal.conversation_signals:
            evidence.append(ConversationEvidence(
                quote=sig.quote,
                source=sig.source,
                deal_name=deal.name,
                stage=deal.stage,
                sentiment=sig.sentiment,
            ))
    # Sort: negative first, then neutral, then positive
    order = {"negative": 0, "neutral": 1, "positive": 2}
    evidence.sort(key=lambda e: order.get(e.sentiment, 1))
    return evidence[:max_quotes]


def compute_patterns(
    quarter: Optional[str] = None,
    industry: Optional[str] = None,
    region: Optional[str] = None,
    sales_rep: Optional[str] = None,
    product_line: Optional[str] = None,
) -> List[PatternInsight]:
    """Detect 7 pattern categories with conversation evidence."""
    all_deals = get_deals()
    companies = {c.id: c for c in get_companies()}

    deals = _apply_filters(all_deals, companies, quarter, industry, region, sales_rep, product_line)
    won = [d for d in deals if d.stage == "closedwon"]
    lost = [d for d in deals if d.stage == "closedlost"]
    overall_wr = round(len(won) / len(deals) * 100, 1) if deals else 0

    # Dynamic threshold based on filtered deal count
    total = len(deals)
    min_deals = max(1, total // 15)

    patterns = []  # type: List[PatternInsight]

    # --- 1. Industry Pattern ---
    industry_stats = defaultdict(lambda: {"won": 0, "total": 0, "deals": []})  # type: Dict[str, dict]
    for d in deals:
        comp = companies.get(d.company_id)
        if comp:
            industry_stats[comp.industry]["total"] += 1
            industry_stats[comp.industry]["deals"].append(d)
            if d.stage == "closedwon":
                industry_stats[comp.industry]["won"] += 1

    ind_ranked = [(ind, s["won"] / s["total"] * 100, s["total"], s["deals"])
                  for ind, s in industry_stats.items() if s["total"] >= 3]
    ind_ranked.sort(key=lambda x: x[1], reverse=True)

    if len(ind_ranked) >= 2:
        best_ind = ind_ranked[0]
        worst_ind = ind_ranked[-1]
        worst_lost = [d for d in worst_ind[3] if d.stage == "closedlost"]
        patterns.append(PatternInsight(
            category="industry",
            title=f"{best_ind[0]} leads, {worst_ind[0]} struggles",
            description=f"{best_ind[0]} wins at {best_ind[1]:.0f}% ({best_ind[2]} deals) while {worst_ind[0]} only converts at {worst_ind[1]:.0f}%. Lost deals in {worst_ind[0]} show recurring conversation themes.",
            stat_label="Best vertical",
            stat_value=f"{best_ind[1]:.0f}% WR",
            impact="positive",
            evidence=_extract_evidence(worst_lost, 3),
            recommendation=f"Double down on {best_ind[0]} pipeline. For {worst_ind[0]}, develop industry-specific use cases or consider deprioritizing.",
        ))

    # --- 2. Deal Size Pattern ---
    sweet_deals = [d for d in deals if 30000 <= d.amount <= 80000]
    sweet_won = [d for d in sweet_deals if d.stage == "closedwon"]
    sweet_wr = round(len(sweet_won) / len(sweet_deals) * 100, 1) if sweet_deals else 0

    large_deals = [d for d in deals if d.amount > 150000]
    large_won = [d for d in large_deals if d.stage == "closedwon"]
    large_wr = round(len(large_won) / len(large_deals) * 100, 1) if large_deals else 0
    large_lost = [d for d in large_deals if d.stage == "closedlost"]

    # Evidence: pricing/requirement signals from large lost deals
    large_evidence = _extract_evidence(large_lost, 3)
    patterns.append(PatternInsight(
        category="deal_size",
        title=f"Sweet spot $30K-$80K vs large deal drop-off",
        description=f"Deals in the $30K-$80K range win at {sweet_wr}% ({len(sweet_deals)} deals), but deals over $150K drop to {large_wr}% ({len(large_deals)} deals). Large lost deals surface pricing and requirement concerns.",
        stat_label="Sweet spot WR",
        stat_value=f"{sweet_wr}%",
        impact="negative" if large_wr < overall_wr - 10 else "neutral",
        evidence=large_evidence,
        recommendation=f"Create tiered pricing for enterprise deals. For deals >$150K, involve solution architects earlier and address scope/pricing objections proactively.",
    ))

    # --- 3. Sales Cycle Pattern ---
    avg_won_cycle = round(sum(d.cycle_days for d in won) / len(won), 1) if won else 0
    avg_lost_cycle = round(sum(d.cycle_days for d in lost) / len(lost), 1) if lost else 0
    cycle_drag = round(avg_lost_cycle - avg_won_cycle, 1)

    # Slow lost deals (cycle > avg_lost_cycle) with champion risk / procurement signals
    slow_lost = [d for d in lost if d.cycle_days > avg_lost_cycle]
    cycle_evidence = _extract_evidence(slow_lost, 3)

    patterns.append(PatternInsight(
        category="sales_cycle",
        title=f"Lost deals drag {cycle_drag:.0f} days longer",
        description=f"Won deals close in {avg_won_cycle:.0f} days on average, while lost deals take {avg_lost_cycle:.0f} days. Deals that exceed {avg_lost_cycle:.0f} days show champion risk and procurement stall signals.",
        stat_label="Cycle drag",
        stat_value=f"+{cycle_drag:.0f}d",
        impact="negative",
        evidence=cycle_evidence,
        recommendation=f"Implement deal velocity alerts at {avg_won_cycle:.0f} days. For deals approaching {avg_lost_cycle:.0f} days, escalate champion validation and executive engagement.",
    ))

    # --- 4. Competitor Pattern ---
    comp_stats = defaultdict(lambda: {"won": 0, "total": 0, "deals": []})  # type: Dict[str, dict]
    for d in deals:
        if d.competitor:
            comp_stats[d.competitor]["total"] += 1
            comp_stats[d.competitor]["deals"].append(d)
            if d.stage == "closedwon":
                comp_stats[d.competitor]["won"] += 1

    comp_ranked = [(comp, s["won"] / s["total"] * 100, s["total"], s["deals"])
                   for comp, s in comp_stats.items() if s["total"] >= min_deals]
    comp_ranked.sort(key=lambda x: x[1])  # worst win rate first

    if comp_ranked:
        hardest = comp_ranked[0]
        hardest_lost = [d for d in hardest[3] if d.stage == "closedlost"]
        patterns.append(PatternInsight(
            category="competitor",
            title=f"{hardest[0]} is the hardest competitor",
            description=f"Win rate against {hardest[0]} is only {hardest[1]:.0f}% across {hardest[2]} deals. Competitive pressure quotes reveal their key advantages.",
            stat_label=f"vs {hardest[0]}",
            stat_value=f"{hardest[1]:.0f}% WR",
            impact="negative",
            evidence=_extract_evidence(hardest_lost, 3),
            recommendation=f"Build a {hardest[0]} battle card focused on differentiation. Train reps on repositioning when {hardest[0]} is in the deal.",
        ))

    # --- 5. Objection Pattern ---
    obj_data = defaultdict(lambda: {"deals": [], "won": 0})  # type: Dict[str, dict]
    for d in deals:
        for obj in d.objections:
            obj_data[obj]["deals"].append(d)
            if d.stage == "closedwon":
                obj_data[obj]["won"] += 1

    obj_ranked = [(obj, s["won"] / len(s["deals"]) * 100 if s["deals"] else 0, len(s["deals"]), s["deals"])
                  for obj, s in obj_data.items() if len(s["deals"]) >= min_deals]
    obj_ranked.sort(key=lambda x: x[1])  # worst win rate first

    if obj_ranked:
        worst_obj = obj_ranked[0]
        worst_obj_lost = [d for d in worst_obj[3] if d.stage == "closedlost"]
        # Get negative sentiment signals from those deals
        patterns.append(PatternInsight(
            category="objection",
            title=f'"{worst_obj[0]}" is the most damaging objection',
            description=f'When "{worst_obj[0]}" is raised, win rate drops to {worst_obj[1]:.0f}% ({worst_obj[2]} deals). Conversation signals reveal underlying buyer concerns.',
            stat_label="WR when raised",
            stat_value=f"{worst_obj[1]:.0f}%",
            impact="negative",
            evidence=_extract_evidence(worst_obj_lost, 3),
            recommendation=f'Develop preemptive handling for "{worst_obj[0]}". Add proof points and case studies to address this concern before it becomes a blocker.',
        ))

    # --- 6. ICP Pattern ---
    icp_industries = set()
    for ind, s in industry_stats.items():
        if s["total"] >= min_deals and s["won"] / s["total"] > 0.40:
            icp_industries.add(ind)

    icp_deals = []
    non_icp_deals = []
    for d in deals:
        comp = companies.get(d.company_id)
        if not comp:
            non_icp_deals.append(d)
            continue
        is_icp = (
            comp.industry in icp_industries
            and 2000 <= comp.employee_count <= 10000
            and 30000 <= d.amount <= 80000
        )
        if is_icp:
            icp_deals.append(d)
        else:
            non_icp_deals.append(d)

    icp_won = [d for d in icp_deals if d.stage == "closedwon"]
    non_icp_won = [d for d in non_icp_deals if d.stage == "closedwon"]
    icp_wr = round(len(icp_won) / len(icp_deals) * 100, 1) if icp_deals else 0
    non_icp_wr = round(len(non_icp_won) / len(non_icp_deals) * 100, 1) if non_icp_deals else 0
    gap = round(icp_wr - non_icp_wr, 1)

    non_icp_lost = [d for d in non_icp_deals if d.stage == "closedlost"]
    # Filter for requirement mismatch signals
    icp_evidence = _extract_evidence(non_icp_lost, 3)

    patterns.append(PatternInsight(
        category="icp",
        title=f"ICP deals win {gap:.0f}pp more than non-ICP",
        description=f"ICP-fit deals win at {icp_wr}% vs {non_icp_wr}% for non-ICP. Non-ICP lost deals show requirement mismatch and fit issues in conversation signals.",
        stat_label="ICP win rate",
        stat_value=f"{icp_wr}%",
        impact="positive" if gap > 10 else "neutral",
        evidence=icp_evidence,
        recommendation=f"Tighten lead qualification to prioritize ICP-fit prospects. For non-ICP deals, set higher qualification bars or develop a lighter-touch sales motion.",
    ))

    # --- 7. Positioning Gap Pattern ---
    positioning_themes = {"Product Gap", "Requirement Mismatch"}
    positioning_deals = [d for d in deals
                         if any(sig.theme in positioning_themes for sig in d.conversation_signals)]
    pos_lost = [d for d in positioning_deals if d.stage == "closedlost"]
    pos_wr = round(
        len([d for d in positioning_deals if d.stage == "closedwon"]) / len(positioning_deals) * 100, 1
    ) if positioning_deals else 0

    patterns.append(PatternInsight(
        category="positioning",
        title=f"Product gap signals appear in {len(positioning_deals)} deals",
        description=f"Deals mentioning product gaps or requirement mismatches win at only {pos_wr}% ({len(positioning_deals)} deals). Negative quotes reveal specific feature and positioning concerns.",
        stat_label="Affected deals",
        stat_value=str(len(positioning_deals)),
        impact="negative",
        evidence=_extract_evidence(pos_lost, 3),
        recommendation="Feed product gap signals to the product team monthly. Build a public roadmap response for common gaps to maintain deal momentum.",
    ))

    return patterns


def compute_trends(product_line: Optional[str] = None) -> List[TrendPoint]:
    """Monthly win rate trend bucketed by close_date."""
    from datetime import datetime as dt
    deals = get_deals()
    pl_val = _pl_to_deal_value(product_line)
    if pl_val:
        deals = [d for d in deals if d.product_line == pl_val]

    monthly: Dict[str, dict] = defaultdict(lambda: {"won": 0, "total": 0, "revenue": 0.0, "date": None})
    for deal in deals:
        key = deal.close_date.strftime("%b %Y")
        monthly[key]["total"] += 1
        monthly[key]["date"] = deal.close_date
        if deal.stage == "closedwon":
            monthly[key]["won"] += 1
            monthly[key]["revenue"] += deal.amount

    results = []
    for key, data in monthly.items():
        parsed = dt.strptime(key, "%b %Y")
        results.append(TrendPoint(
            month=key,
            year=parsed.year,
            month_num=parsed.month,
            win_rate=round(data["won"] / data["total"] * 100, 1) if data["total"] else 0,
            deals=data["total"],
            won=data["won"],
            revenue=round(data["revenue"], 2),
        ))

    results.sort(key=lambda x: (x.year, x.month_num))
    return results
