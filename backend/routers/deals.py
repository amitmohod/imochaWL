from fastapi import APIRouter, Query
from typing import Optional
from services.analytics import get_enriched_deals

router = APIRouter()


@router.get("")
def list_deals(
    stage: Optional[str] = None,
    industry: Optional[str] = None,
    source: Optional[str] = None,
):
    deals = get_enriched_deals(stage=stage, industry=industry, source=source)
    return [d.model_dump() for d in deals]


@router.get("/recent")
def recent_deals(limit: int = Query(10, le=50)):
    deals = get_enriched_deals()
    sorted_deals = sorted(deals, key=lambda d: d.close_date, reverse=True)
    return [d.model_dump() for d in sorted_deals[:limit]]
