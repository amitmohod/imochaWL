"""Real HubSpot CRM API integration using private app access token."""
import re
from typing import List, Optional, Dict, Set
from datetime import datetime
from collections import defaultdict

import httpx

from models.hubspot import Company, Contact, Deal, ConversationSignal

BASE = "https://api.hubapi.com"

# Session-level cache so repeated calls within one request cycle don't re-fetch
_cache: Dict[str, dict] = {}

# --- Industry Enum Mapping ---
HUBSPOT_INDUSTRY_MAP = {
    "COMPUTER_SOFTWARE": "IT Services",
    "INFORMATION_TECHNOLOGY_AND_SERVICES": "IT Services",
    "IT_SERVICES": "IT Services",
    "SOFTWARE": "IT Services",
    "FINANCIAL_SERVICES": "BFSI",
    "BANKING": "BFSI",
    "INSURANCE": "BFSI",
    "HOSPITAL_HEALTH_CARE": "Healthcare",
    "HEALTH_WELLNESS_AND_FITNESS": "Healthcare",
    "HEALTHCARE": "Healthcare",
    "PHARMACEUTICALS": "Healthcare",
    "MANUFACTURING": "Manufacturing",
    "AUTOMOTIVE": "Manufacturing",
    "INDUSTRIAL": "Manufacturing",
    "RETAIL": "Retail & E-Commerce",
    "CONSUMER_GOODS": "Retail & E-Commerce",
    "E_COMMERCE": "Retail & E-Commerce",
    "EDUCATION_MANAGEMENT": "EdTech",
    "E_LEARNING": "EdTech",
    "EDUCATION": "EdTech",
    "STAFFING_AND_RECRUITING": "Staffing",
    "HUMAN_RESOURCES": "Staffing",
    "LOGISTICS_AND_SUPPLY_CHAIN": "Logistics",
    "TRANSPORTATION": "Logistics",
    "REAL_ESTATE": "Real Estate",
    "CONSTRUCTION": "Construction",
    "GOVERNMENT": "Government",
    "PUBLIC_ADMINISTRATION": "Government",
    "TELECOMMUNICATIONS": "Telecom",
    "MEDIA_AND_INTERNET": "Media & Publishing",
    "PUBLISHING": "Media & Publishing",
    "ENTERTAINMENT": "Media & Publishing",
    "UTILITIES": "Utilities",
    "ENERGY": "Energy & Mining",
    "MINING": "Energy & Mining",
}

# Theme to objection mapping
THEME_TO_OBJECTION = {
    "Pricing": "Pricing concern raised",
    "Product Gap": "Feature/product gap identified",
    "Integration": "Integration gap with existing stack",
    "Requirement Mismatch": "Platform seen as too complex/broad",
    "Champion Risk": "Champion or budget risk flagged",
    "Competitive Pressure": "Competitor actively evaluated",
}

# Win reason mapping
WIN_REASON_MAP = {
    "Strong customer reference sold the deal": ["referral", "reference", "referred", "customer reference"],
    "Executive sponsor drove fast decision": ["executive", "ceo", "cto", "vp", "sponsor", "champion", "executive sponsor"],
    "Broader assessment coverage beyond coding": ["assessment", "coverage", "beyond coding", "assessment coverage"],
    "AI Interview Agent differentiation": ["tara", "ai interview", "interview agent", "conversational ai"],
    "Skills analytics depth unmatched": ["skills analytics", "skills intelligence", "workforce planning", "workforce"],
    "No competitive alternative — greenfield win": ["no competitor", "greenfield", "only vendor", "sole vendor"],
    "Superior platform value over point solutions": ["platform", "full suite", "end-to-end", "comprehensive"],
}

