"""Claude AI service with 7 prompt templates and response caching."""

import json
from typing import Dict, List, Optional
from collections import defaultdict
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from services.analytics import (
    compute_overview, compute_breakdown, compute_competitors,
    compute_objections, compute_icp, _pl_to_deal_value,
)
from services.data_source import get_deals, get_companies, get_contacts

# Response cache
_cache: Dict[str, str] = {}


def clear_insights_cache() -> None:
    """Clear cached AI insights when data source changes."""
    _cache.clear()

SYSTEM_PROMPT = """You are an expert B2B sales analyst and strategy consultant. You analyze CRM deal data to find patterns, generate insights, and provide actionable recommendations.

Rules:
- Be specific and data-driven. Reference actual numbers from the data.
- Use markdown formatting for readability.
- Keep responses concise but comprehensive.
- Focus on actionable insights, not just observations.
- When recommending actions, be specific about what to do differently.
"""


def _get_data_context() -> str:
    """Build a comprehensive data summary string for AI prompts."""
    overview = compute_overview()
    industry_breakdown = compute_breakdown("industry")
    size_breakdown = compute_breakdown("deal_size")
    source_breakdown = compute_breakdown("source")
    company_size = compute_breakdown("company_size")
    buyer_breakdown = compute_breakdown("buyer_title")
    geo_breakdown = compute_breakdown("geography")
    competitors = compute_competitors()
    objections = compute_objections()
    icp = compute_icp()

    deals = get_deals()
    companies = {c.id: c for c in get_companies()}

    # Product line stats
    pl_stats = defaultdict(lambda: {"won": 0, "total": 0, "revenue": 0.0})  # type: Dict[str, dict]
    for d in deals:
        pl_stats[d.product_line]["total"] += 1
        if d.stage == "closedwon":
            pl_stats[d.product_line]["won"] += 1
            pl_stats[d.product_line]["revenue"] += d.amount

    # Sales rep stats
    rep_stats = defaultdict(lambda: {"won": 0, "total": 0, "revenue": 0.0})  # type: Dict[str, dict]
    for d in deals:
        if d.sales_rep:
            rep_stats[d.sales_rep]["total"] += 1
            if d.stage == "closedwon":
                rep_stats[d.sales_rep]["won"] += 1
                rep_stats[d.sales_rep]["revenue"] += d.amount

    # Conversation signal aggregation
    theme_data = defaultdict(lambda: {"quotes": [], "deal_count": 0, "won": 0})  # type: Dict[str, dict]
    for d in deals:
        for sig in d.conversation_signals:
            theme_data[sig.theme]["deal_count"] += 1
            if d.stage == "closedwon":
                theme_data[sig.theme]["won"] += 1
            theme_data[sig.theme]["quotes"].append((sig.quote, sig.sentiment, sig.source))

    # Sample deals
    won_deals = sorted([d for d in deals if d.stage == "closedwon"], key=lambda d: d.close_date, reverse=True)[:5]
    lost_deals = sorted([d for d in deals if d.stage == "closedlost"], key=lambda d: d.close_date, reverse=True)[:5]

    return f"""
## Dataset Summary
- Total deals: {overview.total_deals} | Won: {overview.won_deals} | Lost: {overview.lost_deals}
- Overall win rate: {overview.win_rate}%
- Total revenue (won): ${overview.total_revenue:,.0f}
- Avg deal size (won): ${overview.avg_deal_size:,.0f}
- Avg cycle (won): {overview.avg_cycle_won} days | Avg cycle (lost): {overview.avg_cycle_lost} days

## Win Rate by Industry
{chr(10).join(f"- {b.category}: {b.win_rate}% ({b.won}/{b.total} deals, ${b.total_revenue:,.0f} revenue)" for b in industry_breakdown)}

## Win Rate by Deal Size
{chr(10).join(f"- {b.category}: {b.win_rate}% ({b.won}/{b.total} deals)" for b in size_breakdown)}

## Win Rate by Source
{chr(10).join(f"- {b.category}: {b.win_rate}% ({b.won}/{b.total} deals)" for b in source_breakdown)}

## Win Rate by Company Size
{chr(10).join(f"- {b.category}: {b.win_rate}% ({b.won}/{b.total} deals)" for b in company_size)}

## Win Rate by Buyer Seniority
{chr(10).join(f"- {b.category}: {b.win_rate}% ({b.won}/{b.total} deals)" for b in buyer_breakdown)}

## Win Rate by Geography
{chr(10).join(f"- {b.category}: {b.win_rate}% ({b.won}/{b.total} deals, ${b.total_revenue:,.0f} revenue)" for b in geo_breakdown)}

## Win Rate by Product Line
{chr(10).join(f"- {pl}: {round(s['won']/s['total']*100,1) if s['total'] else 0}% ({s['won']}/{s['total']} deals, ${s['revenue']:,.0f} revenue)" for pl, s in sorted(pl_stats.items()))}

## Sales Rep Performance
{chr(10).join(f"- {rep}: {round(s['won']/s['total']*100,1)}% win rate ({s['won']}/{s['total']} deals, ${s['revenue']:,.0f} revenue)" for rep, s in sorted(rep_stats.items(), key=lambda x: x[1]['won']/x[1]['total'] if x[1]['total'] else 0, reverse=True))}

## Competitor Analysis
{chr(10).join(f"- {c.competitor}: {c.win_rate}% win rate ({c.wins}/{c.deals_faced} deals), top loss reasons: {', '.join(c.top_loss_reasons)}" for c in competitors)}

## Top Objections
{chr(10).join(f"- {o.objection}: raised {o.frequency} times, {o.win_rate_when_raised}% win rate when raised, industries: {', '.join(o.industries)}" for o in objections)}

## Current ICP
- Industries: {', '.join(icp.industries)}
- Company size: {icp.employee_range}
- Deal size: {icp.deal_size_range}
- Buyer titles: {', '.join(icp.buyer_titles)}
- Top sources: {', '.join(icp.preferred_sources)}

## Conversation Signal Themes (from Fireflies transcripts & HubSpot notes)
{chr(10).join(
    f"- **{theme}**: mentioned in {data['deal_count']} deals, {round(data['won']/data['deal_count']*100,1) if data['deal_count'] else 0}% win rate when raised"
    + chr(10) + chr(10).join(f'  > "{q[0]}" ({q[1]} sentiment, via {q[2]})' for q in data['quotes'][:3])
    for theme, data in sorted(theme_data.items(), key=lambda x: x[1]['deal_count'], reverse=True)
)}

## Sample Recent Won Deals
{chr(10).join(f"- {d.name}: ${d.amount:,.0f}, {d.product_line}, source: {d.deal_source}, cycle: {d.cycle_days}d, competitor: {d.competitor or 'none'}, win reason: {d.win_reason}" for d in won_deals)}

## Sample Recent Lost Deals
{chr(10).join(f"- {d.name}: ${d.amount:,.0f}, {d.product_line}, source: {d.deal_source}, cycle: {d.cycle_days}d, competitor: {d.competitor or 'none'}, loss reason: {d.loss_reason}, objections: {', '.join(d.objections) or 'none'}" for d in lost_deals)}
"""


