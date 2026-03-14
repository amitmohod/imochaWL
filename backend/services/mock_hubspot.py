"""
Synthetic CRM data generator for iMocha Win/Loss Intelligence.

Two product lines:
  - Talent Acquisition (TA): Skills Assessment, AI Interview (Tara), Coding Sims, EnglishPro
  - Skills Intelligence (SI): Skills Intelligence Cloud, Skills Analytics, Workforce Planning
  - Full Platform: Bundled TA + SI

Embedded discoverable patterns:
- Vertical: IT Services (65% win), BFSI (58%) vs Manufacturing (25%), Retail (30%)
- Deal size: $30K-$80K = 62% win, >$200K = 22%
- TA Competitors: HackerRank (25% win), Mercer Mettl (60% win)
- SI Competitors: Eightfold AI (28% win), Lightcast (55% win)
- Product line: Full Platform = 65%, TA only = 48%, SI only = 38%
- Source: Customer Referral 72%, G2 55%, Outbound SDR 28%
- Company size: 2000-10000 emp = 60%+, <500 = 30%
- TA Buyer: VP TA/Head Recruitment = 62%, TA Manager = 28%
- SI Buyer: CHRO/CPO = 60%, Head L&D = 35%
- Cycle: Won avg ~38 days, Lost avg ~72 days
"""

import random
from typing import List, Optional, Set
from datetime import datetime, timedelta
from models.hubspot import Company, Contact, Deal, ConversationSignal

# Global data store
_companies: List[Company] = []
_contacts: List[Contact] = []
_deals: List[Deal] = []
_generated = False

# --- VERTICALS ---
INDUSTRIES = ["IT Services", "BFSI", "Product/SaaS", "Healthcare", "Retail/E-commerce", "Manufacturing"]
INDUSTRY_WIN_RATES = {
    "IT Services": 0.65, "BFSI": 0.58, "Product/SaaS": 0.52,
    "Healthcare": 0.42, "Retail/E-commerce": 0.30, "Manufacturing": 0.25,
}
INDUSTRY_WEIGHTS = [28, 22, 18, 12, 10, 10]

# --- PRODUCT LINES ---
PRODUCT_LINES = ["TA", "Skills Intelligence", "Full Platform"]
PRODUCT_LINE_WIN_RATES = {"TA": 0.48, "Skills Intelligence": 0.38, "Full Platform": 0.65}
PRODUCT_LINE_WEIGHTS = [45, 25, 30]

PRODUCT_NAMES = {
    "TA": [
        "Skills Assessment Platform", "AI Interview Agent (Tara)",
        "Coding Simulation Suite", "AI-EnglishPro", "TA Assessment Bundle",
    ],
    "Skills Intelligence": [
        "Skills Intelligence Cloud", "Skills Analytics Suite",
        "Workforce Planning Module", "Skills Data Enrichment",
    ],
    "Full Platform": [
        "iMocha Full Platform", "Enterprise Skills Suite",
        "TA + Skills Intelligence Bundle",
    ],
}

# --- DEAL SOURCES ---
DEAL_SOURCES = ["Customer Referral", "Inbound (Content/SEO)", "Outbound SDR", "Partner/SI", "HR Tech Conference", "G2/Marketplace"]
SOURCE_WIN_RATES = {
    "Customer Referral": 0.72, "Inbound (Content/SEO)": 0.48,
    "Outbound SDR": 0.28, "Partner/SI": 0.55,
    "HR Tech Conference": 0.45, "G2/Marketplace": 0.55,
}
SOURCE_WEIGHTS = [12, 25, 22, 12, 12, 17]

# --- COMPETITORS (by product line) ---
TA_COMPETITORS = [None, "HackerRank", "Codility", "HireVue", "TestGorilla", "Mercer Mettl"]
TA_COMPETITOR_WIN_RATES = {
    None: 0.62, "HackerRank": 0.25, "Codility": 0.42,
    "HireVue": 0.38, "TestGorilla": 0.52, "Mercer Mettl": 0.60,
}
TA_COMPETITOR_WEIGHTS = [25, 22, 14, 13, 12, 14]

SI_COMPETITORS = [None, "Eightfold AI", "Gloat", "Lightcast", "SkyHive"]
SI_COMPETITOR_WIN_RATES = {
    None: 0.58, "Eightfold AI": 0.28, "Gloat": 0.35,
    "Lightcast": 0.55, "SkyHive": 0.48,
}
SI_COMPETITOR_WEIGHTS = [30, 25, 18, 15, 12]