# --- Theme detection keywords ---
THEME_KEYWORDS = {
    "Pricing": [
        "price", "pricing", "cost", "expensive", "budget", "discount", "roi",
        "per candidate", "per seat", "afford", "too much", "cheaper",
    ],
    "Competitive Pressure": [
        "hackerrank", "codility", "hirevue", "testgorilla", "eightfold", "gloat",
        "lightcast", "mercer mettl", "competitor", "alternative", "competing",
        "current vendor", "renewal", "bundled",
    ],
    "Product Gap": [
        "feature", "missing", "gap", "no support", "limitation", "workaround",
        "roadmap", "doesn't have", "unable to", "proctoring", "bias", "fairness",
        "read-only", "write-back",
    ],
    "Integration": [
        "integrate", "integration", "workday", "greenhouse", "ats", "sso", "api",
        "connect", "sync", "native", "hris", "saml", "azure ad", "rate limit",
    ],
    "Requirement Mismatch": [
        "too broad", "overkill", "only need", "don't need", "just need",
        "point solution", "too complex", "simple", "only coding",
        "not the full platform",
    ],
    "Champion Risk": [
        "leaving", "left the company", "new vp", "new head", "reorganiz",
        "champion", "sponsor", "budget freeze", "hiring freeze", "on hold",
        "paused", "no timeline",
    ],
}

POSITIVE_WORDS = [
    "closed", "won", "signed", "approved", "excellent", "strong", "champion",
    "compelling", "differentiator", "resolved", "satisfied", "impressed",
    "smooth", "fast close", "referral",
]

NEGATIVE_WORDS = [
    "lost", "concern", "issue", "problem", "expensive", "not sure", "hesitant",
    "rejected", "could not", "unable", "gap", "freeze", "paused", "overruled",
]

# Loss reason keywords mapping
LOSS_REASON_MAP = {
    "Pricing": ["pricing", "price", "cost", "expensive", "discount", "cheaper", "price-sensitive", "per candidate", "per seat"],
    "Competitive Pressure": ["lost to", "competing with", "competitor", "hackerrank", "codility", "hirevue", "testgorilla", "eightfold", "gloat", "mercer", "lightcast", "bundled", "released"],
    "Product Gap": ["missing feature", "gap", "limitation", "product gap", "doesn't have", "unable to", "workaround", "roadmap", "integration gap", "api rate"],
    "Integration": ["integration", "integrate", "workday", "greenhouse", "ats", "sso", "sync", "native", "hris", "saml", "azure ad", "bi-directional"],
    "Requirement Mismatch": ["overkill", "too broad", "point solution", "only need", "too complex"],
    "Champion Risk": ["champion left", "champion risk", "new vp", "new head", "reorganiz", "budget freeze", "hiring freeze", "on hold", "paused"],
    "Implementation": ["timeline", "implementation", "go live", "weeks", "days"],
}


def _headers():
    from services.data_source import get_token
    return {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    }


