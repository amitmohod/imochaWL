from typing import Optional
from fastapi import APIRouter, Query
from services.analytics import (
    compute_overview, compute_breakdown, compute_competitors,
    compute_objections, compute_icp, compute_strategic_signals,
    compute_filter_options, compute_patterns, compute_trends,
)

router = APIRouter()


@router.get("/overview")
def overview(product_line: Optional[str] = Query(None)):
    return compute_overview(product_line=product_line).model_dump()


@router.get("/filter-options")
def filter_options():
    """Lightweight filter options for dropdowns."""
    return compute_filter_options().model_dump()


@router.get("/breakdown/{dimension}")
def breakdown(
    dimension: str,
    quarter: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    sales_rep: Optional[str] = Query(None),
    product_line: Optional[str] = Query(None),
):
    """Dimensions: industry, deal_size, source, company_size, buyer_title, geography"""
    valid = ["industry", "deal_size", "source", "company_size", "buyer_title", "geography"]
    if dimension not in valid:
        return {"error": f"Invalid dimension. Choose from: {valid}"}
    return [item.model_dump() for item in compute_breakdown(
        dimension, quarter=quarter, industry=industry, region=region,
        sales_rep=sales_rep, product_line=product_line,
    )]


@router.get("/competitors")
def competitors(product_line: Optional[str] = Query(None)):
    return [c.model_dump() for c in compute_competitors(product_line=product_line)]


@router.get("/objections")
def objections(product_line: Optional[str] = Query(None)):
    return [o.model_dump() for o in compute_objections(product_line=product_line)]


@router.get("/icp")
def icp(product_line: Optional[str] = Query(None)):
    return compute_icp(product_line=product_line).model_dump()


@router.get("/patterns")
def patterns(
    quarter: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    sales_rep: Optional[str] = Query(None),
    product_line: Optional[str] = Query(None),
):
    """Pattern discovery with conversation evidence."""
    return [p.model_dump() for p in compute_patterns(
        quarter=quarter, industry=industry, region=region,
        sales_rep=sales_rep, product_line=product_line,
    )]


@router.get("/trends")
def trends(product_line: Optional[str] = Query(None)):
    """Monthly win rate trend for the full dataset."""
    return [t.model_dump() for t in compute_trends(product_line=product_line)]


@router.get("/signals")
def signals(
    quarter: Optional[str] = Query(None, description="Q1, Q2, Q3, or Q4"),
    industry: Optional[str] = Query(None),
    region: Optional[str] = Query(None, description="City name"),
    sales_rep: Optional[str] = Query(None),
    product_line: Optional[str] = Query(None),
):
    """Strategic signals for the CEO intelligence dashboard."""
    return compute_strategic_signals(
        quarter=quarter,
        industry=industry,
        region=region,
        sales_rep=sales_rep,
        product_line=product_line,
    ).model_dump()