# --- BUYER PERSONAS ---
TA_SENIORITY_WIN_RATES = {
    "C-Level": 0.58, "VP": 0.62, "Director": 0.52, "Manager": 0.28,
}
SI_SENIORITY_WIN_RATES = {
    "C-Level": 0.60, "VP": 0.55, "Director": 0.42, "Manager": 0.35,
}

TA_TITLES_BY_SENIORITY = {
    "C-Level": ["CHRO", "CTO", "CPO"],
    "VP": ["VP Talent Acquisition", "VP Recruitment", "VP People Operations"],
    "Director": ["Director TA", "Director Recruitment", "Director HR Technology"],
    "Manager": ["TA Manager", "Recruitment Manager", "HR Technology Manager"],
}
SI_TITLES_BY_SENIORITY = {
    "C-Level": ["CHRO", "Chief People Officer", "CTO"],
    "VP": ["VP HR Strategy", "VP People Analytics", "VP Workforce Planning"],
    "Director": ["Director L&D", "Director People Analytics", "Director Workforce Planning"],
    "Manager": ["Head of L&D", "People Analytics Manager", "HR Systems Manager"],
}

# --- LOSS REASONS ---
TA_LOSS_REASONS = [
    "Chose cheaper point solution", "Went with incumbent vendor",
    "Only needed coding - not full platform", "ATS integration gap",
    "Budget freeze - hiring slowdown", "Procurement delays",
    "No AI interview need", "Chose competitor's brand",
]
SI_LOSS_REASONS = [
    "Chose Eightfold/competitor", "Not ready for skills transformation",
    "HCM vendor bundled skills module", "Budget allocated elsewhere",
    "Complexity concerns", "Procurement delays",
    "Chose to build in-house", "No executive sponsor",
]

# --- OBJECTIONS ---
TA_OBJECTIONS = [
    "Pricing per-candidate too high", "Already using HackerRank/competitor",
    "Need deeper ATS integration", "Concerned about AI bias in hiring",
    "Only need coding assessments", "Proctoring not enterprise-grade enough",
    "Implementation timeline too long", "Need more language support",
    "Candidate experience concerns", "ROI unclear vs current process",
]
SI_OBJECTIONS = [
    "Skills taxonomy too complex", "Integration gap with Workday/SAP",
    "Already invested in Eightfold", "Need proof of ROI first",
    "Data privacy concerns", "Change management too heavy",
    "Not ready for skills-first model", "Need internal mobility features",
    "Concerned about adoption rates", "Budget not allocated for SI",
]

# --- COMPANY NAMES ---
COMPANY_PREFIXES = [
    "Infosys", "Wipro", "TCS", "HCL", "Cognizant", "Tech Mahindra",
    "Capgemini", "Accenture", "Deloitte", "EY", "KPMG", "PwC",
    "HDFC", "ICICI", "Axis", "Kotak", "Bajaj", "Reliance",
    "Freshworks", "Zoho", "Razorpay", "Chargebee", "Postman", "BrowserStack",
    "Apollo", "Fortis", "Max", "Medanta", "Narayana", "Manipal",
    "Flipkart", "Myntra", "Nykaa", "BigBasket", "Swiggy", "Zomato",
    "Tata Steel", "JSW", "Mahindra", "Godrej", "Larsen", "Adani",
    "JP Morgan", "Goldman", "Morgan Stanley", "Barclays", "HSBC", "Citi",
    "Salesforce", "Adobe", "Microsoft", "Google", "Amazon", "Meta",
    "Lenskart", "PhonePe", "CRED", "Meesho", "Ola", "Uber",
]

INDUSTRY_SUFFIXES = {
    "IT Services": ["Digital", "Technologies", "Solutions", "Consulting", "Tech"],
    "BFSI": ["Financial", "Bank", "Insurance", "Capital", "Securities"],
    "Product/SaaS": ["Labs", "Software", "Platform", "Cloud", "Inc"],
    "Healthcare": ["Health", "Hospitals", "Medical", "Care", "Therapeutics"],
    "Retail/E-commerce": ["Retail", "Commerce", "Brands", "Marketplace", "Direct"],
    "Manufacturing": ["Industries", "Manufacturing", "Engineering", "Works", "Corp"],
}

