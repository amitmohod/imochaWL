from pydantic import BaseModel
from typing import List, Optional


class FeatureGap(BaseModel):
    name: str
    deals_affected: int
    revenue_at_risk: float
    competitors: List[str]
    sample_quote: str
    sample_quote_context: str  # e.g. "Lost deal · IT Services"
    source: str  # "loss_reason" or "objection"


class IntegrationGap(BaseModel):
    name: str
    deals_affected: int
    revenue_at_risk: float
    severity: str  # "high" or "medium"


class PersonaNeed(BaseModel):
    title: str          # e.g. "VP" or "C-Level"
    win_rate: float
    top_asks: List[str]
    deal_count: int
    concern: str        # AI-derived summary of the persona's key concern
