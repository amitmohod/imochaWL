# Win/Loss AI — Sales Intelligence Platform

AI-powered system that analyzes CRM deal data (won vs lost), discovers patterns, builds an Ideal Customer Profile, and provides strategic recommendations — with conversation evidence from call transcripts and CRM notes.

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- (Optional) Anthropic API key for live AI responses

### 1. Backend

```bash
cd backend
pip3 install -r requirements.txt
python3 -m uvicorn main:app --reload --port 8000
```

Backend runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard runs at `http://localhost:3000`.

### 3. AI Setup (Optional)

Create `backend/.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

Without an API key, the app uses built-in mock AI responses that match the data patterns — fully functional for demos.

---

## Page-by-Page UI Guide

### 1. Dashboard Overview (`/`)

The CEO-level intelligence page. All sections respond to filters.

#### Filter Bar
4 dropdown selects at the top:
- **Quarter** — All Quarters / Q1 2024 / Q2 2024 / Q3 2024 / Q4 2024
- **Industry** — All Industries / BFSI / Healthcare / IT Services / Manufacturing / Product/SaaS / Retail/E-commerce
- **Region** — All Regions / 12 cities
- **Sales Rep** — All Sales Reps / 8 individual reps
- **Clear filters** button appears when any filter is active

#### KPI Cards (4-column grid)
| Card | Primary Value | Health Color | Sub-Metric | Trend | Insight |
|------|--------------|-------------|------------|-------|---------|
| **Win Rate** | e.g. `48.6%` | Green (>=50%), Amber (>=35%), Red (<35%) | `84W / 91L` | `+3.2pp vs Q3` (quarter-over-quarter) | Best: IT Services (65%) / Worst: Manufacturing (25%) |
| **Total Revenue** | e.g. `$5.2M` | Red if lost > won, else Amber | `$4.8M lost` | `+12.5% vs Q3` | Top leak: $1.2M to Lightcast (8 deals) |
| **Avg Deal Size** | e.g. `$62K` | Green if sweet spot WR >=55%, else Amber | `Sweet spot: $30K-$80K` | — | $30K-$80K wins at 67% / >$200K wins at only 22% |
| **Avg Cycle** | e.g. `38d` | Red (drag >25d), Amber (>15d), Green | `Won: 38d / Lost: 73d` | `+2.1d vs Q3` | Lost deals drag 35d longer — early kill = freed capacity |

Each card has a colored top stripe (green/amber/red) indicating health status.

#### Strategic Signals (3-column grid)
3 color-coded signal cards:
| Card | Color | Headline | Metric | Detail |
|------|-------|----------|--------|--------|
| **Growth Lever** | Teal | "{Source} converts at {X}% but is only {Y}% of pipeline" | `{X}% win rate` | Identifies highest-win-rate source that's underrepresented. Suggests doubling investment. |
| **Revenue Leak** | Rose | "Lost ${X}M to {Competitor} across {N} deals" | `${X}M lost` | Biggest competitor by revenue impact. Links to battlecard review. |
| **ICP Fit** | Blue | "Only {X}% of pipeline matches ICP" | `{ICP WR}% vs {non-ICP WR}%` | Shows ICP vs non-ICP win rate gap. Quantifies potential pp lift from tighter qualification. |

#### Conversation Signals (3-column grid)
One card per conversation theme extracted from Fireflies transcripts and HubSpot notes. Each card shows:
- **Theme icon + name** — e.g. Pricing ($), Product Gap (P), Integration (I), Requirement Mismatch (R), Champion Risk (C), Competitive Pressure (V)
- **Impact badge** — High (rose), Medium (amber), Low (green) — based on how much win rate drops vs overall when this theme appears
- **Frequency** — e.g. "42 deals (24%)"
- **Win rate when raised** — color-coded (green >50%, amber >30%, rose <30%)
- **Sample quote** — italic quote from an actual deal conversation, with source attribution ("via Fireflies" / "via HubSpot Notes")

#### Charts Row (2-column grid)
| Left: Win Rate by Industry | Right: Win/Loss Reasons |
|---------------------------|------------------------|
| Vertical bar chart (Recharts) | Two side-by-side donut charts |
| Each bar color-coded per industry | **Top Win Reasons** (teal heading) — donut with legend showing reason name + count |
| X-axis: industry names, Y-axis: percentage | **Top Loss Reasons** (rose heading) — donut with legend showing reason name + count |
| Tooltip shows exact win rate % | Both use the same 6-color palette |

#### AI Executive Summary
Expandable card (default expanded) with markdown-rendered AI analysis of overall win/loss trends, key insights, and recommendations. Powered by Claude or mock fallback.

#### Recent Deals Table
Scrollable table showing the 8 most recent deals:
| Column | Content |
|--------|---------|
| Deal | Deal name (truncated) |
| Company | Company name |
| Amount | e.g. `$45K` |
| Status | Won (teal badge) / Lost (rose badge) |
| Source | Deal source channel |
| Reason | Win reason or loss reason |
| Cycle | e.g. `34d` |

---

### 2. Win/Loss Analysis (`/win-loss`)

Deep-dive dimensional analysis with pattern discovery.

#### Filter Bar
Same 4 dropdowns as Dashboard (Quarter, Industry, Region, Sales Rep) + Clear button. Filters apply to the breakdown chart/table and pattern discovery.

#### Dimension Tabs
Pill-style tab bar with 6 tabs:
- **Industry** | **Deal Size** | **Source** | **Company Size** | **Buyer Title** | **Geography**

Selecting a tab reloads the chart and table for that dimension.

#### Breakdown Section (2-column grid)

| Left: Horizontal Bar Chart | Right: Detailed Breakdown Table |
|---------------------------|-------------------------------|
| Horizontal bars showing win rate per category | Sorted table (highest win rate first) |
| Color-coded bars (6-color rotating palette) | **Category** — dimension value |
| **LabelList** — percentage labels on each bar (e.g. `65%`) | **Win Rate** — progress bar + percentage |
| Y-axis: category names, X-axis: 0-100% | **W/L** — e.g. `12W / 5L` |
| Dynamic height based on number of categories | **Revenue** — e.g. `$340K` |
| Tooltip with exact win rate on hover | |

#### AI Win/Loss Analysis
Expandable card with AI-generated analysis of win/loss patterns. Uses the `win-loss-summary` insight prompt.

#### Pattern Discovery with Conversation Evidence (2-column grid)
7 pattern cards, each showing:

| Element | Description |
|---------|-------------|
| **Category badge** | Icon + uppercase label (e.g. "INDUSTRY", "DEAL SIZE", "SALES CYCLE") |
| **Color theme** | Teal (Industry, ICP), Blue (Deal Size), Amber (Sales Cycle), Rose (Competitor, Positioning), Purple (Objection) |
| **Stat value** | Key metric (e.g. "65% WR", "+35d", "86.4%") displayed in category color |
| **Title** | Descriptive headline (e.g. "Product/SaaS leads, Retail/E-commerce struggles") |
| **Description** | 2-3 sentence explanation with specific numbers |
| **Evidence quotes** (2-3) | Each quote box contains: italic quote text, sentiment dot (rose=negative, amber=neutral, teal=positive), deal name, source ("via Fireflies"/"via HubSpot Notes"), Won/Lost badge |
| **Recommendation** | Actionable next step with bold "Recommendation:" prefix |

The 7 pattern categories:
1. **Industry** — Best vs worst verticals, evidence from lost deals in worst vertical
2. **Deal Size** — Sweet spot ($30K-$80K) vs large deal (>$150K) drop-off, pricing/requirement signals
3. **Sales Cycle** — Won vs lost cycle drag, champion risk/procurement signals from slow lost deals
4. **Competitor** — Hardest competitor by win rate, competitive pressure quotes
5. **Objection** — Most damaging objection, negative sentiment signals
6. **ICP Refinement** — ICP vs non-ICP win rate gap, requirement mismatch signals
7. **Positioning Gap** — Deals with product gap/requirement mismatch themes, negative quotes

#### All Deals Table
Scrollable table (max 50 rows, 400px height) with stage filter tabs:
- **All** | **Won** | **Lost** (pill toggle in table header)

| Column | Content |
|--------|---------|
| Deal | Deal name (truncated) |
| Amount | e.g. `$62K` |
| Status | Won (teal badge) / Lost (rose badge) |
| Source | Deal source channel |
| Competitor | Competitor name or em-dash |
| Cycle | e.g. `45d` |
| Loss Reason | Reason text or em-dash |

---

### 3. ICP Builder (`/icp`)

Data-driven Ideal Customer Profile with AI recommendations.

#### Two-Column Grid

| Left: Data-Driven ICP | Right: Disqualification Criteria |
|-----------------------|-------------------------------|
| Computed from winning deal patterns | Rules derived from data patterns |

**Data-Driven ICP Card:**
- Confidence badge (e.g. "82% confidence") in teal
- 7 fields, each in a styled row:
  - Target Industries (highlighted teal background)
  - Company Size (highlighted teal background)
  - Deal Size Sweet Spot (highlighted teal background)
  - Buyer Personas
  - Best Channels
  - Avg Sales Cycle
  - Overall Win Rate

**Disqualification Criteria Card:**
- 6 DQ rules, each color-coded by severity:
  - **HIGH** (rose) — e.g. "Manufacturing or Retail companies with 1000+ employees"
  - **MEDIUM** (amber) — e.g. "Outbound-sourced deal with Manager-level contact only"
  - **LOW** (stone) — e.g. "No allocated budget (exploratory only)"
- **Lead Scoring** section at the bottom:
  - A-Lead (teal dot) — ICP match + Referral + VP+ buyer → 80%+
  - B-Lead (blue dot) — Right industry OR right size + decent source → 50-80%
  - C-Lead (amber dot) — Mixed signals, one strong factor → 30-50%
  - D-Lead (rose dot) — Multiple red flags, deprioritize → <30%

#### AI-Generated Ideal Customer Profile
Expandable card (default expanded) with AI-written ICP narrative based on data patterns.

#### AI Positioning Recommendations
Expandable card (collapsed by default) with AI-written messaging and pricing positioning strategy.

---

### 4. Competitor Intelligence (`/competitors`)

Head-to-head performance analysis.

#### Competitor Heatmap Table
Color-coded table where cells are highlighted by performance:

| Column | Color Logic |
|--------|-------------|
| Competitor | Name (clickable to expand detail card) |
| Threat | HIGH (rose) if WR <35%, MEDIUM (amber) if <50%, LOW (teal) if >=50% |
| Our Win Rate | Teal badge >=50%, Amber >=35%, Rose <35% |
| Deals Faced | Rose >=35, Amber >=25, Stone <25 |
| Avg Deal Size | Plain text (e.g. `$58K`) |
| Top Loss Reasons | Pill badges per reason |
| Industries | Blue pill badges per industry (max 3 shown) |

#### Competitor Detail Card (click to expand)
Appears below the table when a row is clicked:
- Competitor name + threat badge + "N deals encountered"
- 3-column layout:
  - **Head-to-Head Record** — stacked progress bar (teal=wins, rose=losses) with `12W (55%)` / `10L (45%)` labels
  - **Why We Lose** — list of loss reasons as rose-colored pills
  - **Active Industries** — list of industries as blue pills

#### AI Competitive Intelligence Briefing
Expandable card (default expanded) with AI-written competitive analysis, battlecard content, and strategies per competitor.

---

### 5. Objection Analysis (`/objections`)

Common objections and their impact.

#### Two-Column Grid

| Left: Objection Frequency Chart | Right: Win Rate Impact Table |
|-------------------------------|---------------------------|
| Horizontal bar chart | Detailed impact table |

**Objection Frequency Chart:**
- Horizontal bars, one per objection
- Y-axis: objection names (130px wide), X-axis: count
- Color-coded bars (10-color palette)
- Tooltip on hover

**Win Rate Impact Table:**
| Column | Content |
|--------|---------|
| Objection | Objection text |
| Count | Frequency number |
| Win Rate | Mini progress bar + percentage — teal >40%, amber >25%, rose <25% |
| Industries | Stone pill badges (max 3 shown, +N for overflow) |

#### AI Objection Handling Guide & Sales Scripts
Expandable card (default expanded) with AI-generated objection handling playbooks, talk tracks, and scripts for each common objection.

---

### 6. Ask AI (`/ask`)

Data-driven conversational interface. Answers are computed from real HubSpot deal data, Fireflies transcript signals, and analytics — not static text.

#### Empty State
When no messages exist:
- Teal chat icon
- "What would you like to know?" heading
- "Ask me anything about your 175 CRM deals" subtext
- **6 suggested question buttons** in a 2-column grid:
  - "What's our win rate against HackerRank?"
  - "Which industries should we stop pursuing?"
  - "How do our sales reps compare in performance?"
  - "What are customers saying about pricing in calls?"
  - "Which product line performs best and why?"
  - "What does our ideal customer profile look like?"

#### Chat Interface
- **User messages** — teal bubbles, right-aligned
- **AI responses** — white bordered bubbles, left-aligned, with markdown rendering (bold, italic, code, lists, headings, tables)
- **Loading indicator** — 3 bouncing teal dots
- **Input bar** — text input + Send button at the bottom, fixed position

#### Smart Topic Detection (15 Topics)
Questions are matched to topics via keyword detection, and responses are built from live data:

| Topic | Example Questions | Data Source |
|-------|-------------------|-------------|
| **deals** | "List 3 latest deals", "Show biggest won deals" | `get_deals()` — actual deal records with company, amount, status, source, competitor, cycle, reason |
| **competitor** | "Win rate against HackerRank?", "Competitor landscape" | `compute_competitors()` + deal conversation signals |
| **industry** | "Which industries to stop pursuing?" | `compute_breakdown("industry")` |
| **deal_size** | "What's our sweet spot?", "Pricing analysis" | `compute_breakdown("deal_size")` |
| **source** | "How do referrals perform?", "Best channels" | `compute_breakdown("source")` |
| **cycle** | "How long do deals take?", "Why are lost deals slow?" | `compute_overview()` + slow-deal conversation signals |
| **objection** | "What objections hurt most?" | `compute_objections()` |
| **icp** | "What's our ideal customer profile?" | `compute_icp()` + ICP-fit gap calculation |
| **sales_rep** | "How do reps compare?", "Top performer" | Deal aggregation per rep (win rate, revenue, avg deal, cycle) |
| **geography** | "Best performing cities?" | `compute_breakdown("geography")` |
| **conversation** | "What are buyers saying about pricing?" | Deal conversation signal aggregation with quotes |
| **product_line** | "Which product line performs best?" | Deal aggregation per product line (TA, Skills Intelligence, Full Platform) |
| **loss** | "Why are we losing?", "Top weaknesses" | Lost deal aggregation with reasons + buyer quotes |
| **win** | "What are our strengths?" | Won deal aggregation with reasons + source breakdown |
| **general** | "How are we doing?", "Pipeline overview" | `compute_overview()` + cross-dimension top insights |

Multi-topic questions (e.g., "Compare our industry performance and competitor landscape") return combined responses for up to 2 topics.

---

## AI System Architecture

The AI layer (`backend/services/claude_ai.py`) operates in two modes:

### With API Key (Claude Mode)
- Sends a comprehensive **15-section data context** to Claude with every prompt
- Context includes: dataset summary, breakdowns by 7 dimensions (industry, deal size, source, company size, buyer title, geography, product line), sales rep performance, competitor analysis, objections, ICP, conversation signal themes with quotes, and sample recent deals
- 7 prompt templates for structured insights (executive summary, ICP, competitors, positioning, industry loss, sales scripts, free-form ask)
- `ask_ai` prompts include iMocha product context and instruct Claude to cite numbers and conversation quotes
- Responses are cached per prompt type (except `ask_ai` which stays fresh)

### Without API Key (Smart Mock Mode)
- **Not static/hardcoded** — mock responses are computed from live synthetic data
- Topic detection via keyword matching on the user's question (15 topics supported)
- Per-topic handler functions query the same analytics functions used by the rest of the app
- Responses include real numbers, markdown tables, conversation signal quotes, and actionable recommendations
- Multi-topic support: complex questions can trigger up to 2 topic handlers with combined output

### Data Context Sections (passed to Claude)
1. Dataset Summary (totals, win rate, revenue, cycle times)
2. Win Rate by Industry
3. Win Rate by Deal Size
4. Win Rate by Source
5. Win Rate by Company Size
6. Win Rate by Buyer Seniority
7. Win Rate by Geography
8. Win Rate by Product Line
9. Sales Rep Performance
10. Competitor Analysis
11. Top Objections
12. Current ICP
13. Conversation Signal Themes (with sample quotes, sentiment, source)
14. Sample Recent Won Deals (5)
15. Sample Recent Lost Deals (5)

---

## Tech Stack

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, Recharts, SWR
- **Backend**: Python FastAPI
- **AI**: Claude API (Sonnet 4.5) with smart mock fallback (data-driven, not static)
- **Data**: In-memory synthetic data (175 deals, 60 companies, 12 cities, conversation signals)

## Synthetic Data Patterns

The dataset has embedded discoverable patterns:

| Pattern | Detail |
|---------|--------|
| Industry sweet spot | IT Services 65%, BFSI 58%, Product/SaaS 52% vs Manufacturing 25%, Retail 30% |
| Deal size sweet spot | $30K-$80K wins at ~67%, >$150K drops significantly |
| Competitor nemesis | Lightcast 25% WR (hardest), HackerRank tough; Mercer Mettl easiest |
| Source quality | Customer Referral ~72% win, G2 55%, Outbound SDR ~28% |
| Company size | 2,000-10,000 employees = 60%+, <500 = ~30% |
| Buyer level | VP/CHRO/CPO = 60%+, Manager/Head L&D = 28-35% |
| Cycle length | Won avg ~38 days, Lost avg ~72 days (+35 day drag) |
| Geography | 12 cities; Delhi NCR & Gurugram highest WR (~84%), Hyderabad lower (~41%) |
| ICP gap | ICP-fit deals ~86% WR vs non-ICP ~47% (39pp gap) |

## API Endpoints

### Analytics
- `GET /api/analytics/overview` — total deals, win rate, revenue, avg cycle
- `GET /api/analytics/breakdown/{dimension}` — industry, deal_size, source, company_size, buyer_title, geography (+ optional query params: quarter, industry, region, sales_rep)
- `GET /api/analytics/competitors` — per-competitor win rate, loss reasons, industries
- `GET /api/analytics/objections` — frequency, win rate impact, industry clustering
- `GET /api/analytics/icp` — computed ideal customer profile
- `GET /api/analytics/signals` — enhanced KPIs, growth lever, revenue leak, ICP fit, conversation themes, win/loss reasons (+ filter query params)
- `GET /api/analytics/filter-options` — quarters, industries, regions, sales reps for dropdown population
- `GET /api/analytics/patterns` — 7 pattern categories with conversation evidence quotes (+ filter query params)

### Deals
- `GET /api/deals?stage=&industry=&source=` — filterable, enriched with company/contact
- `GET /api/deals/recent?limit=10` — most recent deals

### AI Insights
- `GET /api/insights/win-loss-summary` — executive summary
- `GET /api/insights/icp` — AI-generated ICP
- `GET /api/insights/competitors` — competitive intelligence briefing
- `GET /api/insights/positioning` — messaging/pricing recommendations
- `GET /api/insights/industry-loss?industry=Manufacturing` — why we lose in specific industry
- `GET /api/insights/sales-scripts` — objection handling scripts
- `POST /api/insights/ask` — body: `{"question": "..."}`