SALES_REPS = [
    "Ravi Mehta", "Priya Kapoor", "Aditya Sharma", "Neha Reddy",
    "Jason Park", "Sarah Mitchell", "Vikram Desai", "Emily Chen",
]


def _generate_win_reason(source: str, product_line: str, seniority: str, competitor: Optional[str]) -> str:
    """Derive a win reason from deal characteristics."""
    reasons = []
    if source == "Customer Referral":
        reasons.append("Strong customer reference sold the deal")
    if seniority in ("C-Level", "VP"):
        reasons.append("Executive sponsor drove fast decision")
    if product_line == "Full Platform":
        reasons.append("Consolidated platform value over point solutions")
    if competitor == "Mercer Mettl":
        reasons.append("Superior AI proctoring beat incumbent")
    elif competitor == "Lightcast":
        reasons.append("Deeper skills taxonomy won evaluation")
    elif competitor == "TestGorilla":
        reasons.append("Enterprise-grade security and compliance")
    elif competitor == "HackerRank":
        reasons.append("Broader assessment coverage beyond coding")
    elif competitor == "Eightfold AI":
        reasons.append("Better ROI on skills intelligence investment")
    elif competitor is None:
        reasons.append("No competitive alternative — greenfield win")
    if source in ("G2/Marketplace", "Inbound (Content/SEO)"):
        reasons.append("Product-led momentum from self-serve trial")
    if product_line == "TA":
        reasons.append("AI Interview Agent (Tara) differentiation")
    if product_line == "Skills Intelligence":
        reasons.append("Skills analytics depth unmatched in market")
    return random.choice(reasons) if reasons else "Strong product-market fit"


CITIES = [
    ("Bangalore", "KA"), ("Mumbai", "MH"), ("Hyderabad", "TG"), ("Pune", "MH"),
    ("Chennai", "TN"), ("Delhi NCR", "DL"), ("Gurugram", "HR"), ("Noida", "UP"),
    ("San Francisco", "CA"), ("New York", "NY"), ("London", "UK"), ("Singapore", "SG"),
]

FIRST_NAMES = [
    "Amit", "Priya", "Rahul", "Sneha", "Vikram", "Anita", "Rajesh", "Kavita",
    "Suresh", "Meera", "Deepak", "Pooja", "Arun", "Nisha", "Sanjay", "Ritu",
    "James", "Sarah", "Michael", "Emily", "David", "Jessica", "Robert", "Amanda",
    "Chris", "Lisa", "Andrew", "Rachel", "Mark", "Jennifer", "Kevin", "Rebecca",
]

LAST_NAMES = [
    "Sharma", "Patel", "Kumar", "Singh", "Gupta", "Reddy", "Nair", "Joshi",
    "Iyer", "Menon", "Desai", "Shah", "Rao", "Verma", "Chopra", "Malhotra",
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Chen", "Kim", "Thompson", "Anderson", "Taylor", "Moore", "Wilson", "Lee",
]


def _employee_count_for_pattern(industry: str) -> int:
    """Generate employee counts. Sweet spot: 2000-10000 for iMocha."""
    if industry in ("IT Services", "BFSI"):
        return random.choice([
            random.randint(2000, 10000),
            random.randint(2000, 10000),
            random.randint(2000, 10000),
            random.randint(10001, 50000),
            random.randint(500, 1999),
        ])
    elif industry in ("Product/SaaS",):
        return random.choice([
            random.randint(200, 1000),
            random.randint(500, 2000),
            random.randint(1000, 5000),
            random.randint(2000, 10000),
        ])
    elif industry in ("Manufacturing", "Retail/E-commerce"):
        return random.choice([
            random.randint(5000, 20000),
            random.randint(10000, 50000),
            random.randint(1000, 5000),
            random.randint(500, 2000),
        ])
    else:
        return random.choice([
            random.randint(1000, 5000),
            random.randint(2000, 10000),
            random.randint(500, 3000),
        ])