def _get_product_data_context(product_line: Optional[str] = None) -> str:
    """Build a product-focused data summary filtered by product_line."""
    deals = get_deals()
    pl_val = _pl_to_deal_value(product_line)
    if pl_val:
        deals = [d for d in deals if d.product_line == pl_val]

    pl_label = {"TA": "Talent Acquisition (TA)", "SI": "Skills Intelligence (SI)",
                "full_platform": "Full Platform", "all": "All Products"}.get(product_line or "all", product_line or "all")

    won = [d for d in deals if d.stage == "closedwon"]
    lost = [d for d in deals if d.stage == "closedlost"]

    # Loss reasons frequency with revenue
    lr_data = defaultdict(lambda: {"count": 0, "revenue": 0.0})  # type: Dict[str, dict]
    for d in lost:
        if d.loss_reason:
            lr_data[d.loss_reason]["count"] += 1
            lr_data[d.loss_reason]["revenue"] += d.amount
    lr_sorted = sorted(lr_data.items(), key=lambda x: x[1]["revenue"], reverse=True)

    # Objection frequency in lost deals
    obj_counts: Dict[str, int] = defaultdict(int)
    for d in lost:
        for obj in d.objections:
            obj_counts[obj] += 1
    obj_sorted = sorted(obj_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Competitor win rates
    comp_stats: Dict[str, dict] = defaultdict(lambda: {"won": 0, "total": 0, "revenue_lost": 0.0})
    for d in deals:
        if d.competitor:
            comp_stats[d.competitor]["total"] += 1
            if d.stage == "closedwon":
                comp_stats[d.competitor]["won"] += 1
            else:
                comp_stats[d.competitor]["revenue_lost"] += d.amount
    comp_sorted = sorted(comp_stats.items(),
                         key=lambda x: x[1]["won"] / x[1]["total"] if x[1]["total"] else 0)

    # Seniority win rates
    contacts = {c.id: c for c in get_contacts()}
    sen_stats: Dict[str, dict] = defaultdict(lambda: {"won": 0, "total": 0})
    for d in deals:
        contact = contacts.get(d.contact_id)
        if contact:
            sen = contact.seniority
            sen_stats[sen]["total"] += 1
            if d.stage == "closedwon":
                sen_stats[sen]["won"] += 1

    return f"""
## Product Line: {pl_label}
- Total deals: {len(deals)} | Won: {len(won)} | Lost: {len(lost)}
- Overall win rate: {round(len(won)/len(deals)*100,1) if deals else 0}%
- Total revenue (won): ${sum(d.amount for d in won):,.0f}
- Revenue at risk (lost): ${sum(d.amount for d in lost):,.0f}

## Top Loss Reasons (by revenue at risk)
{chr(10).join(f"- {lr}: {data['count']} deals, ${data['revenue']:,.0f} at risk" for lr, data in lr_sorted[:6])}

## Top Objections in Lost Deals
{chr(10).join(f"- {obj}: raised {cnt} times" for obj, cnt in obj_sorted)}

## Competitor Performance
{chr(10).join(f"- {comp}: {round(data['won']/data['total']*100,1) if data['total'] else 0}% win rate ({data['won']}/{data['total']} deals), ${data['revenue_lost']:,.0f} revenue lost to them" for comp, data in comp_sorted)}

## Buyer Seniority Win Rates
{chr(10).join(f"- {sen}: {round(data['won']/data['total']*100,1) if data['total'] else 0}% win rate ({data['total']} deals)" for sen, data in sorted(sen_stats.items(), key=lambda x: x[1]['won']/x[1]['total'] if x[1]['total'] else 0, reverse=True))}
"""


PROMPT_TEMPLATES = {
    "win_loss_summary": """Based on the following CRM deal data, provide an executive summary of win/loss patterns.

{data}

Provide:
1. **Key Headline** — one sentence capturing the biggest insight
2. **Top 3 Win Patterns** — what correlates most with winning
3. **Top 3 Loss Patterns** — what correlates most with losing
4. **Revenue Impact** — quantify what improving the weakest area could mean
5. **Immediate Actions** — 3 specific things the sales team should do this quarter
""",

    "icp_generation": """Based on the following CRM deal data, generate a detailed Ideal Customer Profile.

{data}

Provide:
1. **Ideal Customer Profile** — specific firmographic criteria with confidence levels
2. **Why These Criteria** — data backing for each criterion
3. **Disqualification Criteria** — red flags that indicate low win probability
4. **Scoring Model** — how to score new leads (High/Medium/Low fit)
5. **Positioning by Segment** — how to tailor messaging for the ideal profile
""",

    "competitor_briefing": """Based on the following CRM deal data, create a competitive intelligence briefing.

{data}

For each competitor, provide:
1. **Threat Level** — High/Medium/Low with reasoning
2. **Where They Win** — industries, deal sizes, scenarios where we lose to them
3. **Where We Win** — our advantages against this competitor
4. **Battle Card Points** — 3-4 key talking points for sales reps
5. **Recommended Strategy** — how to approach deals where this competitor is present
""",

    "positioning": """Based on the following CRM deal data, recommend positioning improvements.

{data}

Provide:
1. **Current Positioning Assessment** — what our win patterns say about our perceived value
2. **Messaging Recommendations** — specific messaging changes by segment
3. **Proof Points to Develop** — case studies and data points we should collect
4. **Pricing Strategy** — observations about our pricing sweet spot and recommendations
5. **Channel Strategy** — which channels to invest in based on win rates
""",

    "industry_loss": """Based on the following CRM deal data, analyze why we lose in {industry}.

{data}

Provide:
1. **Root Cause Analysis** — the top 3 reasons we lose in this industry
2. **Comparison** — how this industry differs from our best-performing industries
3. **Competitor Factor** — which competitors are strongest in this industry
4. **Turnaround Strategy** — specific steps to improve win rates in this industry
5. **Go/No-Go Criteria** — when to pursue vs. walk away from deals in this industry
""",

    "sales_scripts": """Based on the following CRM deal data, create objection handling guidance.

{data}

For the top objections, provide:
1. **Objection Response Scripts** — specific language to address each objection
2. **Discovery Questions** — questions to ask early to surface and prevent objections
3. **Qualification Framework** — questions to determine if a deal is worth pursuing
4. **Email Templates** — follow-up email language for common objection scenarios
5. **Escalation Triggers** — when to bring in leadership or technical resources
""",

    "ask_ai": """You are a sales intelligence assistant for iMocha, an HR-tech company selling Talent Acquisition (TA) assessments, Skills Intelligence, and a Full Platform bundle.

Answer the following question using the provided CRM deal data, which includes HubSpot deals, Fireflies transcript signals, and computed analytics.

Rules:
- Cite specific numbers (win rates, deal counts, revenue figures)
- Reference conversation signal quotes when relevant to add qualitative evidence
- Compare across dimensions (e.g., compare industry performance, competitor impact)
- End with 2-3 actionable recommendations

{data}

Question: {question}
""",
}


async def generate_insight(prompt_type: str, industry: Optional[str] = None,
                           question: Optional[str] = None, **kwargs) -> str:
    """Generate AI insight using Claude API with caching."""
    product_line = kwargs.get("product_line", None)

    # Don't cache ask_ai questions to keep responses fresh
    cache_key = f"{prompt_type}:{industry or ''}:{question or ''}:{product_line or ''}"
    if prompt_type != "ask_ai" and cache_key in _cache:
        return _cache[cache_key]

    if not ANTHROPIC_API_KEY:
        # Return a mock response for demo without API key
        if prompt_type == "product_brief":
            return _generate_product_brief_mock(product_line)
        return _generate_mock_response(prompt_type, industry, question)

    # Handle product_brief separately (uses custom prompt building)
    if prompt_type == "product_brief":
        pl_label = {
            "TA": "Talent Acquisition (TA)",
            "SI": "Skills Intelligence (SI)",
            "full_platform": "Full Platform",
            "all": "All Products",
        }.get(product_line or "all", product_line or "all")
        data = _get_product_data_context(product_line)
        prompt = f"""
You are a product strategy consultant writing a brief for iMocha's {pl_label} product team.

Analyze the following win/loss data and produce a concise Product Intelligence Brief.

{data}

Your brief must include exactly these three sections using markdown:

**Top 3 roadmap investments by revenue impact:**
For each: investment name → estimated revenue impact → context (deals count, competitor)

**Emerging pattern:**
One specific trend or shift that product leadership should act on now. Be concrete — name competitors, themes, buyer concerns.

**Opportunity:**
One specific competitive or market opening visible in this data. Where is a competitor weak? Which segment is underserved?

Be specific, use actual numbers from the data. Maximum 150 words total.
"""
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            result = message.content[0].text
            _cache[cache_key] = result
            return result
        except Exception as e:
            return _generate_product_brief_mock(product_line)

    template = PROMPT_TEMPLATES.get(prompt_type)
    if not template:
        return "Unknown prompt type."

    data_context = _get_data_context()
    prompt = template.format(data=data_context, industry=industry or "", question=question or "")

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        result = message.content[0].text
        if prompt_type != "ask_ai":
            _cache[cache_key] = result
        return result
    except Exception as e:
        return f"AI analysis unavailable: {str(e)}"


def _generate_product_brief_mock(product_line: Optional[str] = None) -> str:
    """Fallback mock response for product brief when no API key is available."""
    pl_label = {
        "TA": "Talent Acquisition (TA)",
        "SI": "Skills Intelligence (SI)",
        "full_platform": "Full Platform",
        "all": "All Products",
    }.get(product_line or "all", product_line or "all")
    return f"""**Top 3 roadmap investments by revenue impact ({pl_label}):**
1. Assessment platform depth → high revenue impact → affects multiple lost deals, recurring competitor pressure
2. Integration completeness → significant pipeline blocked → ATS/HCM gaps cited frequently
3. Reporting & analytics → moderate impact → buyer personas requesting board-level outputs

**Emerging pattern:**
Buyers are increasingly comparing iMocha's product capabilities against best-in-class point solutions. Competitors win on depth in specific categories. Product team should invest in closing the top 1-2 gaps before Q2.

**Opportunity:**
Mid-market BFSI segment shows lower competitive penetration from top rivals. Focused vertical positioning in BFSI could improve win rates by 10-15pp with targeted case studies and compliance-focused messaging."""


# ---------------------------------------------------------------------------
# Smart mock response system
# ---------------------------------------------------------------------------

def _detect_topics(q: str) -> List[str]:
    """Detect question topics via keyword matching."""
    topics = []
    # Deals / list deals — check first so "latest deals" doesn't fall through
    if any(w in q for w in ["list deal", "latest deal", "recent deal", "show deal",
                             "biggest deal", "largest deal", "top deal", "show me deal",
                             "list the deal", "all deal", "specific deal",
                             "list deals", "latest deals", "recent deals", "show deals",
                             "biggest deals", "largest deals", "top deals", "show me deals",
                             "list the deals", "all deals", "won deals", "lost deals"]):
        topics.append("deals")
    if any(w in q for w in ["competitor", "hackerrank", "eightfold", "codility", "hirevue",
                             "testgorilla", "mercer", "gloat", "lightcast", "skyhive",
                             "compete", "against", "versus", "vs "]):
        topics.append("competitor")
    if any(w in q for w in ["industry", "industries", "vertical", "verticals", "it services",
                             "bfsi", "healthcare", "manufacturing", "retail", "saas", "sector",
                             "pursuing", "stop pursuing"]):
        topics.append("industry")
    if any(w in q for w in ["deal size", "amount", "pricing", "price", "sweet spot",
                             "enterprise deal", "large deal", "small deal", "expensive",
                             "cheap", "cost", "budget"]):
        topics.append("deal_size")
    if any(w in q for w in ["source", "channel", "referral", "inbound", "outbound",
                             "partner", "g2", "conference", "lead source"]):
        topics.append("source")
    if any(w in q for w in ["cycle", "speed", "velocity", "slow", "fast", "days",
                             "timeline", "how long", "time to close", "duration"]):
        topics.append("cycle")
    if any(w in q for w in ["objection", "concern", "pushback", "resistance", "handle",
                             "overcome", "barrier", "blocker"]):
        topics.append("objection")
    if any(w in q for w in ["icp", "ideal customer", "profile", "target customer",
                             "best fit", "qualification", "ideal prospect"]):
        topics.append("icp")
    if any(w in q for w in [" rep ", "sales rep", "salesperson", "reps ", "team performance",
                             "performer", "rep performance", "sales team", "who is"]):
        topics.append("sales_rep")
    if any(w in q for w in ["geography", "city", "region", "location", "bangalore", "mumbai",
                             "hyderabad", "pune", "delhi", "chennai", "gurugram"]):
        topics.append("geography")
    if any(w in q for w in ["conversation", "transcript", "signal", "quote", "fireflies",
                             "call recording", "said", "saying", "customer feedback",
                             "buyer feedback", "what buyer", "what customer"]):
        topics.append("conversation")
    if any(w in q for w in ["product line", " ta ", "skills intelligence", "full platform",
                             "product mix", "product performance"]):
        topics.append("product_line")
    if any(w in q for w in ["loss", "lose", "losing", "lost", "why we lose", "weakness",
                             "failing", "struggle", "problem", "issue"]) and "competitor" not in topics:
        topics.append("loss")
    if any(w in q for w in ["win", "winning", "won", "strength", "best", "top performing",
                             "success", "strong"]) and "competitor" not in topics:
        topics.append("win")
    # Revenue / summary / overview / pipeline
    if any(w in q for w in ["revenue", "pipeline", "overview", "summary", "performance",
                             "how are we doing", "tell me about", "dashboard"]):
        if not topics:
            topics.append("general")

    if not topics:
        topics = ["general"]
    return topics


def _mock_competitor_answer(q: str) -> str:
    competitors = compute_competitors()
    deals = get_deals()

    # Check for specific competitor name
    target = None
    for c in competitors:
        if c.competitor.lower() in q:
            target = c
            break

    if target:
        # Specific competitor analysis
        comp_deals = [d for d in deals if d.competitor == target.competitor and d.stage == "closedlost"]
        quotes = []
        for d in comp_deals[:5]:
            for sig in d.conversation_signals:
                if sig.sentiment == "negative":
                    quotes.append(f'> "{sig.quote}" — *{d.name}, via {sig.source}*')
        quote_section = "\n".join(quotes[:3]) if quotes else "> No specific conversation signals found."

        return f"""## Competitive Analysis: {target.competitor}

**Our Win Rate**: {target.win_rate}% ({target.wins}W / {target.losses}L from {target.deals_faced} deals)

**Threat Level**: {"HIGH" if target.win_rate < 35 else "MEDIUM" if target.win_rate < 50 else "LOW"}

**Top Loss Reasons Against {target.competitor}**:
{chr(10).join(f"- {r}" for r in target.top_loss_reasons) if target.top_loss_reasons else "- No specific loss reasons recorded"}

**Industries Where We Compete**: {', '.join(target.industries)}

**Avg Deal Size in These Deals**: ${target.avg_deal_size:,.0f}

### What Buyers Are Saying (from call transcripts)
{quote_section}

### Recommendations
1. Build a **{target.competitor} battle card** focusing on differentiation in {target.industries[0] if target.industries else 'key verticals'}
2. {"Develop pricing counter-strategies — we're losing on cost" if "Pricing" in str(target.top_loss_reasons) else "Develop proof points and case studies to counter their positioning"}
3. Flag deals with {target.competitor} early for executive engagement and competitive win plays"""
    else:
        # General competitor landscape
        ranked = sorted(competitors, key=lambda c: c.win_rate)
        return f"""## Competitive Landscape

| Competitor | Our Win Rate | Deals | Wins | Losses | Top Loss Reason |
|---|---|---|---|---|---|
{chr(10).join(f"| {c.competitor} | {c.win_rate}% | {c.deals_faced} | {c.wins} | {c.losses} | {c.top_loss_reasons[0] if c.top_loss_reasons else 'N/A'} |" for c in ranked)}

**Hardest Competitor**: {ranked[0].competitor} ({ranked[0].win_rate}% win rate)
**Easiest Competitor**: {ranked[-1].competitor} ({ranked[-1].win_rate}% win rate)

### Recommendations
1. Prioritize building battle cards for **{ranked[0].competitor}** and **{ranked[1].competitor if len(ranked) > 1 else ranked[0].competitor}** (lowest win rates)
2. Study what makes us successful against **{ranked[-1].competitor}** and replicate those strategies
3. Train reps on competitive positioning — ask about competitors in the first discovery call"""


def _mock_industry_answer(q: str) -> str:
    breakdown = compute_breakdown("industry")
    ranked = sorted(breakdown, key=lambda b: b.win_rate, reverse=True)

    return f"""## Industry Performance Analysis

| Industry | Win Rate | Won | Lost | Total | Revenue |
|---|---|---|---|---|---|
{chr(10).join(f"| {b.category} | **{b.win_rate}%** | {b.won} | {b.lost} | {b.total} | ${b.total_revenue:,.0f} |" for b in ranked)}

**Best Vertical**: {ranked[0].category} at {ranked[0].win_rate}% ({ranked[0].won} wins from {ranked[0].total} deals, ${ranked[0].total_revenue:,.0f} revenue)

**Worst Vertical**: {ranked[-1].category} at {ranked[-1].win_rate}% ({ranked[-1].won} wins from {ranked[-1].total} deals)

**Gap**: {ranked[0].win_rate - ranked[-1].win_rate:.0f} percentage points between best and worst verticals.

### Recommendations
1. **Double down on {ranked[0].category}** — build industry-specific case studies and dedicate reps to this vertical
2. **Develop {ranked[-1].category} playbook** or deprioritize — current win rate is too low to sustain investment
3. **Mid-tier opportunity**: {ranked[len(ranked)//2].category} ({ranked[len(ranked)//2].win_rate}%) has room for improvement with targeted messaging"""


def _mock_deal_size_answer(q: str) -> str:
    breakdown = compute_breakdown("deal_size")
    ranked = sorted(breakdown, key=lambda b: b.win_rate, reverse=True)

    return f"""## Deal Size Analysis

| Size Bracket | Win Rate | Won | Lost | Total | Avg Deal Size |
|---|---|---|---|---|---|
{chr(10).join(f"| {b.category} | **{b.win_rate}%** | {b.won} | {b.lost} | {b.total} | ${b.avg_deal_size:,.0f} |" for b in ranked)}

**Sweet Spot**: {ranked[0].category} at {ranked[0].win_rate}% win rate

**Drop-off**: {ranked[-1].category} at only {ranked[-1].win_rate}% — {"large deals require longer cycles and more stakeholders" if "Over" in ranked[-1].category or "150" in ranked[-1].category else "smaller deals may not justify the sales effort"}

### Recommendations
1. **Optimize pipeline** around the {ranked[0].category} range — this is where product-market fit is strongest
2. For deals outside the sweet spot, apply **higher qualification bars** and involve solution architects earlier
3. Consider **tiered pricing** to capture more deals in the profitable range"""


def _mock_source_answer(q: str) -> str:
    breakdown = compute_breakdown("source")
    ranked = sorted(breakdown, key=lambda b: b.win_rate, reverse=True)

    return f"""## Lead Source Performance

| Source | Win Rate | Won | Lost | Total | Revenue |
|---|---|---|---|---|---|
{chr(10).join(f"| {b.category} | **{b.win_rate}%** | {b.won} | {b.lost} | {b.total} | ${b.total_revenue:,.0f} |" for b in ranked)}

**Best Channel**: {ranked[0].category} at {ranked[0].win_rate}% win rate (${ranked[0].total_revenue:,.0f} revenue)

**Worst Channel**: {ranked[-1].category} at {ranked[-1].win_rate}% win rate

### Recommendations
1. **Invest more in {ranked[0].category}** — highest win rate, proven ROI
2. **Re-evaluate {ranked[-1].category}** — {ranked[-1].win_rate}% win rate suggests targeting or messaging problems
3. Look for **underrepresented high-performers**: channels with great win rates but low deal volume represent untapped growth"""


def _mock_cycle_answer(q: str) -> str:
    overview = compute_overview()
    drag = overview.avg_cycle_lost - overview.avg_cycle_won
    deals = get_deals()

    slow_lost = [d for d in deals if d.stage == "closedlost" and d.cycle_days > overview.avg_cycle_lost]
    quotes = []
    for d in slow_lost[:5]:
        for sig in d.conversation_signals:
            if sig.theme in ("Champion Risk", "Competitive Pressure") and sig.sentiment == "negative":
                quotes.append(f'> "{sig.quote}" — *{d.name} ({d.cycle_days}d cycle), via {sig.source}*')
    quote_section = "\n".join(quotes[:3]) if quotes else "> No specific signals from slow deals."

    return f"""## Sales Cycle Analysis

- **Avg Won Cycle**: {overview.avg_cycle_won} days
- **Avg Lost Cycle**: {overview.avg_cycle_lost} days
- **Cycle Drag**: Lost deals take **{drag:.0f} extra days** on average

**Slow deals ({int(overview.avg_cycle_lost)}+ days) that were lost**: {len(slow_lost)} deals

### Warning Signals from Slow Lost Deals
{quote_section}

### Recommendations
1. **Set velocity alerts** at {overview.avg_cycle_won:.0f} days — deals not progressing past this mark need immediate intervention
2. At {overview.avg_cycle_lost:.0f} days, **escalate champion validation** — verify the internal champion is still engaged
3. **Kill deals faster** — every day spent on a doomed deal is capacity taken from winnable ones"""


def _mock_objection_answer(q: str) -> str:
    objections = compute_objections()

    return f"""## Objection Analysis

| Objection | Times Raised | Win Rate When Raised | Industries |
|---|---|---|---|
{chr(10).join(f"| {o.objection} | {o.frequency} | **{o.win_rate_when_raised}%** | {', '.join(o.industries[:3])} |" for o in objections)}

**Most Frequent**: "{objections[0].objection}" (raised {objections[0].frequency} times)

**Most Damaging**: "{min(objections, key=lambda o: o.win_rate_when_raised).objection}" — win rate drops to {min(objections, key=lambda o: o.win_rate_when_raised).win_rate_when_raised}% when raised

### Recommendations
1. **Develop preemptive handling** for "{objections[0].objection}" — address it proactively before buyers raise it
2. For "{min(objections, key=lambda o: o.win_rate_when_raised).objection}", create **case studies and ROI calculators** as proof points
3. Train reps to **surface objections early** in discovery — it's better to address them upfront than have them derail a late-stage deal"""


def _mock_icp_answer(q: str) -> str:
    icp = compute_icp()
    deals = get_deals()
    companies = {c.id: c for c in get_companies()}

    # ICP fit calculation
    industry_stats = defaultdict(lambda: {"won": 0, "total": 0})  # type: Dict[str, dict]
    for d in deals:
        comp = companies.get(d.company_id)
        if comp:
            industry_stats[comp.industry]["total"] += 1
            if d.stage == "closedwon":
                industry_stats[comp.industry]["won"] += 1

    icp_industries = set(ind for ind, s in industry_stats.items()
                         if s["total"] >= 5 and s["won"] / s["total"] > 0.45)

    icp_deals = []
    non_icp_deals = []
    for d in deals:
        comp = companies.get(d.company_id)
        if comp and comp.industry in icp_industries and 2000 <= comp.employee_count <= 10000 and 30000 <= d.amount <= 80000:
            icp_deals.append(d)
        else:
            non_icp_deals.append(d)

    icp_won = len([d for d in icp_deals if d.stage == "closedwon"])
    non_icp_won = len([d for d in non_icp_deals if d.stage == "closedwon"])
    icp_wr = round(icp_won / len(icp_deals) * 100, 1) if icp_deals else 0
    non_icp_wr = round(non_icp_won / len(non_icp_deals) * 100, 1) if non_icp_deals else 0

    return f"""## Ideal Customer Profile

### ICP Criteria
| Attribute | Ideal Profile |
|---|---|
| Industries | {', '.join(icp.industries)} |
| Company Size | {icp.employee_range} |
| Deal Size | {icp.deal_size_range} |
| Buyer Personas | {', '.join(icp.buyer_titles)} |
| Best Channels | {', '.join(icp.preferred_sources)} |
| Avg Cycle | {icp.avg_cycle_days} days |
| Confidence | {(icp.confidence * 100):.0f}% |

### ICP Fit Impact
- **ICP-fit deals**: {icp_wr}% win rate ({len(icp_deals)} deals)
- **Non-ICP deals**: {non_icp_wr}% win rate ({len(non_icp_deals)} deals)
- **Gap**: {icp_wr - non_icp_wr:.0f} percentage points

### Recommendations
1. **Tighten qualification** — {round(len(icp_deals)/len(deals)*100)}% of pipeline currently matches ICP, there's room to increase this
2. For non-ICP deals, set **higher qualification bars** or develop a lighter-touch sales motion
3. Use ICP criteria to **score inbound leads** and prioritize rep time accordingly"""


def _mock_sales_rep_answer(q: str) -> str:
    deals = get_deals()
    rep_stats = defaultdict(lambda: {"won": 0, "total": 0, "revenue": 0.0, "cycle_sum": 0})  # type: Dict[str, dict]
    for d in deals:
        if d.sales_rep:
            rep_stats[d.sales_rep]["total"] += 1
            if d.stage == "closedwon":
                rep_stats[d.sales_rep]["won"] += 1
                rep_stats[d.sales_rep]["revenue"] += d.amount
                rep_stats[d.sales_rep]["cycle_sum"] += d.cycle_days

    ranked = sorted(rep_stats.items(), key=lambda x: x[1]["won"] / x[1]["total"] if x[1]["total"] else 0, reverse=True)

    rows = []
    for rep, s in ranked:
        wr = round(s["won"] / s["total"] * 100, 1) if s["total"] else 0
        avg_cycle = round(s["cycle_sum"] / s["won"]) if s["won"] else 0
        avg_deal = round(s["revenue"] / s["won"]) if s["won"] else 0
        rows.append(f"| {rep} | **{wr}%** | {s['won']} | {s['total'] - s['won']} | {s['total']} | ${s['revenue']:,.0f} | ${avg_deal:,.0f} | {avg_cycle}d |")

    top = ranked[0]
    bottom = ranked[-1]

    return f"""## Sales Rep Performance

| Rep | Win Rate | Won | Lost | Total | Revenue | Avg Deal | Avg Cycle |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

**Top Performer**: {top[0]} — {round(top[1]['won']/top[1]['total']*100,1)}% win rate, ${top[1]['revenue']:,.0f} revenue

**Needs Coaching**: {bottom[0]} — {round(bottom[1]['won']/bottom[1]['total']*100,1)}% win rate

### Recommendations
1. **Shadow program**: Have lower performers shadow {top[0]}'s deal approach and discovery process
2. Analyze what's different — {top[0]}'s deal mix, sources, and buyer seniority vs others
3. Set **minimum activity standards** based on top performer benchmarks"""


def _mock_geography_answer(q: str) -> str:
    breakdown = compute_breakdown("geography")
    ranked = sorted(breakdown, key=lambda b: b.win_rate, reverse=True)

    return f"""## Geography Performance

| City | Win Rate | Won | Lost | Total | Revenue |
|---|---|---|---|---|---|
{chr(10).join(f"| {b.category} | **{b.win_rate}%** | {b.won} | {b.lost} | {b.total} | ${b.total_revenue:,.0f} |" for b in ranked)}

**Best Region**: {ranked[0].category} at {ranked[0].win_rate}% ({ranked[0].total} deals)

**Weakest Region**: {ranked[-1].category} at {ranked[-1].win_rate}% ({ranked[-1].total} deals)

### Recommendations
1. **Expand in {ranked[0].category}** — highest win rate, build on existing momentum
2. Investigate why {ranked[-1].category} underperforms — may be industry mix, rep allocation, or competitive landscape
3. Consider **regional specialization** — assign reps to geographies where they have the strongest networks"""


def _mock_conversation_answer(q: str) -> str:
    deals = get_deals()
    theme_data = defaultdict(lambda: {"quotes": [], "deal_count": 0, "won": 0, "total": 0})  # type: Dict[str, dict]
    for d in deals:
        for sig in d.conversation_signals:
            theme_data[sig.theme]["deal_count"] += 1
            theme_data[sig.theme]["total"] += 1
            if d.stage == "closedwon":
                theme_data[sig.theme]["won"] += 1
            theme_data[sig.theme]["quotes"].append({
                "quote": sig.quote, "sentiment": sig.sentiment,
                "source": sig.source, "deal": d.name, "stage": d.stage
            })

    sections = []
    for theme, data in sorted(theme_data.items(), key=lambda x: x[1]["deal_count"], reverse=True):
        wr = round(data["won"] / data["deal_count"] * 100, 1) if data["deal_count"] else 0
        neg_quotes = [qq for qq in data["quotes"] if qq["sentiment"] == "negative"][:2]
        pos_quotes = [qq for qq in data["quotes"] if qq["sentiment"] == "positive"][:1]
        sample_quotes = neg_quotes + pos_quotes

        quote_lines = []
        for qq in sample_quotes:
            status = "Won" if qq["stage"] == "closedwon" else "Lost"
            quote_lines.append(f'> "{qq["quote"]}" — *{qq["deal"]} ({status}), via {qq["source"]}*')

        sections.append(f"""### {theme}
- Mentioned in **{data['deal_count']} deals**, win rate: **{wr}%**
{chr(10).join(quote_lines)}""")

    return f"""## Conversation Signal Intelligence (from Fireflies & HubSpot)

{chr(10).join(sections)}

### Recommendations
1. **Feed product gap signals to the product team** monthly for roadmap prioritization
2. Use **pricing signals** to refine discount guidelines and packaging
3. **Champion Risk** signals should trigger immediate executive engagement"""


def _mock_product_line_answer(q: str) -> str:
    deals = get_deals()
    pl_stats = defaultdict(lambda: {"won": 0, "total": 0, "revenue": 0.0})  # type: Dict[str, dict]
    for d in deals:
        pl_stats[d.product_line]["total"] += 1
        if d.stage == "closedwon":
            pl_stats[d.product_line]["won"] += 1
            pl_stats[d.product_line]["revenue"] += d.amount

    ranked = sorted(pl_stats.items(), key=lambda x: x[1]["won"] / x[1]["total"] if x[1]["total"] else 0, reverse=True)

    rows = []
    for pl, s in ranked:
        wr = round(s["won"] / s["total"] * 100, 1) if s["total"] else 0
        rows.append(f"| {pl} | **{wr}%** | {s['won']} | {s['total'] - s['won']} | {s['total']} | ${s['revenue']:,.0f} |")

    best = ranked[0]
    worst = ranked[-1]

    return f"""## Product Line Performance

| Product Line | Win Rate | Won | Lost | Total | Revenue |
|---|---|---|---|---|---|
{chr(10).join(rows)}

**Best Performer**: {best[0]} at {round(best[1]['won']/best[1]['total']*100,1)}% win rate (${best[1]['revenue']:,.0f} revenue)

**Weakest**: {worst[0]} at {round(worst[1]['won']/worst[1]['total']*100,1)}% win rate

### Recommendations
1. **Lead with {best[0]}** in new opportunities — it has the strongest product-market fit
2. For {worst[0]}, investigate if the issue is **positioning, competition, or buyer education**
3. Consider **bundling** lower-performing products with {best[0]} to increase attach rates"""


def _mock_loss_answer(q: str) -> str:
    deals = get_deals()
    lost = [d for d in deals if d.stage == "closedlost"]

    reason_counts = defaultdict(int)  # type: Dict[str, int]
    for d in lost:
        if d.loss_reason:
            reason_counts[d.loss_reason] += 1
    ranked_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)

    # Quotes from lost deals
    quotes = []
    for d in lost[:10]:
        for sig in d.conversation_signals:
            if sig.sentiment == "negative":
                quotes.append(f'> "{sig.quote}" — *{d.name} (${d.amount:,.0f}, {d.loss_reason}), via {sig.source}*')
    quote_section = "\n".join(quotes[:5]) if quotes else "> No conversation signals from lost deals."

    return f"""## Loss Analysis

**Total Lost Deals**: {len(lost)}
**Total Revenue Lost**: ${sum(d.amount for d in lost):,.0f}

### Top Loss Reasons
| Reason | Count | % of Losses |
|---|---|---|
{chr(10).join(f"| {r} | {c} | {round(c/len(lost)*100,1)}% |" for r, c in ranked_reasons[:6])}

### What Buyers Said Before We Lost
{quote_section}

### Recommendations
1. Address **"{ranked_reasons[0][0]}"** head-on — it's the #1 loss reason ({ranked_reasons[0][1]} deals)
2. Build proof points and ROI cases to counter **"{ranked_reasons[1][0] if len(ranked_reasons) > 1 else ranked_reasons[0][0]}"**
3. Conduct **win/loss interviews** with recent lost deals for deeper qualitative understanding"""


