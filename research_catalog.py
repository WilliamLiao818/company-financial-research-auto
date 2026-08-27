from __future__ import annotations


COMPANY_NAMES = {
    "MSFT": "Microsoft Corporation",
    "ORCL": "Oracle Corporation",
    "GOOG": "Alphabet Inc.",
    "AVGO": "Broadcom Inc.",
    "SNDK": "Sandisk Corporation",
    "NVDA": "NVIDIA Corporation",
}


CIKS = {
    "MSFT": "0000789019",
    "ORCL": "0001341439",
    "GOOG": "0001652044",
    "AVGO": "0001730168",
    "SNDK": "0002023554",
    "NVDA": "0001045810",
}


def sec_filings_url(ticker: str, form: str) -> str:
    cik = CIKS[ticker]
    return f"https://www.sec.gov/edgar/browse/?CIK={cik}&owner=exclude&action=getcompany&type={form}"


TARGET_PRICE_SNAPSHOTS = {
    "MSFT": {
        "as_of": "2026-08-12",
        "source_url": "https://price-target.com/ai/microsoft/",
        "street": [
            {"firm": "Wells Fargo", "target": 700.0, "date": "2026-08-12"},
            {"firm": "Bernstein", "target": 660.0, "date": "2026-08-10"},
            {"firm": "Citi", "target": 600.0, "date": "2026-07-30"},
            {"firm": "UBS", "target": 525.0, "date": "2026-07-30"},
        ],
        "house": {"Bear": 450.0, "Base": 550.0, "Bull": 660.0},
        "basis": "A transparent range centered on the recent institutional cluster, with dispersion driven by Azure and AI monetization versus infrastructure-return risk.",
    },
    "ORCL": {
        "as_of": "2026-08-21",
        "source_url": "https://stockanalysis.com/stocks/orcl/forecast/",
        "street": [
            {"firm": "J.P. Morgan", "target": 200.0, "date": "2026-08-17"},
            {"firm": "RBC Capital", "target": 190.0, "date": "2026-08-12"},
            {"firm": "UBS", "target": 245.0, "date": "2026-08-06"},
        ],
        "house": {"Bear": 170.0, "Base": 245.0, "Bull": 320.0},
        "basis": "The range weighs OCI backlog conversion against capex, financing and deployment-timing risk; it is not a consensus average.",
    },
    "GOOG": {
        "as_of": "2026-08-24",
        "source_url": "https://stockanalysis.com/stocks/googl/forecast/",
        "street": [
            {"firm": "Citizens JMP", "target": 515.0, "date": "2026-08-24"},
            {"firm": "Bernstein", "target": 385.0, "date": "2026-08-20"},
            {"firm": "Evercore ISI", "target": 420.0, "date": "2026-07-23"},
            {"firm": "UBS", "target": 379.0, "date": "2026-07-23"},
        ],
        "house": {"Bear": 360.0, "Base": 430.0, "Bull": 515.0},
        "basis": "The range balances Search durability and Cloud acceleration against higher AI capex and the monetization gap between AI usage and advertising economics.",
    },
    "AVGO": {
        "as_of": "2026-08-21",
        "source_url": "https://stockanalysis.com/stocks/avgo/forecast/",
        "street": [
            {"firm": "Mizuho", "target": 530.0, "date": "2026-08-21"},
            {"firm": "Bank of America", "target": 530.0, "date": "2026-08-20"},
            {"firm": "Bernstein", "target": 550.0, "date": "2026-08-20"},
            {"firm": "BMO Capital", "target": 455.0, "date": "2026-08-20"},
        ],
        "house": {"Bear": 430.0, "Base": 525.0, "Bull": 590.0},
        "basis": "The range separates custom-accelerator and networking growth from customer concentration, ASIC margin pressure and software-integration risk.",
    },
    "SNDK": {
        "as_of": "2026-08-25",
        "source_url": "https://stockanalysis.com/stocks/sndk/forecast/",
        "street": [
            {"firm": "Mizuho", "target": 1875.0, "date": "2026-08-25"},
            {"firm": "Bernstein", "target": 3000.0, "date": "2026-08-17"},
            {"firm": "Goldman Sachs", "target": 2200.0, "date": "2026-08-14"},
            {"firm": "Wedbush", "target": 2000.0, "date": "2026-08-14"},
        ],
        "house": {"Bear": 1600.0, "Base": 2150.0, "Bull": 2900.0},
        "basis": "The range reflects NAND pricing and enterprise-SSD mix while keeping cycle normalization, supply response and customer concentration explicit.",
    },
    "NVDA": {
        "as_of": "2026-08-25",
        "source_url": "https://stockanalysis.com/stocks/nvda/forecast/",
        "street": [
            {"firm": "Raymond James", "target": 352.0, "date": "2026-08-25"},
            {"firm": "KeyBanc", "target": 330.0, "date": "2026-08-24"},
            {"firm": "Morgan Stanley", "target": 288.0, "date": "2026-08-14"},
        ],
        "house": {"Bear": 245.0, "Base": 305.0, "Bull": 355.0},
        "basis": "The range weighs Rubin and Blackwell demand visibility against growth deceleration, customer silicon substitution and multiple compression.",
    },
}