def _deal_amount(product_line: str) -> float:
    """Generate deal amounts based on product line."""
    if product_line == "Full Platform":
        bucket = random.choices(
            ["medium", "sweet", "large", "enterprise"],
            weights=[15, 35, 30, 20],
        )[0]
    elif product_line == "Skills Intelligence":
        bucket = random.choices(
            ["small", "sweet", "medium", "large"],
            weights=[10, 35, 35, 20],
        )[0]
    else:  # TA
        bucket = random.choices(
            ["small", "sweet", "medium", "large"],
            weights=[20, 40, 25, 15],
        )[0]

    if bucket == "small":
        return round(random.uniform(10000, 29999), -2)
    elif bucket == "sweet":
        return round(random.uniform(30000, 80000), -2)
    elif bucket == "medium":
        return round(random.uniform(80001, 200000), -2)
    elif bucket == "large":
        return round(random.uniform(200001, 400000), -2)
    else:  # enterprise
        return round(random.uniform(300001, 800000), -2)


def _compute_win_probability(
    industry: str, amount: float, source: str,
    competitor: Optional[str], seniority: str,
    employee_count: int, product_line: str,
) -> float:
    """Combine all pattern factors into a single win probability."""
    base = INDUSTRY_WIN_RATES[industry]

    # Product line modifier
    pl_mod = (PRODUCT_LINE_WIN_RATES[product_line] - 0.48) * 0.5

    # Deal size modifier
    if 30000 <= amount <= 80000:
        size_mod = 0.10
    elif amount < 30000:
        size_mod = -0.02
    elif amount <= 200000:
        size_mod = -0.05
    else:
        size_mod = -0.22

    # Source modifier
    source_mod = (SOURCE_WIN_RATES[source] - 0.45) * 0.5

    # Competitor modifier
    if product_line in ("TA", "Full Platform"):
        comp_rate = TA_COMPETITOR_WIN_RATES.get(competitor, 0.45)
    else:
        comp_rate = SI_COMPETITOR_WIN_RATES.get(competitor, 0.45)
    comp_mod = (comp_rate - 0.45) * 0.4

    # Seniority modifier
    if product_line in ("TA", "Full Platform"):
        sen_rate = TA_SENIORITY_WIN_RATES.get(seniority, 0.40)
    else:
        sen_rate = SI_SENIORITY_WIN_RATES.get(seniority, 0.40)
    sen_mod = (sen_rate - 0.45) * 0.4

    # Company size modifier (sweet spot 2000-10000)
    if 2000 <= employee_count <= 10000:
        emp_mod = 0.08
    elif 500 <= employee_count < 2000:
        emp_mod = 0.0
    elif employee_count < 500:
        emp_mod = -0.12
    else:
        emp_mod = -0.05

    prob = base + pl_mod + size_mod + source_mod + comp_mod + sen_mod + emp_mod
    prob += random.uniform(-0.08, 0.08)
    return max(0.05, min(0.95, prob))


