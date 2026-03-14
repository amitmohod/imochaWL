from typing import Optional
from fastapi import APIRouter, Query
from services.product_analytics import compute_feature_gaps, compute_integration_gaps, compute_persona_needs

router = APIRouter()


@router.get("/feature-gaps")
def feature_gaps(product_line: Optional[str] = Query(None)):
    return [g.model_dump() for g in compute_feature_gaps(product_line)]


@router.get("/integration-gaps")
def integration_gaps(product_line: Optional[str] = Query(None)):
    return [g.model_dump() for g in compute_integration_gaps(product_line)]


@router.get("/persona-needs")
def persona_needs(product_line: Optional[str] = Query(None)):
    return [p.model_dump() for p in compute_persona_needs(product_line)]