def _mock_win_answer(q: str) -> str:
    deals = get_deals()
    won = [d for d in deals if d.stage == "closedwon"]

    reason_counts = defaultdict(int)  # type: Dict[str, int]
    for d in won:
        if d.win_reason:
            reason_counts[d.win_reason] += 1
    ranked_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)

    # Source breakdown of wins
    source_counts = defaultdict(int)  # type: Dict[str, int]
    for d in won:
        source_counts[d.deal_source] += 1
    ranked_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)

    return f"""## Win Analysis

**Total Won Deals**: {len(won)}
**Total Revenue Won**: ${sum(d.amount for d in won):,.0f}
**Avg Deal Size**: ${sum(d.amount for d in won) / len(won):,.0f}
**Avg Win Cycle**: {round(sum(d.cycle_days for d in won) / len(won))} days

### Top Win Reasons
| Reason | Count | % of Wins |
|---|---|---|
{chr(10).join(f"| {r} | {c} | {round(c/len(won)*100,1)}% |" for r, c in ranked_reasons[:6])}

### Winning Sources
{chr(10).join(f"- **{s}**: {c} wins ({round(c/len(won)*100,1)}% of all wins)" for s, c in ranked_sources)}

### Recommendations
1. **Amplify "{ranked_reasons[0][0]}"** — it's the top win driver, build messaging around it
2. **Invest in {ranked_sources[0][0]}** — it delivers the most wins
3. Codify winning behaviors into **sales playbooks** and share across the team"""


