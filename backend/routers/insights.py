from fastapi import APIRouter, Query
from typing import Optional
from models.analysis import AskAIRequest, AIInsightResponse, AskAIResponse
from services.claude_ai import generate_insight

router = APIRouter()


@router.get("/product-brief")
async def product_brief(product_line: Optional[str] = Query(None)):
    content = await generate_insight("product_brief", product_line=product_line or "all")
    return AIInsightResponse(content=content, prompt_type="product_brief").model_dump()


@router.get("/win-loss-summary")
async def win_loss_summary():
    content = await generate_insight("win_loss_summary")
    return AIInsightResponse(content=content, prompt_type="win_loss_summary").model_dump()


@router.get("/icp")
async def icp_insight():
    content = await generate_insight("icp_generation")
    return AIInsightResponse(content=content, prompt_type="icp_generation").model_dump()


@router.get("/competitors")
async def competitor_briefing():
    content = await generate_insight("competitor_briefing")
    return AIInsightResponse(content=content, prompt_type="competitor_briefing").model_dump()


@router.get("/positioning")
async def positioning():
    content = await generate_insight("positioning")
    return AIInsightResponse(content=content, prompt_type="positioning").model_dump()


@router.get("/industry-loss")
async def industry_loss(industry: str = Query(...)):
    content = await generate_insight("industry_loss", industry=industry)
    return AIInsightResponse(content=content, prompt_type="industry_loss").model_dump()


@router.get("/sales-scripts")
async def sales_scripts():
    content = await generate_insight("sales_scripts")
    return AIInsightResponse(content=content, prompt_type="sales_scripts").model_dump()


@router.post("/ask")
async def ask_ai(req: AskAIRequest):
    content = await generate_insight("ask_ai", question=req.question)
    return AskAIResponse(answer=content, question=req.question).model_dump()
