"""Primary research roles for the public semiconductor and AI company directory.

Each company has one discovery category. The role identifies a concrete
product, technology or deployment activity, not a share of company revenue.
"""

COVERAGE_GROUPS = {
    "Compute & chip design": {
        "AAPL": "Apple silicon and Neural Engines for on-device inference",
        "AMD": "Instinct accelerators and EPYC server processors",
        "ARM": "CPU architecture and processor IP for cloud and edge chips",
        "AVGO": "Custom accelerators and switching silicon",
        "INTC": "Xeon server processors, accelerators and chip manufacturing",
        "LSCC": "Low-power FPGAs for server management and control",
        "MRVL": "Custom compute silicon and data-center interconnect chips",
        "NVDA": "GPU accelerators, networking and accelerated-computing software",
        "QCOM": "Snapdragon processors and on-device inference engines",
    },
    "Foundry, equipment & EDA": {
        "AMAT": "Materials engineering and wafer-processing equipment",
        "AMKR": "Outsourced semiconductor packaging and test",
        "ASML": "Lithography systems for chip manufacturing",
        "CDNS": "Chip design, verification and system analysis software",
        "ENTG": "Materials and contamination control for semiconductor fabs",
        "GFS": "Specialty foundry processes for communications and silicon photonics",
        "KLAC": "Wafer inspection, metrology and yield management",
        "LRCX": "Deposition, etch and clean equipment for semiconductor fabs",
        "SNPS": "Electronic design automation and reusable semiconductor IP",
        "TER": "Automated testing for processors, memory and other chips",
        "TSM": "Contract chip fabrication and advanced packaging",
    },
    "Memory & storage": {
        "MU": "High-bandwidth memory, DRAM and data-center flash",
        "RMBS": "Memory-interface chips and IP for server memory systems",
        "SNDK": "NAND flash and data-center solid-state drives",
        "STX": "High-capacity nearline hard drives for data centers",
        "WDC": "Hard-disk storage for cloud and enterprise data centers",
    },
    "Networking & optics": {
        "ANET": "Ethernet switching and network software for AI clusters",
        "COHR": "Optical transceivers and photonics for data-center links",
        "CSCO": "Data-center switches, routing silicon and optical networking",
        "FN": "Contract manufacturing for optical communications equipment",
        "LITE": "Optical components and transceivers for cloud networks",
        "MTSI": "Semiconductor components for high-speed optical interconnects",
    },
    "Servers, power & cooling": {
        "ADI": "Power management and monitoring for accelerator boards and servers",
        "DELL": "Accelerated servers, storage and rack integration",
        "ETN": "Electrical distribution and backup power for data centers",
        "HPE": "Accelerated computing systems and data-center networking",
        "MPWR": "Power-management chips and modules for data-center processors",
        "SMCI": "GPU servers, rack-scale integration and liquid cooling",
        "TXN": "Power conversion and sensing chips for data-center racks",
        "VRT": "Power delivery and thermal management for data centers",
    },
    "Cloud & AI platforms": {
        "AMZN": "AWS cloud capacity, Trainium chips and Bedrock model services",
        "GOOG": "Google Cloud, Gemini models and TPU accelerators",
        "IBM": "watsonx enterprise AI software and hybrid-cloud deployment",
        "META": "Llama models and large-scale training and inference infrastructure",
        "MSFT": "Azure cloud infrastructure and AI model services",
        "NET": "Workers AI inference on a distributed developer platform",
        "ORCL": "Oracle Cloud Infrastructure GPU clusters and cloud databases",
        "PLTR": "AI Platform for deploying models into operational workflows",
        "SNOW": "Cortex AI services on the Snowflake data platform",
    },
}

COMPANY_SECTORS = {
    ticker: sector for sector, companies in COVERAGE_GROUPS.items() for ticker in companies
}
COMPANY_ROLES = {
    ticker: role for companies in COVERAGE_GROUPS.values() for ticker, role in companies.items()
}