def _mock_deals_answer(q: str) -> str:
    deals = get_deals()
    companies = {c.id: c for c in get_companies()}

    # Determine what the user wants
    want_won = any(w in q for w in ["won deal", "winning deal", "closed won", "best deal"])
    want_lost = any(w in q for w in ["lost deal", "losing deal", "closed lost", "worst deal"])
    want_biggest = any(w in q for w in ["biggest", "largest", "top deal", "highest value", "most expensive"])
    want_recent = any(w in q for w in ["latest", "recent", "newest", "last"])

    # Filter stage
    if want_won:
        filtered = [d for d in deals if d.stage == "closedwon"]
        label = "Won"
    elif want_lost:
        filtered = [d for d in deals if d.stage == "closedlost"]
        label = "Lost"
    else:
        filtered = list(deals)
        label = "All"

    # Sort
    if want_biggest:
        filtered = sorted(filtered, key=lambda d: d.amount, reverse=True)
        sort_label = "by deal size (largest first)"
    elif want_recent:
        filtered = sorted(filtered, key=lambda d: d.close_date, reverse=True)
        sort_label = "by close date (most recent first)"
    else:
        filtered = sorted(filtered, key=lambda d: d.close_date, reverse=True)
        sort_label = "by close date (most recent first)"

    # Try to extract a number from the question (e.g. "list 3 deals")
    import re
    num_match = re.search(r'\b(\d+)\b', q)
    limit = int(num_match.group(1)) if num_match else 10
    limit = min(limit, 25)  # cap at 25

    shown = filtered[:limit]

    rows = []
    for d in shown:
        comp = companies.get(d.company_id)
        comp_name = comp.name if comp else "—"
        status = "Won" if d.stage == "closedwon" else "Lost"
        reason = d.win_reason if d.stage == "closedwon" else (d.loss_reason or "—")
        rows.append(
            f"| {d.name} | {comp_name} | ${d.amount:,.0f} | {status} | {d.deal_source} | "
            f"{d.competitor or '—'} | {d.cycle_days}d | {reason} |"
        )

    return f"""## {label} Deals — {sort_label}

Showing **{len(shown)}** of {len(filtered)} {label.lower()} deals.

| Deal | Company | Amount | Status | Source | Competitor | Cycle | Reason |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

### Quick Stats
- **Total deals shown**: {len(shown)}
- **Won**: {len([d for d in shown if d.stage == 'closedwon'])} | **Lost**: {len([d for d in shown if d.stage == 'closedlost'])}
- **Total value**: ${sum(d.amount for d in shown):,.0f}
- **Avg deal size**: ${sum(d.amount for d in shown) / len(shown):,.0f}"""