# --- CONVERSATION SIGNAL TEMPLATES ---
SIGNAL_TEMPLATES = {
    "Pricing": {
        "negative": [
            "Your per-candidate pricing is 3x what we pay now",
            "At this price point, we can't justify the switch from our current tool",
            "We need volume discounts — $12 per assessment doesn't scale for 10K hires",
            "The ROI math doesn't work unless you can bring the per-seat cost down 40%",
            "Finance flagged the annual cost as 2x our current budget for assessments",
        ],
        "neutral": [
            "We're comparing pricing models across three vendors right now",
            "The pricing is in the range we expected for an enterprise platform",
        ],
        "positive": [
            "The per-candidate model actually works better for our seasonal hiring",
            "Compared to the cost of a bad hire, this is very reasonable",
        ],
    },
    "Product Gap": {
        "negative": [
            "We need deeper ATS integration with Greenhouse",
            "Without video interview recording, we can't replace HireVue",
            "The skills taxonomy doesn't cover our niche engineering roles",
            "We need custom assessment builders — the templates are too rigid",
            "No support for our compliance requirements in healthcare hiring",
        ],
        "neutral": [
            "The product roadmap looks promising, especially the AI interviewer",
            "We'd want to see the Workday integration before committing",
        ],
        "positive": [
            "The AI proctoring feature is ahead of anything else we've seen",
            "Your skills intelligence layer is genuinely differentiated",
        ],
    },
    "Integration": {
        "negative": [
            "If it doesn't connect to Workday, it's a non-starter for us",
            "We need native Greenhouse integration — Zapier workarounds won't fly",
            "Our IT team said the SSO setup looked more complex than competitors",
            "The API rate limits are a problem for our high-volume use case",
        ],
        "neutral": [
            "We're evaluating how the platform fits into our existing HR tech stack",
            "The REST API looks solid, we'd just need to validate the webhook support",
        ],
        "positive": [
            "The SAP SuccessFactors integration was seamless in our POC",
            "Having native Slack notifications for hiring managers is a nice touch",
        ],
    },
    "Requirement Mismatch": {
        "negative": [
            "We only need coding assessments, not the full platform",
            "This is overkill for what we need — we're a 50-person startup",
            "We're looking for a point solution, not an enterprise suite",
            "The skills intelligence piece isn't relevant — we just need TA",
            "We don't need AI interviews, just simple skills tests",
        ],
        "neutral": [
            "Let us revisit once we've scaled to the point where we need the full platform",
            "We might need this next year, but right now it's more than we need",
        ],
        "positive": [
            "Actually, the bundled approach saves us from managing three vendors",
        ],
    },
    "Champion Risk": {
        "negative": [
            "Our VP of TA just left, new one wants to re-evaluate everything",
            "The hiring freeze means our champion can't push this through procurement",
            "Our CHRO is leaving in Q2, the new one will have different priorities",
            "The project sponsor moved to a different business unit last month",
        ],
        "neutral": [
            "We need to get the new VP aligned before we can move forward",
            "There's a leadership transition happening, but our Director is still supportive",
        ],
        "positive": [
            "Our CHRO is personally championing this — it's a board-level priority",
        ],
    },
    "Competitive Pressure": {
        "negative": [
            "HackerRank already offered us a 40% discount to renew",
            "Eightfold gave us a free pilot and their AI matching is impressive",
            "Codility is bundling proctoring for free — hard to compete with that",
            "TestGorilla is half the price and covers 80% of what we need",
            "Our current vendor just launched the exact features we asked you about",
        ],
        "neutral": [
            "We're running parallel evaluations with two other vendors",
            "The competitive landscape is crowded — we need to see clear differentiation",
        ],
        "positive": [
            "None of the competitors have the skills intelligence depth you offer",
            "Your AI interview agent is genuinely unique in the market",
        ],
    },
}

# Map loss reasons / objections to likely conversation signal themes
LOSS_REASON_THEME_MAP = {
    "Chose cheaper point solution": ["Pricing", "Requirement Mismatch"],
    "Went with incumbent vendor": ["Competitive Pressure", "Champion Risk"],
    "Only needed coding - not full platform": ["Requirement Mismatch", "Pricing"],
    "ATS integration gap": ["Integration", "Product Gap"],
    "Budget freeze - hiring slowdown": ["Pricing", "Champion Risk"],
    "Procurement delays": ["Champion Risk", "Pricing"],
    "No AI interview need": ["Requirement Mismatch"],
    "Chose competitor's brand": ["Competitive Pressure", "Product Gap"],
    "Chose Eightfold/competitor": ["Competitive Pressure", "Product Gap"],
    "Not ready for skills transformation": ["Requirement Mismatch", "Champion Risk"],
    "HCM vendor bundled skills module": ["Competitive Pressure", "Integration"],
    "Budget allocated elsewhere": ["Pricing", "Champion Risk"],
    "Complexity concerns": ["Product Gap", "Integration"],
    "Chose to build in-house": ["Competitive Pressure", "Requirement Mismatch"],
    "No executive sponsor": ["Champion Risk"],
}

OBJECTION_THEME_MAP = {
    "Pricing per-candidate too high": "Pricing",
    "Already using HackerRank/competitor": "Competitive Pressure",
    "Need deeper ATS integration": "Integration",
    "Concerned about AI bias in hiring": "Product Gap",
    "Only need coding assessments": "Requirement Mismatch",
    "Proctoring not enterprise-grade enough": "Product Gap",
    "Implementation timeline too long": "Integration",
    "Need more language support": "Product Gap",
    "Candidate experience concerns": "Product Gap",
    "ROI unclear vs current process": "Pricing",
    "Skills taxonomy too complex": "Product Gap",
    "Integration gap with Workday/SAP": "Integration",
    "Already invested in Eightfold": "Competitive Pressure",
    "Need proof of ROI first": "Pricing",
    "Data privacy concerns": "Product Gap",
    "Change management too heavy": "Requirement Mismatch",
    "Not ready for skills-first model": "Requirement Mismatch",
    "Need internal mobility features": "Product Gap",
    "Concerned about adoption rates": "Champion Risk",
    "Budget not allocated for SI": "Pricing",
}