MARKET_SHARE_SNAPSHOTS = {
    "MSFT": {
        "title": "Global cloud infrastructure services",
        "period": "Q2 2026",
        "values": {"AWS": 28.0, "Microsoft": 20.0, "Google Cloud": 15.0, "Oracle and tier two": 5.0, "Other": 32.0},
        "source": "Synergy Research Group",
        "source_url": "https://www.srgresearch.com/articles/q2-cloud-market-passes-143-billion-highest-growth-rate-in-eight-years",
        "note": "The named tier-two share is a grouped visual estimate; use the source chart for exact vendor definitions.",
    },
    "ORCL": {
        "title": "Global cloud infrastructure services",
        "period": "Q2 2026",
        "values": {"AWS": 28.0, "Microsoft": 20.0, "Google Cloud": 15.0, "Oracle and tier two": 5.0, "Other": 32.0},
        "source": "Synergy Research Group",
        "source_url": "https://www.srgresearch.com/articles/q2-cloud-market-passes-143-billion-highest-growth-rate-in-eight-years",
        "note": "Oracle is shown inside a grouped tier-two estimate because the public release does not disclose a standalone percentage.",
    },
    "GOOG": {
        "title": "Global cloud infrastructure services",
        "period": "Q2 2026",
        "values": {"AWS": 28.0, "Microsoft": 20.0, "Google Cloud": 15.0, "Oracle and tier two": 5.0, "Other": 32.0},
        "source": "Synergy Research Group",
        "source_url": "https://www.srgresearch.com/articles/q2-cloud-market-passes-143-billion-highest-growth-rate-in-eight-years",
        "note": "Share is based on enterprise cloud infrastructure service revenue, not total company revenue.",
    },
    "AVGO": {
        "title": "AI accelerator vendor revenue",
        "period": "2025 reference view",
        "values": {"NVIDIA": 78.0, "Broadcom": 10.3, "AMD": 7.0, "Other": 4.7},
        "source": "IDC market outlook",
        "source_url": "https://www.semi.org/sites/semi.org/files/2025-09/1%20%EA%B9%80%EC%88%98%EA%B2%B8_IDC%20Semiconductor%20Market%20Outlook.pdf",
        "note": "A reference category view; custom ASIC design share and total accelerator revenue share are not interchangeable.",
    },
    "SNDK": {
        "title": "Global NAND shipments",
        "period": "Q2 2026",
        "values": {"Samsung": 25.0, "SK hynix": 22.0, "YMTC": 14.0, "Kioxia": 14.0, "Micron": 13.0, "SanDisk": 11.0, "Other": 1.0},
        "source": "Counterpoint Research",
        "source_url": "https://counterpointresearch.com/en/insights/server-led-essds-hit-48-percent-of-nand-shipments",
        "note": "Shipment share differs from revenue share because product mix and pricing vary by supplier.",
    },
    "NVDA": {
        "title": "Worldwide discrete data-center GPUs",
        "period": "H1 2024 regulatory reference",
        "values": {"NVIDIA": 85.0, "AMD and other": 15.0},
        "source": "European Commission decision using IDC and company data",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32024M11766",
        "note": "The public decision reports NVIDIA within an 80%-90% range; 85% is the midpoint used only for visualization.",
    },
}