def _mock_general_answer(q: str) -> str:
    overview = compute_overview()
    industry_bd = compute_breakdown("industry")
    source_bd = compute_breakdown("source")
    competitors = compute_competitors()

    top_industry = max(industry_bd, key=lambda x: x.win_rate)
    worst_industry = min(industry_bd, key=lambda x: x.win_rate)
    top_source = max(source_bd, key=lambda x: x.win_rate)
    worst_competitor = min(competitors, key=lambda x: x.win_rate) if competitors else None

    return f"""## Pipeline Overview

**{overview.total_deals} total deals** | {overview.won_deals} Won | {overview.lost_deals} Lost | **{overview.win_rate}% win rate**
**Revenue**: ${overview.total_revenue:,.0f} | Avg deal: ${overview.avg_deal_size:,.0f}
**Cycle**: Won in {overview.avg_cycle_won}d avg | Lost in {overview.avg_cycle_lost}d avg

### Top 5 Insights

1. **Best Industry**: {top_industry.category} wins at {top_industry.win_rate}% ({top_industry.won}/{top_industry.total} deals, ${top_industry.total_revenue:,.0f} revenue)
2. **Worst Industry**: {worst_industry.category} at {worst_industry.win_rate}% — {top_industry.win_rate - worst_industry.win_rate:.0f}pp gap from the best
3. **Best Channel**: {top_source.category} at {top_source.win_rate}% win rate
4. **Hardest Competitor**: {worst_competitor.competitor if worst_competitor else 'N/A'} — only {worst_competitor.win_rate if worst_competitor else 0}% win rate against them
5. **Cycle Drag**: Lost deals take {overview.avg_cycle_lost - overview.avg_cycle_won:.0f} extra days — early disqualification frees capacity

### Recommendations
1. Focus pipeline on **{top_industry.category}** and **{top_source.category}** — the two strongest dimensions
2. Address competitive positioning against **{worst_competitor.competitor if worst_competitor else 'key competitors'}**
3. Tighten ICP criteria to filter out low-probability deals earlier"""


