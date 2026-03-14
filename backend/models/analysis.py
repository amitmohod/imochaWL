from pydantic import BaseModel
from typing import List, Optional


class OverviewMetrics(BaseModel):
    total_deals: int
    won_deals: int
    lost_deals: int
    win_rate: float
    total_revenue: float
    avg_deal_size: float
    avg_cycle_won: float
    avg_cycle_lost: float


class BreakdownItem(BaseModel):
    category: str
    total: int
    won: int
    lost: int
    win_rate: float
    avg_deal_size: float
    total_revenue: float


class CompetitorMetrics(BaseModel):
    competitor: str
    deals_faced: int
    wins: int
    losses: int
    win_rate: float
    avg_deal_size: float
    top_loss_reasons: List[str]
    industries: List[str]


class ObjectionTheme(BaseModel):
    objection: str
    frequency: int
    percentage: float
    industries: List[str]
    win_rate_when_raised: float


class ICPProfile(BaseModel):
    industries: List[str]
    employee_range: str
    deal_size_range: str
    buyer_titles: List[str]
    preferred_sources: List[str]
    avg_cycle_days: int
    win_rate: float
    confidence: float


class AIInsightResponse(BaseModel):
    content: str
    prompt_type: str
    cached: bool = False


class SegmentStat(BaseModel):
    name: str
    win_rate: float
    total: int


class KPIComparison(BaseModel):
    period_label: str  # e.g. "vs Q3"
    win_rate_change: float  # pp change
    revenue_change_pct: float  # % change
    deal_count_change: int
    cycle_change: float  # days change


class ReasonCount(BaseModel):
    reason: str
    count: int


class FilterOptions(BaseModel):
    quarters: List[str]
    industries: List[str]
    regions: List[str]
    sales_reps: List[str]


class EnhancedKPIs(BaseModel):
    win_rate: float
    won_deals: int
    lost_deals: int
    best_segment: SegmentStat
    worst_segment: SegmentStat
    total_revenue: float
    total_lost_revenue: float
    top_leak_reason: str
    top_leak_amount: float
    avg_deal_size: float
    sweet_spot_range: str
    sweet_spot_win_rate: float
    large_deal_range: str
    large_deal_win_rate: float
    avg_cycle_won: float
    avg_cycle_lost: float
    cycle_drag: float
    comparison: Optional[KPIComparison] = None


class GrowthLever(BaseModel):
    source: str
    win_rate: float
    pipeline_pct: float
    total_deals: int


class RevenueLeak(BaseModel):
    competitor: str
    revenue_lost: float
    deals_lost: int


class ICPFitSignal(BaseModel):
    icp_match_pct: float
    icp_win_rate: float
    non_icp_win_rate: float


class ConversationThemeAgg(BaseModel):
    theme: str
    frequency: int
    deal_pct: float
    win_rate_when_raised: float
    impact_level: str  # "High", "Medium", "Low"
    sample_quote: str
    sample_source: str


class StrategicSignals(BaseModel):
    kpis: EnhancedKPIs
    growth_lever: GrowthLever
    revenue_leak: RevenueLeak
    icp_fit: ICPFitSignal
    conversation_themes: List[ConversationThemeAgg]
    win_reasons: List[ReasonCount] = []
    loss_reasons: List[ReasonCount] = []
    filters: Optional[FilterOptions] = None


class ConversationEvidence(BaseModel):
    quote: str
    source: str
    deal_name: str
    stage: str
    sentiment: str


class PatternInsight(BaseModel):
    category: str
    title: str
    description: str
    stat_label: str
    stat_value: str
    impact: str  # "positive", "negative", "neutral"
    evidence: List[ConversationEvidence]
    recommendation: str


class AskAIRequest(BaseModel):
    question: str


class AskAIResponse(BaseModel):
    answer: str
    question: str