EXTENDED_PROFILES = {
    "GOOG": {
        "business_model": "A global advertising, cloud, subscription and computing-platform business built around Search, YouTube, Android, Google Cloud and AI infrastructure.",
        "research_thesis": "Search and YouTube cash generation can fund a faster-growing cloud and AI platform, while distribution and proprietary data provide multiple monetization paths.",
        "counter_thesis": "AI interfaces can raise serving costs, weaken click economics and require heavy infrastructure spending before new monetization offsets pressure on the core search franchise.",
        "growth_engines": ["Google Cloud and enterprise AI", "Search and commerce monetization", "YouTube subscriptions and advertising"],
        "key_kpis": ["Search revenue growth", "Google Cloud growth and margin", "Capex intensity", "AI query monetization"],
        "key_questions": ["Can AI Mode protect query share without diluting search economics?", "Does Cloud margin scale faster than infrastructure investment?", "How durable is YouTube growth across advertising and subscriptions?"],
        "moat_factors": [("Distribution", "Search, Android, Chrome and YouTube create global consumer reach."), ("Data and intent", "Commercial intent and user behavior strengthen relevance and monetization."), ("Compute stack", "TPUs, models and cloud infrastructure support differentiated economics."), ("Capital capacity", "Core cash generation funds frontier-model and infrastructure investment.")],
        "catalysts": ["Cloud backlog converts with improving margins.", "AI search usage monetizes without a material cost penalty.", "YouTube gains viewing and advertising share.", "Capex growth begins to trail operating-profit growth."],
        "risks": ["AI assistants weaken search distribution or pricing.", "Infrastructure costs and depreciation pressure free cash flow.", "Regulatory remedies change default distribution economics.", "Cloud growth requires lower-margin third-party compute."],
        "monitoring_signals": [("Search", "Query share, commercial query growth and cost per query"), ("Cloud", "Revenue, backlog, margin and capacity"), ("Cash", "Capex, depreciation and free cash flow"), ("Regulation", "Distribution and advertising remedies")],
        "scenario_defaults": {"years": 3, "bear_growth": .10, "base_growth": .16, "bull_growth": .22, "bear_margin": .28, "base_margin": .32, "bull_margin": .36},
        "competitive_dimensions": ["Distribution", "Data", "Cloud scale", "AI stack", "Monetization"],
        "competitive_scores": {"Alphabet": [5, 5, 4, 5, 5], "Microsoft": [5, 4, 5, 5, 5], "Amazon": [4, 4, 5, 4, 5], "Meta": [4, 5, 2, 4, 5]},
        "diligence_questions": ["What is the incremental cost and revenue per AI search interaction?", "How much cloud capacity is committed versus built ahead of demand?", "Which regulatory outcomes would change distribution economics?"],
        "source_url": "https://www.sec.gov/edgar/browse/?CIK=0001652044&owner=exclude&action=getcompany&type=10-K",
    },
    "AVGO": {
        "business_model": "A semiconductor and infrastructure-software platform spanning custom AI accelerators, networking, connectivity and VMware subscription software.",
        "research_thesis": "Custom AI silicon and networking can compound with infrastructure software cash generation, producing a differentiated mix of high growth and recurring revenue.",
        "counter_thesis": "Customer concentration, custom-silicon bargaining power and VMware integration complexity can make headline growth less durable than current expectations imply.",
        "growth_engines": ["Custom AI accelerators", "Data-center networking", "VMware subscription conversion"],
        "key_kpis": ["AI semiconductor revenue", "Customer concentration", "Semiconductor gross margin", "VMware bookings and free cash flow"],
        "key_questions": ["How durable is Broadcom's position as hyperscalers diversify design partners?", "Can AI revenue scale without diluting margin?", "Does VMware retention support the modeled software cash flow?"],
        "moat_factors": [("Co-design", "Deep engineering relationships embed Broadcom in long product roadmaps."), ("Networking", "Switching and connectivity broaden value beyond accelerators."), ("IP portfolio", "Specialized silicon and connectivity IP compress customer time to market."), ("Software cash flow", "Recurring infrastructure software can fund semiconductor investment.")],
        "catalysts": ["Additional hyperscaler programs enter production.", "AI networking grows alongside accelerator shipments.", "VMware bookings stabilize after portfolio changes.", "Free cash flow expands faster than integration costs."],
        "risks": ["A top customer changes design partners.", "Custom silicon pricing compresses gross margin.", "VMware customer attrition exceeds savings.", "Acquisition leverage limits strategic flexibility."],
        "monitoring_signals": [("AI", "Program count, revenue and customer mix"), ("Margins", "Semiconductor gross margin and mix"), ("Software", "Bookings, retention and recurring revenue"), ("Cash", "FCF, debt reduction and integration costs")],
        "scenario_defaults": {"years": 3, "bear_growth": .14, "base_growth": .22, "bull_growth": .30, "bear_margin": .36, "base_margin": .42, "bull_margin": .47},
        "competitive_dimensions": ["Custom silicon", "Networking", "Software", "Customer access", "Cash generation"],
        "competitive_scores": {"Broadcom": [5, 5, 4, 5, 5], "NVIDIA": [4, 5, 3, 5, 5], "Marvell": [4, 4, 2, 4, 3], "AMD": [3, 4, 2, 4, 4]},
        "diligence_questions": ["What share of AI revenue is tied to each major customer?", "How do new programs change gross-margin mix?", "What retention evidence supports VMware cash-flow assumptions?"],
        "source_url": "https://www.sec.gov/edgar/browse/?CIK=0001730168&owner=exclude&action=getcompany&type=10-K",
    },
    "SNDK": {
        "business_model": "A NAND flash and storage company serving data-center, client, mobile and consumer markets through memory products, enterprise SSDs and branded storage.",
        "research_thesis": "AI-driven enterprise SSD demand and constrained NAND supply can improve pricing, utilization and product mix for a focused storage supplier.",
        "counter_thesis": "NAND remains cyclical: high prices can trigger supply, customer inventory corrections or technology transitions that reverse margins quickly.",
        "growth_engines": ["Enterprise SSD demand", "NAND pricing and mix", "Technology-node and yield improvement"],
        "key_kpis": ["NAND ASP", "Enterprise SSD mix", "Bit shipments", "Gross margin and inventory"],
        "key_questions": ["How much of current pricing is contracted versus spot-driven?", "Can enterprise SSD mix remain elevated through a supply response?", "What normalized margin survives the NAND cycle?"],
        "moat_factors": [("Flash IP", "Controller, firmware and NAND integration support performance and qualification."), ("Manufacturing partnership", "Long-standing supply collaboration supports scale and technology access."), ("Qualification", "Enterprise storage qualification can create product-cycle stickiness."), ("Brand and channels", "Consumer and client distribution diversify routes to market.")],
        "catalysts": ["Enterprise SSD mix rises faster than expected.", "Long-term agreements extend price visibility.", "Yield and node transitions lower unit cost.", "Industry capacity stays disciplined."],
        "risks": ["NAND pricing reverses after customer inventory builds.", "Supply additions outpace demand.", "Technology transitions raise cost or delay qualification.", "Customer concentration weakens pricing power."],
        "monitoring_signals": [("Pricing", "Contract and spot NAND prices"), ("Mix", "Enterprise SSD share and customer qualification"), ("Supply", "Industry capex and bit growth"), ("Cash", "Inventory, working capital and FCF")],
        "scenario_defaults": {"years": 3, "bear_growth": .03, "base_growth": .12, "bull_growth": .20, "bear_margin": .18, "base_margin": .28, "bull_margin": .38},
        "competitive_dimensions": ["NAND scale", "Enterprise SSD", "Technology", "Channels", "Cycle resilience"],
        "competitive_scores": {"SanDisk": [4, 4, 4, 5, 3], "Samsung": [5, 5, 5, 5, 5], "SK hynix": [5, 5, 5, 4, 4], "Micron": [4, 4, 5, 4, 4]},
        "diligence_questions": ["What portion of forward demand has enforceable pricing and volume terms?", "How does enterprise SSD mix affect normalized gross margin?", "Which capacity additions can change the 12-month supply balance?"],
        "source_url": "https://www.sec.gov/edgar/browse/?CIK=0002023554&owner=exclude&action=getcompany&type=10-K",
    },
    "NVDA": {
        "business_model": "A full-stack accelerated-computing platform monetized through data-center systems, GPUs, networking, software and ecosystem adoption.",
        "research_thesis": "Architecture leadership, CUDA and system-level integration can sustain premium economics as accelerated computing expands across training, inference and enterprise workloads.",
        "counter_thesis": "Customer concentration, custom silicon and a decelerating infrastructure cycle can pressure growth and valuation even if NVIDIA remains the technical leader.",
        "growth_engines": ["Data-center accelerators", "Networking and systems", "Enterprise inference and software"],
        "key_kpis": ["Data-center revenue", "Gross margin", "Supply and product transitions", "Customer concentration"],
        "key_questions": ["Does Rubin extend performance leadership without a disruptive transition?", "How quickly do custom accelerators take addressable workloads?", "Can software and systems broaden the profit pool beyond GPUs?"],
        "moat_factors": [("CUDA ecosystem", "Developers and optimized libraries reinforce adoption."), ("System architecture", "Compute, networking and software are designed together."), ("Roadmap velocity", "Frequent product cycles raise the execution hurdle for competitors."), ("Scale", "Demand visibility and supplier relationships support rapid deployment.")],
        "catalysts": ["Rubin ramps with strong supply and demand.", "Inference becomes a broader enterprise workload.", "Networking and software outgrow the core GPU cycle.", "Gross margin stabilizes through product transitions."],
        "risks": ["Hyperscalers shift workloads to custom silicon.", "Export controls limit accessible markets.", "Product transitions create supply or margin volatility.", "AI infrastructure returns disappoint end customers."],
        "monitoring_signals": [("Demand", "Cloud capex and customer concentration"), ("Roadmap", "Shipment timing and performance"), ("Margins", "Mix, supply costs and gross margin"), ("Competition", "Custom accelerators and software adoption")],
        "scenario_defaults": {"years": 3, "bear_growth": .12, "base_growth": .22, "bull_growth": .32, "bear_margin": .48, "base_margin": .56, "bull_margin": .62},
        "competitive_dimensions": ["Compute", "Networking", "Software", "Developer ecosystem", "Scale"],
        "competitive_scores": {"NVIDIA": [5, 5, 5, 5, 5], "AMD": [4, 4, 3, 3, 4], "Broadcom": [4, 5, 3, 4, 4], "Hyperscaler silicon": [4, 4, 4, 4, 5]},
        "diligence_questions": ["How concentrated is revenue by customer and platform generation?", "Which inference workloads are most exposed to custom silicon?", "What gross margin is sustainable through the next transition?"],
        "source_url": "https://www.sec.gov/edgar/browse/?CIK=0001045810&owner=exclude&action=getcompany&type=10-K",
    },
}


def target_price_snapshot(ticker: str) -> dict[str, object]:
    return TARGET_PRICE_SNAPSHOTS.get(ticker, {"as_of": "", "source_url": "", "street": [], "house": {}, "basis": ""})


def market_share_snapshot(ticker: str) -> dict[str, object]:
    return MARKET_SHARE_SNAPSHOTS.get(ticker, {"title": "", "period": "", "values": {}, "source": "", "source_url": "", "note": ""})