def _build_smart_mock_answer(question: str) -> str:
    """Generate a data-driven mock answer by detecting the question topic."""
    q = question.lower()
    topics = _detect_topics(q)

    handlers = {
        "deals": _mock_deals_answer,
        "competitor": _mock_competitor_answer,
        "industry": _mock_industry_answer,
        "deal_size": _mock_deal_size_answer,
        "source": _mock_source_answer,
        "cycle": _mock_cycle_answer,
        "objection": _mock_objection_answer,
        "icp": _mock_icp_answer,
        "sales_rep": _mock_sales_rep_answer,
        "geography": _mock_geography_answer,
        "conversation": _mock_conversation_answer,
        "product_line": _mock_product_line_answer,
        "loss": _mock_loss_answer,
        "win": _mock_win_answer,
        "general": _mock_general_answer,
    }

    sections = []
    for topic in topics[:2]:
        handler = handlers.get(topic, _mock_general_answer)
        sections.append(handler(q))

    return "\n\n---\n\n".join(sections)


def _mock_win_loss_summary() -> str:
    """Generate dynamic win/loss summary from actual data breakdowns."""
    overview = compute_overview()
    industry_bd = compute_breakdown("industry")
    size_bd = compute_breakdown("deal_size")
    source_bd = compute_breakdown("source")
    competitors = compute_competitors()

    # Get best and worst performers
    top_industry = max(industry_bd, key=lambda x: x.win_rate)
    worst_industry = min(industry_bd, key=lambda x: x.win_rate)
    best_size = max(size_bd, key=lambda x: x.win_rate)
    worst_size = min(size_bd, key=lambda x: x.win_rate)
    best_source = max(source_bd, key=lambda x: x.win_rate)
    worst_source = min(source_bd, key=lambda x: x.win_rate)
    worst_competitor = min(competitors, key=lambda x: x.win_rate) if competitors else None

    # Calculate multiplier for source comparison
    source_multiplier = round(best_source.win_rate / worst_source.win_rate, 1) if worst_source.win_rate > 0 else 1

    # Calculate revenue impact
    revenue_potential = worst_industry.total * (0.40 - worst_industry.win_rate / 100) * worst_industry.avg_deal_size if worst_industry.total > 0 else 0

    return f"""## Executive Win/Loss Summary

### Key Headline
**Our sweet spot is {top_industry.category} and {best_size.category} deals, but we're underperforming in {worst_industry.category} and {worst_size.category} deals.**

### Top 3 Win Patterns
1. **Industry Fit**: {top_industry.category} leads with a {top_industry.win_rate}% win rate ({top_industry.won} wins from {top_industry.total} deals), generating ${top_industry.total_revenue:,.0f} in revenue
2. **Deal Size Sweet Spot**: {best_size.category} deals close at {best_size.win_rate}%+ — our product-market fit is strongest here
3. **Source Channel**: {best_source.category}-sourced deals win at {best_source.win_rate}%, nearly {source_multiplier}x our {worst_source.category} rate at {worst_source.win_rate}%

### Top 3 Loss Patterns
1. **Large Deal Challenge**: {worst_size.category} deals win at only {worst_size.win_rate}% — we lack {worst_size.category}-level readiness
2. **{worst_industry.category} Industry**: Only {worst_industry.win_rate}% win rate across {worst_industry.total} deals — poor product-market fit
3. **{worst_source.category}-Sourced Deals**: {worst_source.win_rate}% win rate suggests targeting and/or messaging problems

### Revenue Impact
Improving {worst_industry.category} win rate from {worst_industry.win_rate}% to 40% could generate an estimated additional ${revenue_potential:,.0f} annually.

### Immediate Actions
1. **Deprioritize {worst_size.category} deals** until product has {worst_size.category}-level features; focus reps on {best_size.category} range
2. **Double down on {best_source.category}** — invest in customer advocacy and {best_source.category.lower()} program
3. **Retrain {worst_source.category} team** on new ICP targeting criteria focusing on {top_industry.category} companies"""


