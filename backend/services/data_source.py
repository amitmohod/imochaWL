"""Routes data access between mock and real HubSpot based on current setting."""
from typing import Optional, List

_source = "mock"
_hubspot_token = ""        # in-memory only, never persisted to disk
_override_deals = None     # selected + edited deals from preview step; None = fetch live


def get_source() -> str:
    return _source


def get_token() -> str:
    return _hubspot_token


def set_source(source: str, token: str = "", override_deals=None) -> None:
    global _source, _hubspot_token, _override_deals
    if source not in ("mock", "hubspot"):
        raise ValueError(f"Invalid source: {source}")
    if source == "hubspot":
        if not token:
            raise ValueError("HubSpot access token is required")
        _hubspot_token = token
        _override_deals = override_deals  # may be None (fetch live) or a list of deals
    else:
        _hubspot_token = ""
        _override_deals = None
    try:
        import services.hubspot_real as hr
        hr._cache.clear()
    except Exception:
        pass
    # Clear AI insights cache (late import to avoid circular dependency)
    try:
        from services.claude_ai import clear_insights_cache
        clear_insights_cache()
    except Exception:
        pass
    _source = source


def get_companies():
    if _source == "hubspot":
        from services.hubspot_real import get_companies
        return get_companies()
    from services.mock_hubspot import get_companies
    return get_companies()


def get_contacts():
    if _source == "hubspot":
        from services.hubspot_real import get_contacts
        return get_contacts()
    from services.mock_hubspot import get_contacts
    return get_contacts()


def get_deals():
    if _source == "hubspot":
        if _override_deals is not None:
            return _override_deals
        from services.hubspot_real import get_deals
        return get_deals()
    from services.mock_hubspot import get_deals
    return get_deals()


def get_company(company_id: str):
    if _source == "hubspot":
        from services.hubspot_real import get_company
        return get_company(company_id)
    from services.mock_hubspot import get_company
    return get_company(company_id)


def get_contact(contact_id: str):
    if _source == "hubspot":
        from services.hubspot_real import get_contact
        return get_contact(contact_id)
    from services.mock_hubspot import get_contact
    return get_contact(contact_id)
