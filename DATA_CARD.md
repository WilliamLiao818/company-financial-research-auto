# Data card

- Supported source families: U.S. Securities and Exchange Commission filings and Company Facts; Financial Modeling Prep annual statements when a user supplies a key; dated public market-share and target-price sources.
- Prebuilt coverage: 15 companies — Microsoft, Oracle, Alphabet, Broadcom, Sandisk, NVIDIA, Marvell, Apple, Amazon, Meta, Lumentum, Applied Materials, TSMC, ASML and AMD; four or five annual periods are available per company.
- Snapshot update date: 2026-09-29. Each prebuilt pack also carries a separate, native-currency latest-quarter snapshot and direct link to the official filing or SEC-filed earnings exhibit available by this date.
- Unit: U.S. dollars, as filed in XBRL or shown as a convenience translation in the issuer's filing. TSMC FY2025 uses the USD convenience translation in its 20-F; the issuer's reporting currency remains TWD.
- Input modes: 15 prebuilt packs, online ticker/CIK through SEC Company Facts, and an in-session provider-key path for other U.S.-listed companies.
- Processing: the preferred supported standard US-GAAP tag is selected first; within a tag and period, the latest-filed annual fact is retained. Latest-quarter values require an explicit 70–110-day statement column and are not mixed into or annualized within the annual series.
- Provenance: the bundled display snapshot retains filed dates and filing URLs. SEC refresh outputs additionally preserve CIK, selected XBRL tags, accessions, forms and Company Facts URLs when available. Provider rows carry statement-period and source-family metadata.
- Derived metrics: growth, margins, simplified free cash flow, capex intensity, cash conversion and a liabilities/assets proxy are deterministic calculations.
- Scenario inputs: growth and entry/exit multiples are user assumptions and are never presented as sourced company facts. Dated institutional targets remain separate from The Company Bear/Base/Bull range.
- Missingness policy: unsupported or absent facts remain null; the connector does not estimate, interpolate or silently substitute company-specific values.
- Retention: user-supplied provider keys are held only in the active Streamlit session and are not written by application code. Hosting-platform logging and retention remain the deployer's responsibility.
- Limitations: company-specific tags, restatements, fiscal calendars, foreign-issuer reporting currencies and user-supplied CSV quality may affect comparability. TSMC and ASML market-performance series represent their U.S.-traded ADRs. Always verify material conclusions against the original filing.
- License/usage: public regulatory filings; this repository stores a normalized factual snapshot and source URLs.