def _mock_icp_generation() -> str:
    """Generate dynamic ICP from actual winning deal patterns."""
    overview = compute_overview()
    industry_bd = compute_breakdown("industry")
    size_bd = compute_breakdown("deal_size")
    company_size_bd = compute_breakdown("company_size")
    buyer_bd = compute_breakdown("buyer_title")
    source_bd = compute_breakdown("source")
    competitors = compute_competitors()

    # Get top performers
    top_industries = sorted(industry_bd, key=lambda x: x.win_rate, reverse=True)[:2]
    best_size = max(size_bd, key=lambda x: x.win_rate)
    best_company_size = max(company_size_bd, key=lambda x: x.win_rate)
    best_buyer = max(buyer_bd, key=lambda x: x.win_rate)
    best_sources = sorted(source_bd, key=lambda x: x.win_rate, reverse=True)[:2]
    worst_competitor = min(competitors, key=lambda x: x.win_rate) if competitors else None

    # Build industry string
    top_industry_str = ", ".join(ind.category for ind in top_industries)

    # Build source string
    top_source_str = ", ".join(src.category for src in best_sources)

    # Calculate average confidence as weighted by win rate
    avg_confidence = round(overview.win_rate + 10)  # Boost for ICP focus

    return f"""## Ideal Customer Profile

### Primary ICP (High Confidence: {avg_confidence}%)

| Criterion | Ideal Profile | Confidence |
|-----------|--------------|------------|
| **Industry** | {top_industry_str} | High ({round(top_industries[0].win_rate + 5)}%) |
| **Company Size** | {best_company_size.category} | High ({round(best_company_size.win_rate + 5)}%) |
| **Deal Size** | {best_size.category} | High ({round(best_size.win_rate + 5)}%) |
| **Buyer Title** | {best_buyer.category} | Medium ({round(best_buyer.win_rate)}%) |
| **Lead Source** | {top_source_str} | High ({round(best_sources[0].win_rate + 5)}%) |

### Why These Criteria
- **{top_industries[0].category}** wins at {top_industries[0].win_rate}% vs overall {overview.win_rate}% — our product resonates most with these buyers
- **{best_company_size.category}** = right complexity level; large enough to have budget, small enough to make fast decisions
- **{best_size.category}** = our proven value delivery zone; above this, we compete with enterprise vendors

### Disqualification Criteria (Walk Away)
- {worst_competitor.competitor if worst_competitor else 'Key competitor'} presence in deal with their stronghold industry
- Deals over $150K without executive sponsor at VP+ level
- {best_sources[-1].category if len(best_sources) > 1 else 'Unqualified'}-sourced deal with Manager-level contact only
- Industry with <25% win rate and company size outside {best_company_size.category}

### Lead Scoring Model
- **A-Lead ({round(overview.win_rate + 15)}%+ expected win rate)**: {top_industries[0].category}/{top_industries[1].category if len(top_industries) > 1 else top_industries[0].category} + {best_company_size.category} + {best_sources[0].category} + {best_buyer.category}
- **B-Lead (50-80%)**: Right industry OR right size + decent source
- **C-Lead (30-50%)**: Mixed signals, one strong factor
- **D-Lead (<30%)**: Multiple red flags, deprioritize

### Positioning by Segment
- **{top_industries[0].category}**: Lead with speed, flexibility, and innovation. Win rate: {top_industries[0].win_rate}%
- **{top_industries[1].category if len(top_industries) > 1 else 'Enterprise'}**: Lead with reliability, support, and integration. Win rate: {top_industries[1].win_rate if len(top_industries) > 1 else 'N/A'}%
- **Mid-market**: Emphasize rapid time-to-value and dedicated support"""


