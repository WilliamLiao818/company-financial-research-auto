# Company Financial Research Snapshot

Public SEC XBRL facts, deterministic calculations and source links. Not investment advice.

| Company | Fiscal year | Revenue | Growth | Gross margin | Operating margin | Free cash flow |
|---|---:|---:|---:|---:|---:|---:|
| [Microsoft Corporation](https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json) | 2026 | $331.8B | 17.8% | 67.9% | 46.8% | $67.0B |
| [NVIDIA Corporation](https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json) | 2026 | $215.9B | 65.5% | 71.1% | 60.4% | $96.7B |
| [Oracle Corporation](https://data.sec.gov/api/xbrl/companyfacts/CIK0001341439.json) | 2026 | $67.4B | 17.3% | — | 30.6% | $-23.7B |

## MSFT rule-based research prompts

- 资本开支/营收达到30%或以上：需要核查扩产、云基础设施或一次性项目。

Data-quality checks:

- No rule-based data quality warning for the latest fiscal year.

## NVDA rule-based research prompts

- 营收增速较上年放缓至少10个百分点：需要核查基数与分部驱动。

Data-quality checks:

- No rule-based data quality warning for the latest fiscal year.

## ORCL rule-based research prompts

- 简化自由现金流为负：经营现金流不足以覆盖当年资本开支。
- 资本开支/营收达到30%或以上：需要核查扩产、云基础设施或一次性项目。
- 总负债/总资产达到80%或以上：这是结构提示，不等同于净债务或信用结论。

Data-quality checks:

- Missing latest-year fields: gross_profit

## Valuation boundary

The interactive app includes a user-assumption scenario for growth, entry/exit multiples, net debt, MOIC and IRR. It is not a target price, DCF, investment recommendation or completed private-equity return model.