def _generate_conversation_signals(deal_stage: str, loss_reason: Optional[str],
                                   objections: List[str], competitor: Optional[str]) -> List[ConversationSignal]:
    """Generate realistic conversation signals based on deal outcome and context."""
    signals = []  # type: List[ConversationSignal]

    # Determine which themes to pull from
    relevant_themes = set()  # type: Set[str]

    if loss_reason and loss_reason in LOSS_REASON_THEME_MAP:
        for theme in LOSS_REASON_THEME_MAP[loss_reason]:
            relevant_themes.add(theme)

    for obj in objections:
        if obj in OBJECTION_THEME_MAP:
            relevant_themes.add(OBJECTION_THEME_MAP[obj])

    # If competitor exists, always add Competitive Pressure
    if competitor:
        relevant_themes.add("Competitive Pressure")

    if deal_stage == "closedlost":
        # Lost deals: 2-4 signals, mostly negative
        if not relevant_themes:
            relevant_themes = set(random.sample(list(SIGNAL_TEMPLATES.keys()), 2))

        n_signals = random.randint(2, min(4, len(relevant_themes) + 1))
        theme_list = list(relevant_themes)
        random.shuffle(theme_list)

        for theme in theme_list[:n_signals]:
            templates = SIGNAL_TEMPLATES[theme]
            # 75% negative, 25% neutral for lost deals
            if random.random() < 0.75 and templates["negative"]:
                sentiment = "negative"
            else:
                sentiment = "neutral"
            quote = random.choice(templates[sentiment])
            source = random.choice(["Fireflies", "Fireflies", "HubSpot Notes"])  # 2:1 Fireflies bias
            signals.append(ConversationSignal(
                theme=theme, quote=quote, source=source, sentiment=sentiment
            ))
    else:
        # Won deals: 0-2 signals, mostly positive/neutral
        n_signals = random.choices([0, 1, 2], weights=[40, 40, 20])[0]
        if n_signals > 0:
            available_themes = list(relevant_themes) if relevant_themes else list(SIGNAL_TEMPLATES.keys())
            random.shuffle(available_themes)
            for theme in available_themes[:n_signals]:
                templates = SIGNAL_TEMPLATES[theme]
                # Won deals: 50% positive, 40% neutral, 10% negative
                roll = random.random()
                if roll < 0.5 and templates["positive"]:
                    sentiment = "positive"
                elif roll < 0.9:
                    sentiment = "neutral"
                else:
                    sentiment = "negative"
                quote = random.choice(templates[sentiment])
                source = random.choice(["Fireflies", "HubSpot Notes"])
                signals.append(ConversationSignal(
                    theme=theme, quote=quote, source=source, sentiment=sentiment
                ))

    return signals