def _mock_competitor_briefing() -> str:
    """Generate dynamic competitor briefing from actual win/loss data."""
    competitors = compute_competitors()

    if not competitors:
        return "## Competitive Intelligence Briefing\n\nNo competitor data available yet."

    briefing_sections = []
    for c in competitors[:4]:
        threat_level = "HIGH" if c.win_rate < 35 else "MEDIUM" if c.win_rate < 50 else "LOW"
        industries_str = ', '.join(c.industries[:2]) if c.industries else "enterprise accounts"
        top_reason = c.top_loss_reasons[0] if c.top_loss_reasons else "price"

        section = f"""### {c.competitor}
- **Threat Level**: {threat_level} — {c.win_rate}% win rate when they're involved ({c.losses} losses to them)
- **Where They Win**: {industries_str} — particularly in deals where {top_reason} is the deciding factor
- **Where We Win**: Deals with VP+ buyers and referral sources; our relationship-based selling outperforms their product-led approach
- **Battle Card**:
  1. Ask about their experience with {c.competitor}'s implementation timeline (typically 2-3x longer)
  2. Reference our {c.industries[0] if c.industries else "enterprise"}-specific case studies
  3. Offer a technical proof-of-concept to demonstrate superiority in their specific use case
  4. Highlight our customer retention rate and dedicated support model"""

        briefing_sections.append(section)

    return "## Competitive Intelligence Briefing\n\n" + "\n\n".join(briefing_sections)


def _mock_sales_scripts() -> str:
    """Generate dynamic objection handling from actual objection data."""
    objections = compute_objections()
    overview = compute_overview()
    size_bd = compute_breakdown("deal_size")
    best_size = max(size_bd, key=lambda x: x.win_rate)

    # Get top 3 objections
    top_objections = objections[:3] if objections else []

    scripts_content = "## Objection Handling Guide\n\n### Top Objections & Response Scripts\n\n"

    if not top_objections:
        scripts_content += "**No objection data available yet.**"
        scripts_content += f"\n\n### Qualification Framework (BANT+)\n1. **Budget**: Is there allocated budget, or is this exploratory?\n2. **Authority**: Is our contact the decision maker, or do we need executive access?\n3. **Need**: Is this solving an active pain point or a nice-to-have?\n4. **Timeline**: Is there a compelling event driving the decision?\n5. **Fit**: Does this company match our ICP criteria?\n\n### Escalation Triggers\n- Bring in **Sales Engineering** when: technical objections arise in first 2 calls\n- Bring in **VP of Sales** when: deal over {best_size.category} and competitor involved\n- Bring in **Customer Success** when: prospect asks about implementation and support"
        return scripts_content

    for idx, obj in enumerate(top_objections, 1):
        scripts_content += f"**{idx}. \"{obj.objection}\"** (appears in {obj.frequency} deals, {obj.percentage}% of objections)\n"

        if idx == 1:
            scripts_content += f"> \"I understand that's a key consideration. Let me ask — what would the cost of *not* solving this problem be over the next 12 months? Our customers in {obj.industries[0] if obj.industries else 'similar'} typically see ROI within 90 days. Let me walk you through a specific example...\"\n\n"
            scripts_content += f"**Discovery question**: \"What's driving the urgency around this initiative?\"\n\n"
        elif idx == 2:
            scripts_content += f"> \"That's great feedback. How critical is this {obj.objection.lower()} to your workflow? We've found that 80% of our customers in {obj.industries[0] if obj.industries else 'your industry'} need exactly this. For anything beyond standard requirements, our API allows you to build exactly what you need in days.\"\n\n"
            scripts_content += f"**Discovery question**: \"Can you walk me through your current workflow and where this gaps most?\"\n\n"
        else:
            scripts_content += f"> \"We take this extremely seriously — it's actually one of our strongest differentiators. We're SOC 2 Type II certified and have strong controls for {obj.objection.lower()}. Would it help if I connected you with our team for a deep-dive?\"\n\n"
            scripts_content += f"**Discovery question**: \"What are your organization's specific requirements around {obj.objection.lower()}?\"\n\n"

    scripts_content += f"""### Qualification Framework (BANT+)
1. **Budget**: Is there allocated budget, or is this exploratory?
2. **Authority**: Is our contact the decision maker, or do we need executive access?
3. **Need**: Is this solving an active pain point or a nice-to-have?
4. **Timeline**: Is there a compelling event driving the decision?
5. **Fit**: Does this company match our ICP criteria?

### Escalation Triggers
- Bring in **Sales Engineering** when: technical objections arise in first 2 calls
- Bring in **VP of Sales** when: deal over {best_size.category} and competitor involved
- Bring in **Customer Success** when: prospect asks about implementation and support"""

    return scripts_content


def _generate_mock_response(prompt_type: str, industry: Optional[str] = None,
                            question: Optional[str] = None) -> str:
    """Generate realistic mock AI responses when no API key is configured."""
    overview = compute_overview()
    industry_bd = compute_breakdown("industry")
    competitors = compute_competitors()

    top_industry = max(industry_bd, key=lambda x: x.win_rate)
    worst_industry = min(industry_bd, key=lambda x: x.win_rate)
    worst_competitor = min(competitors, key=lambda x: x.win_rate) if competitors else None

    mock_responses = {
        "win_loss_summary": _mock_win_loss_summary(),

        "icp_generation": _mock_icp_generation(),

        "competitor_briefing": _mock_competitor_briefing(),

        "sales_scripts": _mock_sales_scripts(),

        "positioning": f"""## Positioning Recommendations

### Current Positioning Assessment
Our win patterns reveal we're positioned as a **mid-market solution for technology-forward companies**. Our sweet spot ($25K-$75K) suggests buyers see us as a professional-tier tool, not an enterprise platform.

### Messaging Recommendations
1. **For Technology**: Emphasize speed, API flexibility, and developer experience. Win rate: {top_industry.win_rate}%
2. **For Healthcare**: Lead with compliance, HIPAA readiness, and data security. Tailor demos to health-specific workflows
3. **For all segments**: Shift from feature-based to outcome-based messaging. Quantify ROI in terms they care about

### Proof Points to Develop
- ROI case study from a 200-employee Technology company (our ideal win scenario)
- Security audit / compliance certification for Healthcare segment
- Implementation speed benchmark (target: <30 days to value)

### Pricing Strategy
- **Sweet spot is $25K-$75K** — hold firm in this range, don't discount
- **Above $75K**: Bundle additional services to justify, or restructure as phased engagement
- **Above $150K**: Only pursue with executive sponsorship and multi-year commitment

### Channel Strategy
- **Invest heavily in Referral** (70% win rate) — launch formal referral program
- **Improve Inbound** (48% win rate) — optimize qualification to filter out poor-fit leads
- **Reduce Outbound spend** (30% win rate) — unless retargeted at ICP criteria""",

        "industry_loss": f"""## Why We Lose in {industry or worst_industry.category}

### Root Cause Analysis
1. **Product-Market Misfit**: {industry or worst_industry.category} companies typically have complex legacy systems that our integration layer doesn't handle well
2. **Wrong Buyer Level**: We're engaging too many Manager-level contacts (30% win rate) instead of VPs/Directors who can champion internally
3. **Competitive Disadvantage**: Specialized {industry or worst_industry.category} vendors have deeper domain expertise and established relationships

### Comparison with Best Industries
| Factor | Technology ({top_industry.win_rate}% win) | {industry or worst_industry.category} ({worst_industry.win_rate}% win) |
|--------|------------|---------------|
| Typical company size | 100-300 emp | 1000+ emp |
| Decision maker | VP/CTO | IT Manager |
| Sales cycle | ~30 days | ~70 days |
| Main objection | Feature questions | Price + Integration |

### Turnaround Strategy
1. **Narrow targeting**: Only pursue {industry or worst_industry.category} companies with <500 employees
2. **Build 2-3 {industry or worst_industry.category} case studies** to establish credibility
3. **Partner with a {industry or worst_industry.category} consultant** for co-selling
4. **Develop industry-specific demo** showcasing relevant use cases

### Go/No-Go Criteria
**Pursue if**: <500 employees, VP+ buyer, referral source, no ZetaFlow competitor, budget confirmed
**Walk away if**: 1000+ employees, Manager contact only, outbound source, 3+ competitors involved""",

        "sales_scripts": _mock_sales_scripts(),

        "ask_ai": _build_smart_mock_answer(question or ""),
    }

    return mock_responses.get(prompt_type, "Analysis not available for this prompt type.")
