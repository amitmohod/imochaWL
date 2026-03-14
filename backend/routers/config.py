"""Endpoints for reading and switching the active data source."""
from typing import Optional, List, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.data_source import get_source, get_token, set_source

router = APIRouter()


class PreviewRequest(BaseModel):
    token: str


class DataSourceRequest(BaseModel):
    source: str
    token: Optional[str] = None
    override_deals: Optional[List[Any]] = None  # selected + edited deals from preview


@router.get("")
def get_config():
    return {
        "data_source": get_source(),
        "has_token": bool(get_token()),
    }


@router.post("/preview")
def preview_hubspot(body: PreviewRequest):
    """Fetch deals from HubSpot for preview WITHOUT switching the active data source."""
    if not body.token:
        raise HTTPException(status_code=400, detail="Token is required")
    try:
        from services.hubspot_real import fetch_preview
        import httpx
        deals = fetch_preview(body.token)
        return {"deals": deals, "total": len(deals)}
    except Exception as e:
        import httpx
        if hasattr(e, "response"):
            status = e.response.status_code
            if status == 401:
                raise HTTPException(status_code=401, detail="Invalid token. Check your HubSpot Private App access token.")
            raise HTTPException(status_code=400, detail=f"HubSpot API error: {status}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data-source")
def switch_data_source(body: DataSourceRequest):
    if body.source == "hubspot" and not body.token:
        raise HTTPException(status_code=400, detail="HubSpot access token is required")

    override = None
    if body.override_deals is not None:
        # Reconstruct Deal objects from the edited preview data
        from models.hubspot import Deal, ConversationSignal
        from datetime import datetime
        deals = []
        for d in body.override_deals:
            try:
                close_date = datetime.fromisoformat(d["close_date"])
                create_date = datetime.fromisoformat(d["create_date"])
            except Exception:
                close_date = create_date = datetime.now()
            deals.append(Deal(
                id=d["id"],
                name=d["name"],
                stage=d["stage"],
                amount=float(d.get("amount") or 0),
                close_date=close_date,
                create_date=create_date,
                pipeline=d.get("pipeline") or "default",
                product_line=d.get("product_line") or "TA",
                deal_source=d.get("deal_source") or "Unknown",
                loss_reason=d.get("loss_reason"),
                win_reason=d.get("win_reason"),
                competitor=d.get("competitor"),
                sales_rep=d.get("sales_rep") or "",
                company_id=d.get("company_id") or "",
                contact_id=d.get("contact_id") or "",
                cycle_days=int(d.get("cycle_days") or 0),
                objections=[],
                conversation_signals=[],
            ))
        override = deals

    try:
        set_source(body.source, token=body.token or "", override_deals=override)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"data_source": get_source()}
