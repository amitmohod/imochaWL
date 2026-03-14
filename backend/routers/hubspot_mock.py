"""Mock HubSpot API endpoints — mirrors real HubSpot CRM API structure."""

from fastapi import APIRouter, Query
from services.mock_hubspot import get_companies, get_contacts, get_deals, get_company, get_contact

router = APIRouter()


@router.get("/companies")
def list_companies(limit: int = Query(100, le=500), offset: int = 0):
    companies = get_companies()
    subset = companies[offset:offset + limit]
    return {
        "results": [c.model_dump() for c in subset],
        "total": len(companies),
        "offset": offset,
    }


@router.get("/companies/{company_id}")
def get_company_detail(company_id: str):
    company = get_company(company_id)
    if not company:
        return {"error": "Company not found"}
    return company.model_dump()


@router.get("/contacts")
def list_contacts(limit: int = Query(100, le=500), offset: int = 0):
    contacts = get_contacts()
    subset = contacts[offset:offset + limit]
    return {
        "results": [c.model_dump() for c in subset],
        "total": len(contacts),
        "offset": offset,
    }


@router.get("/deals")
def list_deals(limit: int = Query(100, le=500), offset: int = 0):
    deals = get_deals()
    subset = deals[offset:offset + limit]
    return {
        "results": [d.model_dump() for d in subset],
        "total": len(deals),
        "offset": offset,
    }


@router.get("/deals/{deal_id}")
def get_deal_detail(deal_id: str):
    from services.mock_hubspot import get_deal
    deal = get_deal(deal_id)
    if not deal:
        return {"error": "Deal not found"}
    return deal.model_dump()