def generate_data():
    global _companies, _contacts, _deals, _generated
    if _generated:
        return

    random.seed(42)

    # Generate 60 companies
    used_names: Set[str] = set()
    shuffled_prefixes = COMPANY_PREFIXES.copy()
    random.shuffle(shuffled_prefixes)

    for i in range(60):
        industry = random.choices(INDUSTRIES, weights=INDUSTRY_WEIGHTS)[0]
        prefix = shuffled_prefixes[i % len(shuffled_prefixes)]
        suffix = random.choice(INDUSTRY_SUFFIXES[industry])
        name = f"{prefix} {suffix}"
        if name in used_names:
            name = f"{prefix} {suffix} {random.choice(['Group', 'Global', 'India'])}"
        used_names.add(name)

        emp = _employee_count_for_pattern(industry)
        city, state = random.choice(CITIES)
        _companies.append(Company(
            id=f"comp_{i+1:03d}",
            name=name,
            industry=industry,
            employee_count=emp,
            annual_revenue=round(emp * random.uniform(80000, 250000), -3),
            website=f"https://www.{prefix.lower().replace(' ', '')}.com",
            city=city,
            state=state,
        ))

    # Generate contacts (2-4 per company)
    contact_idx = 0
    for comp in _companies:
        n_contacts = random.randint(2, 4)
        for _ in range(n_contacts):
            # Decide if TA or SI buyer
            is_ta_buyer = random.random() < 0.6
            seniority_rates = TA_SENIORITY_WIN_RATES if is_ta_buyer else SI_SENIORITY_WIN_RATES
            titles_map = TA_TITLES_BY_SENIORITY if is_ta_buyer else SI_TITLES_BY_SENIORITY

            seniority = random.choices(
                list(seniority_rates.keys()),
                weights=[10, 25, 30, 35],
            )[0]
            title = random.choice(titles_map[seniority])
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            _contacts.append(Contact(
                id=f"cont_{contact_idx+1:03d}",
                first_name=first,
                last_name=last,
                email=f"{first.lower()}.{last.lower()}@{comp.name.lower().replace(' ', '')}.com",
                title=title,
                seniority=seniority,
                company_id=comp.id,
            ))
            contact_idx += 1

    # Generate 175 deals
    for i in range(175):
        company = random.choice(_companies)
        company_contacts = [c for c in _contacts if c.company_id == company.id]
        contact = random.choice(company_contacts)

        industry = company.industry
        product_line = random.choices(PRODUCT_LINES, weights=PRODUCT_LINE_WEIGHTS)[0]
        source = random.choices(DEAL_SOURCES, weights=SOURCE_WEIGHTS)[0]

        # Pick competitor based on product line
        if product_line in ("TA", "Full Platform"):
            competitor = random.choices(TA_COMPETITORS, weights=TA_COMPETITOR_WEIGHTS)[0]
        else:
            competitor = random.choices(SI_COMPETITORS, weights=SI_COMPETITOR_WEIGHTS)[0]

        amount = _deal_amount(product_line)

        win_prob = _compute_win_probability(
            industry, amount, source, competitor, contact.seniority,
            company.employee_count, product_line,
        )
        won = random.random() < win_prob
        stage = "closedwon" if won else "closedlost"

        # Cycle length
        if won:
            base_cycle = 38 if product_line == "TA" else 52 if product_line == "Skills Intelligence" else 48
            cycle = max(14, int(random.gauss(base_cycle, 12)))
        else:
            base_cycle = 72 if product_line == "TA" else 85 if product_line == "Skills Intelligence" else 78
            cycle = max(20, int(random.gauss(base_cycle, 20)))

        close_date = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 364))
        create_date = close_date - timedelta(days=cycle)

        # Loss reason & objections
        loss_reason = None
        objections: List[str] = []
        loss_pool = TA_LOSS_REASONS if product_line in ("TA", "Full Platform") else SI_LOSS_REASONS
        obj_pool = TA_OBJECTIONS if product_line in ("TA", "Full Platform") else SI_OBJECTIONS

        if not won:
            loss_reason = random.choice(loss_pool)

        n_objections = random.choices([0, 1, 2, 3], weights=[20, 35, 30, 15] if won else [5, 25, 40, 30])[0]
        if n_objections > 0:
            objections = random.sample(obj_pool, min(n_objections, len(obj_pool)))

        # Win reason for won deals
        win_reason = None
        if won:
            win_reason = _generate_win_reason(source, product_line, contact.seniority, competitor)

        # Sales rep
        sales_rep = random.choice(SALES_REPS)

        # Deal name
        product_name = random.choice(PRODUCT_NAMES[product_line])
        deal_name = f"{company.name} - {product_name}"

        # Generate conversation signals
        conv_signals = _generate_conversation_signals(stage, loss_reason, objections, competitor)

        _deals.append(Deal(
            id=f"deal_{i+1:03d}",
            name=deal_name,
            stage=stage,
            amount=amount,
            close_date=close_date,
            create_date=create_date,
            pipeline="default",
            product_line=product_line,
            deal_source=source,
            loss_reason=loss_reason,
            win_reason=win_reason,
            competitor=competitor,
            sales_rep=sales_rep,
            company_id=company.id,
            contact_id=contact.id,
            cycle_days=cycle,
            objections=objections,
            conversation_signals=conv_signals,
        ))

    _generated = True


def get_companies() -> List[Company]:
    return _companies


def get_contacts() -> List[Contact]:
    return _contacts


def get_deals() -> List[Deal]:
    return _deals


def get_company(company_id: str) -> Optional[Company]:
    return next((c for c in _companies if c.id == company_id), None)


def get_contact(contact_id: str) -> Optional[Contact]:
    return next((c for c in _contacts if c.id == contact_id), None)


def get_deal(deal_id: str) -> Optional[Deal]:
    return next((d for d in _deals if d.id == deal_id), None)