def _paginate(url: str, params: dict, max_records: int = 500) -> list:
    results = []
    after = None
    while len(results) < max_records:
        p = {**params, "limit": 100}
        if after:
            p["after"] = after
        resp = httpx.get(url, headers=_headers(), params=p, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
    return results


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def _extract_loss_reason(note_text: str) -> Optional[str]:
    """Extract loss reason from note text by matching keywords."""
    if not note_text:
        return None

    text_lower = note_text.lower()

    # Match against loss reason keywords (don't require "lost" keyword)
    for reason, keywords in LOSS_REASON_MAP.items():
        if any(kw in text_lower for kw in keywords):
            return reason

    return None


def _extract_win_reason(note_text: str) -> Optional[str]:
    """Extract win reason from note text by matching keywords."""
    if not note_text:
        return None

    text_lower = note_text.lower()

    # Match against win reason keywords
    for reason, keywords in WIN_REASON_MAP.items():
        if keywords and any(kw in text_lower for kw in keywords):
            return reason

    return None


def _extract_competitor(note_text: str) -> Optional[str]:
    """Extract competitor name from note text."""
    if not note_text:
        return None

    text_lower = note_text.lower()

    competitors = {
        "hackerrank": "HackerRank",
        "codility": "Codility",
        "hirevue": "HireVue",
        "testgorilla": "TestGorilla",
        "eightfold": "Eightfold",
        "gloat": "Gloat",
        "mercer": "Mercer Mettl",
        "lightcast": "Lightcast",
        "sap": "SAP SuccessFactors",
        "greenhouse": "Greenhouse",
    }

    for key, competitor_name in competitors.items():
        if key in text_lower:
            return competitor_name

    return None


def _extract_deal_source(note_text: str, deal_name: str = "") -> str:
    """Extract deal source from note text and deal name."""
    if not note_text:
        note_text = ""

    text_lower = note_text.lower() + " " + deal_name.lower()

    # Check for referral/referral mention
    if "referral" in text_lower:
        return "Referral"

    # Check for specific source mentions
    if "inbound" in text_lower or "content" in text_lower or "form" in text_lower or "web" in text_lower:
        return "Inbound"

    if "outbound" in text_lower or "sdr" in text_lower or "sourced" in text_lower:
        return "Outbound"

    if "event" in text_lower or "conference" in text_lower or "webinar" in text_lower:
        return "Event"

    if "partner" in text_lower or "channel" in text_lower:
        return "Partner"

    # Default based on deal name patterns
    if "marketplace" in text_lower or "app" in text_lower:
        return "Marketplace"

    return "Direct"


def _parse_note_to_signal(note_body: str) -> ConversationSignal:
    """Parse a HubSpot note body into a ConversationSignal."""
    clean = _strip_html(note_body)
    text = clean.lower()

    # Detect theme — first match wins
    theme = "General"
    for t, keywords in THEME_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            theme = t
            break

    # Detect sentiment
    neg_score = sum(1 for w in NEGATIVE_WORDS if w in text)
    pos_score = sum(1 for w in POSITIVE_WORDS if w in text)
    if neg_score > pos_score:
        sentiment = "negative"
    elif pos_score > neg_score:
        sentiment = "positive"
    else:
        sentiment = "neutral"

    # Truncate quote to 280 chars
    quote = clean[:280] + ("…" if len(clean) > 280 else "")

    return ConversationSignal(
        theme=theme,
        quote=quote,
        source="HubSpot Notes",
        sentiment=sentiment,
    )


def _get_owner_name_map(token: Optional[str] = None) -> Dict[str, str]:
    """Fetch HubSpot owner IDs and map to names (cached per request)."""
    if "owner_map" in _cache:
        return _cache["owner_map"]

    from services.data_source import get_token as get_stored_token
    headers = {
        "Authorization": f"Bearer {token or get_stored_token()}",
        "Content-Type": "application/json",
    }
    owners: Dict[str, str] = {}

    try:
        resp = httpx.get(
            f"{BASE}/crm/v3/owners",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            for owner in resp.json().get("results", []):
                owner_id = str(owner.get("id", ""))
                first_name = owner.get("firstName", "")
                last_name = owner.get("lastName", "")
                full_name = f"{first_name} {last_name}".strip()
                if owner_id and full_name:
                    owners[owner_id] = full_name
    except Exception:
        pass

    _cache["owner_map"] = owners
    return owners


def _fetch_notes_by_deal(deal_ids: Set[str], token: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Fetch all notes that are associated with the given deal IDs.
    Returns dict: deal_id -> [note_body, ...]
    """
    deal_notes: Dict[str, List[str]] = defaultdict(list)
    if not deal_ids:
        return deal_notes

    # Use provided token or fall back to global token
    headers = {
        "Authorization": f"Bearer {token or get_token()}",
        "Content-Type": "application/json",
    }

    after = None
    while True:
        params: dict = {
            "properties": "hs_note_body",
            "associations": "deals",
            "limit": 100,
        }
        if after:
            params["after"] = after

        try:
            resp = httpx.get(
                f"{BASE}/crm/v3/objects/notes",
                headers=headers,
                params=params,
                timeout=20,
            )
            if resp.status_code != 200:
                break
            data = resp.json()
        except Exception as e:
            break

        for note in data.get("results", []):
            body = note.get("properties", {}).get("hs_note_body") or ""
            body = body.strip()
            if not body:
                continue
            associated_deals = (
                note.get("associations", {})
                .get("deals", {})
                .get("results", [])
            )
            for assoc in associated_deals:
                did = assoc.get("id", "")
                if did in deal_ids:
                    deal_notes[did].append(body)

        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
    return deal_notes


def get_companies() -> List[Company]:
    if "companies" in _cache:
        return list(_cache["companies"].values())

    props = ["name", "industry", "numberofemployees", "annualrevenue", "website", "city", "state"]
    records = _paginate(f"{BASE}/crm/v3/objects/companies", {"properties": ",".join(props)})

    companies = []
    for r in records:
        p = r.get("properties", {})
        try:
            emp = int(float(p.get("numberofemployees") or 0))
        except (ValueError, TypeError):
            emp = 0
        try:
            rev = float(p.get("annualrevenue") or 0) or None
        except (ValueError, TypeError):
            rev = None

        # Map industry from HubSpot enum to readable string
        raw_industry = p.get("industry") or ""
        industry = HUBSPOT_INDUSTRY_MAP.get(raw_industry.upper(), raw_industry or "Unknown")

        # If still "Unknown", try name-based fallback
        if industry == "Unknown":
            name_lower = (p.get("name") or "").lower()
            if any(x in name_lower for x in ["bank", "financial", "credit", "mortgage"]):
                industry = "BFSI"
            elif any(x in name_lower for x in ["hospital", "health", "clinic", "med"]):
                industry = "Healthcare"
            elif any(x in name_lower for x in ["tech", "software", "it", "cloud", "saas"]):
                industry = "IT Services"
            elif any(x in name_lower for x in ["logistics", "transport", "shipping"]):
                industry = "Logistics"
            elif any(x in name_lower for x in ["retail", "store", "shop", "e-commerce"]):
                industry = "Retail & E-Commerce"
            elif any(x in name_lower for x in ["school", "university", "education"]):
                industry = "EdTech"

        # Estimate employee count from revenue if not provided
        if emp == 0 and rev:
            if rev >= 1_000_000_000:
                emp = 5000
            elif rev >= 100_000_000:
                emp = 1000
            elif rev >= 10_000_000:
                emp = 200
            elif rev >= 1_000_000:
                emp = 75
            else:
                emp = 25

        companies.append(Company(
            id=r["id"],
            name=p.get("name") or "Unknown",
            industry=industry,
            employee_count=emp,
            annual_revenue=rev,
            website=p.get("website"),
            city=p.get("city"),
            state=p.get("state"),
        ))

    _cache["companies"] = {c.id: c for c in companies}
    return companies


def _seniority_from_title(title: str) -> str:
    if not title:
        return "Manager"
    t = title.lower()
    if any(x in t for x in ["chief", "ceo", "cto", "coo", "cfo", "chro", "cpo", "president"]):
        return "C-Level"
    if any(x in t for x in ["vp", "vice president", "head of"]):
        return "VP"
    if "director" in t:
        return "Director"
    return "Manager"


def get_contacts() -> List[Contact]:
    if "contacts" in _cache:
        return list(_cache["contacts"].values())

    props = ["firstname", "lastname", "email", "jobtitle", "associatedcompanyid"]
    records = _paginate(f"{BASE}/crm/v3/objects/contacts", {"properties": ",".join(props)})

    contacts = []
    for r in records:
        p = r.get("properties", {})
        title = p.get("jobtitle") or ""
        contacts.append(Contact(
            id=r["id"],
            first_name=p.get("firstname") or "",
            last_name=p.get("lastname") or "",
            email=p.get("email") or "",
            title=title,
            seniority=_seniority_from_title(title),
            company_id=p.get("associatedcompanyid") or "",
        ))

    _cache["contacts"] = {c.id: c for c in contacts}
    return contacts


def _infer_source(deal_name: str) -> str:
    """Infer deal source from deal name patterns."""
    name_lower = deal_name.lower()
    if any(x in name_lower for x in ["marketplace", "app", "store"]):
        return "Marketplace"
    if any(x in name_lower for x in ["partner", "referral", "channel"]):
        return "Partner"
    if any(x in name_lower for x in ["event", "conference", "webinar", "demo"]):
        return "Event"
    if any(x in name_lower for x in ["inbound", "form", "web"]):
        return "Inbound"
    return "Direct"


def _infer_competitor(deal_name: str) -> Optional[str]:
    """Infer competitor from deal name patterns."""
    competitors_map = {
        "hackerrank": "HackerRank",
        "codility": "Codility",
        "hirevue": "HireVue",
        "testgorilla": "TestGorilla",
        "eightfold": "Eightfold",
        "gloat": "Gloat",
        "mercer": "Mercer Mettl",
        "lightcast": "Lightcast",
    }
    name_lower = deal_name.lower()
    for key, competitor in competitors_map.items():
        if key in name_lower:
            return competitor
    return None


def _parse_dt(value: str) -> datetime:
    if not value:
        return datetime.now()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.now()


def get_deals() -> List[Deal]:
    if "deals" in _cache:
        return list(_cache["deals"].values())

    # Fetch standard HubSpot properties + any custom ones that might exist
    props = [
        "dealname", "dealstage", "amount", "closedate", "createdate", "pipeline",
        "dealtype", "dealstage", "hs_analytics_deal_stage",
        # Try custom properties (these may not exist)
        "deal_source", "loss_reason", "win_reason", "competitor",
        "sales_rep", "product_line", "hubspotownerid",
    ]
    records = _paginate(
        f"{BASE}/crm/v3/objects/deals",
        {"properties": ",".join(props), "associations": "companies,contacts"},
    )

    deals = []
    for r in records:
        p = r.get("properties", {})
        stage = p.get("dealstage") or ""

        if stage not in ("closedwon", "closedlost"):
            continue

        assoc = r.get("associations", {})
        comp_results = assoc.get("companies", {}).get("results", [])
        cont_results = assoc.get("contacts", {}).get("results", [])
        company_id = comp_results[0]["id"] if comp_results else ""
        contact_id = cont_results[0]["id"] if cont_results else ""

        close_date = _parse_dt(p.get("closedate", ""))
        create_date = _parse_dt(p.get("createdate", ""))
        cycle_days = max(0, (close_date - create_date).days)

        try:
            amount = float(p.get("amount") or 0)
        except (ValueError, TypeError):
            amount = 0.0

        # Map custom fields with fallbacks from standard fields or generation
        deal_source = p.get("deal_source") or p.get("dealtype") or _infer_source(p.get("dealname", ""))
        if not deal_source or deal_source.lower() in ("unknown", "none", ""):
            deal_source = "Direct" if amount > 50000 else "Inbound"

        deals.append(Deal(
            id=r["id"],
            name=p.get("dealname") or "Untitled Deal",
            stage=stage,
            amount=amount,
            close_date=close_date,
            create_date=create_date,
            pipeline=p.get("pipeline") or "default",
            product_line=p.get("product_line") or ("TA" if "hiring" in p.get("dealname", "").lower() else "TM"),
            deal_source=deal_source,
            loss_reason=p.get("loss_reason"),
            win_reason=p.get("win_reason"),
            competitor=p.get("competitor") or _infer_competitor(p.get("dealname", "")),
            sales_rep=p.get("sales_rep") or p.get("hubspotownerid") or "",
            company_id=company_id,
            contact_id=contact_id,
            cycle_days=cycle_days,
            objections=[],
            conversation_signals=[],
        ))

    # Fetch notes and attach as conversation signals + extract structured data
    deal_id_set = {d.id for d in deals}
    try:
        note_map = _fetch_notes_by_deal(deal_id_set)
        for deal in deals:
            notes = note_map.get(deal.id, [])
            deal.conversation_signals = [_parse_note_to_signal(n) for n in notes]

            # Derive objections from conversation signal themes
            if not deal.objections and deal.conversation_signals:
                deal.objections = list({
                    THEME_TO_OBJECTION[sig.theme]
                    for sig in deal.conversation_signals
                    if sig.theme in THEME_TO_OBJECTION
                })

            # Extract loss_reason, competitor, win_reason from notes
            combined_notes = " ".join(notes)
            if combined_notes:
                # Extract competitor from notes
                extracted_competitor = _extract_competitor(combined_notes)
                if extracted_competitor:
                    deal.competitor = extracted_competitor

                # Extract loss_reason from notes for lost deals
                if deal.stage == "closedlost":
                    extracted_loss_reason = _extract_loss_reason(combined_notes)
                    if extracted_loss_reason:
                        deal.loss_reason = extracted_loss_reason

                # Extract win_reason from notes for won deals
                if deal.stage == "closedwon" and not deal.win_reason:
                    extracted_win_reason = _extract_win_reason(combined_notes)
                    if extracted_win_reason:
                        deal.win_reason = extracted_win_reason

                # Extract deal_source from notes if it's still generic
                if deal.deal_source in ("Unknown", "Direct", "Inbound"):
                    extracted_source = _extract_deal_source(combined_notes, deal.name)
                    # Only override if we got a more specific source
                    if extracted_source not in ("Direct", "Inbound"):
                        deal.deal_source = extracted_source
    except Exception as e:
        # If note extraction fails, continue with base deal data
        print(f"Note extraction failed: {e}", flush=True)

    # Resolve owner IDs to names
    owner_map = _get_owner_name_map()
    for deal in deals:
        if deal.sales_rep and deal.sales_rep.isdigit():
            deal.sales_rep = owner_map.get(deal.sales_rep, deal.sales_rep)

    _cache["deals"] = {d.id: d for d in deals}
    return deals


def fetch_preview(token: str, limit: int = 100) -> List[dict]:
    """Fetch deals + company names using the given token without touching global state."""
    def _h():
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    props = [
        "dealname", "dealstage", "amount", "closedate", "createdate", "pipeline",
        "dealtype", "hs_analytics_deal_stage",
        "deal_source", "loss_reason", "win_reason", "competitor", "sales_rep", "product_line", "hubspotownerid",
    ]
    resp = httpx.get(
        f"{BASE}/crm/v3/objects/deals",
        headers=_h(),
        params={"properties": ",".join(props), "associations": "companies,contacts", "limit": min(limit, 100)},
        timeout=20,
    )
    resp.raise_for_status()
    records = resp.json().get("results", [])

    # Batch fetch company names
    company_ids = set()
    for r in records:
        ids = r.get("associations", {}).get("companies", {}).get("results", [])
        if ids:
            company_ids.add(ids[0]["id"])

    company_names: dict = {}
    if company_ids:
        batch_resp = httpx.post(
            f"{BASE}/crm/v3/objects/companies/batch/read",
            headers=_h(),
            json={"inputs": [{"id": cid} for cid in company_ids], "properties": ["name"]},
            timeout=20,
        )
        if batch_resp.status_code == 200:
            for r in batch_resp.json().get("results", []):
                company_names[r["id"]] = r.get("properties", {}).get("name", "")

    deals = []
    for r in records:
        p = r.get("properties", {})
        stage = p.get("dealstage") or "unknown"

        assoc = r.get("associations", {})
        comp_list = assoc.get("companies", {}).get("results", [])
        cont_list = assoc.get("contacts", {}).get("results", [])
        company_id = comp_list[0]["id"] if comp_list else ""
        contact_id = cont_list[0]["id"] if cont_list else ""

        close_date = _parse_dt(p.get("closedate", ""))
        create_date = _parse_dt(p.get("createdate", ""))

        try:
            amount = float(p.get("amount") or 0)
        except (ValueError, TypeError):
            amount = 0.0

        # Map custom fields with fallbacks
        deal_source = p.get("deal_source") or p.get("dealtype") or _infer_source(p.get("dealname", ""))
        if not deal_source or deal_source.lower() in ("unknown", "none", ""):
            deal_source = "Direct" if amount > 50000 else "Inbound"

        deals.append({
            "id": r["id"],
            "name": p.get("dealname") or "Untitled Deal",
            "stage": stage,
            "amount": amount,
            "close_date": close_date.isoformat(),
            "create_date": create_date.isoformat(),
            "pipeline": p.get("pipeline") or "default",
            "product_line": p.get("product_line") or ("TA" if "hiring" in p.get("dealname", "").lower() else "TM"),
            "deal_source": deal_source,
            "loss_reason": p.get("loss_reason"),
            "win_reason": p.get("win_reason"),
            "competitor": p.get("competitor") or _infer_competitor(p.get("dealname", "")),
            "sales_rep": p.get("sales_rep") or p.get("hubspotownerid") or "",
            "company_id": company_id,
            "company_name": company_names.get(company_id, ""),
            "contact_id": contact_id,
            "cycle_days": max(0, (close_date - create_date).days),
            "objections": [],
            "conversation_signals": [],  # Will be populated by note extraction below
        })

    # Fetch notes and extract structured data for preview
    deal_id_set = {d["id"] for d in deals}
    try:
        note_map = _fetch_notes_by_deal(deal_id_set, token=token)
        for deal in deals:
            notes = note_map.get(deal["id"], [])
            combined_notes = " ".join(notes)

            # Parse notes into conversation signals (convert to dict for JSON serialization)
            deal["conversation_signals"] = [
                _parse_note_to_signal(n).model_dump() for n in notes
            ]

            # Derive objections from conversation signal themes
            if not deal["objections"] and deal["conversation_signals"]:
                deal["objections"] = list({
                    THEME_TO_OBJECTION[sig["theme"]]
                    for sig in deal["conversation_signals"]
                    if sig["theme"] in THEME_TO_OBJECTION
                })

            if combined_notes:
                # Extract competitor from notes
                extracted_competitor = _extract_competitor(combined_notes)
                if extracted_competitor:
                    deal["competitor"] = extracted_competitor

                # Extract loss_reason from notes for lost deals
                if deal["stage"] == "closedlost":
                    extracted_loss_reason = _extract_loss_reason(combined_notes)
                    if extracted_loss_reason:
                        deal["loss_reason"] = extracted_loss_reason

                # Extract win_reason from notes for won deals
                if deal["stage"] == "closedwon" and not deal["win_reason"]:
                    extracted_win_reason = _extract_win_reason(combined_notes)
                    if extracted_win_reason:
                        deal["win_reason"] = extracted_win_reason

                # Extract deal_source from notes if it's still generic
                if deal["deal_source"] in ("Unknown", "Direct", "Inbound"):
                    extracted_source = _extract_deal_source(combined_notes, deal["name"])
                    # Only override if we got a more specific source
                    if extracted_source not in ("Direct", "Inbound"):
                        deal["deal_source"] = extracted_source
    except Exception as e:
        # If note extraction fails, continue with base deal data
        print(f"Note extraction failed: {e}", flush=True)

    return deals


def get_company(company_id: str) -> Optional[Company]:
    if "companies" not in _cache:
        get_companies()
    return _cache.get("companies", {}).get(company_id)


def get_contact(contact_id: str) -> Optional[Contact]:
    if "contacts" not in _cache:
        get_contacts()
    return _cache.get("contacts", {}).get(contact_id)
