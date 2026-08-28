import json
import os
import unittest
from unittest.mock import patch

import pandas as pd

from input_pipeline import company_facts_json_from_bytes, financial_csv_from_bytes, parse_identifiers
from sec_connector import SecConfigurationError, SecInputError, company_facts_to_frame, fetch_company_facts, normalize_cik


def sec_payload() -> dict:
    def metric(tag: str, values: list[tuple[int, str, int]]) -> dict:
        return {
            tag: {
                "units": {
                    "USD": [
                        {
                            "fy": year,
                            "fp": "FY",
                            "form": "10-K",
                            "end": period_end,
                            "filed": f"{year + 1}-02-15",
                            "accn": f"0000001234-{str(year + 1)[-2:]}-000001",
                            "val": value,
                        }
                        for year, period_end, value in values
                    ]
                }
            }
        }

    facts = {}
    facts.update(metric("RevenueFromContractWithCustomerExcludingAssessedTax", [(2024, "2024-12-31", 100), (2025, "2025-12-31", 120)]))
    facts.update(metric("OperatingIncomeLoss", [(2024, "2024-12-31", 20), (2025, "2025-12-31", 24)]))
    facts.update(metric("NetIncomeLoss", [(2024, "2024-12-31", 15), (2025, "2025-12-31", 18)]))
    facts.update(metric("NetCashProvidedByUsedInOperatingActivities", [(2024, "2024-12-31", 25), (2025, "2025-12-31", 30)]))
    facts.update(metric("PaymentsToAcquirePropertyPlantAndEquipment", [(2024, "2024-12-31", 5), (2025, "2025-12-31", 6)]))
    facts.update(metric("Assets", [(2024, "2024-12-31", 200), (2025, "2025-12-31", 220)]))
    facts.update(metric("Liabilities", [(2024, "2024-12-31", 80), (2025, "2025-12-31", 88)]))
    facts.update(metric("StockholdersEquity", [(2024, "2024-12-31", 120), (2025, "2025-12-31", 132)]))
    return {"cik": 1234, "entityName": "Example Corporation", "facts": {"us-gaap": facts}}


class SecConnectorTests(unittest.TestCase):
    def test_normalize_cik_and_identifier_limit(self) -> None:
        self.assertEqual(normalize_cik("CIK1234"), "0000001234")
        self.assertEqual(parse_identifiers("msft, ORCL\nmsft"), ["MSFT", "ORCL"])
        with self.assertRaises(SecInputError):
            parse_identifiers("A,B,C,D,E,F")

    def test_uploaded_company_facts_preserves_missing_values_and_provenance(self) -> None:
        frame = company_facts_json_from_bytes(json.dumps(sec_payload()).encode(), ticker="EXAMPLE", years=2)
        self.assertEqual(set(frame["ticker"]), {"EXAMPLE"})
        self.assertTrue(frame["gross_profit"].isna().all())
        self.assertTrue(frame["cost_of_revenue"].isna().all())
        self.assertEqual(frame.iloc[-1]["revenue_xbrl_tag"], "RevenueFromContractWithCustomerExcludingAssessedTax")
        self.assertEqual(frame.iloc[-1]["input_source"], "uploaded_sec_json")

    def test_company_facts_rejects_non_company_facts_json(self) -> None:
        with self.assertRaisesRegex(SecInputError, "US GAAP or IFRS"):
            company_facts_to_frame({"cik": 1234, "facts": {}}, years=2)

    def test_online_fetch_requires_identifiable_user_agent_before_network(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SecConfigurationError, "SEC_USER_AGENT"):
                fetch_company_facts("CIK1234", years=2)

    @patch("sec_connector._fetch_json")
    def test_ticker_resolves_to_cik_and_loads_facts(self, fetch_json) -> None:
        fetch_json.side_effect = [
            {"0": {"ticker": "TST", "cik_str": 1234, "title": "Example Corporation"}},
            sec_payload(),
        ]
        frame = fetch_company_facts("tst", years=2)
        self.assertEqual(set(frame["ticker"]), {"TST"})
        self.assertEqual(set(frame["cik"]), {"0000001234"})
        self.assertEqual(len(frame), 2)

    def test_same_schema_csv_is_parsed_in_memory(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "ticker": "TST",
                    "company": "Test",
                    "fiscal_year": 2025,
                    "fiscal_year_end": "2025-12-31",
                    "filed": "2026-02-15",
                    "source_url": "https://example.com/filing",
                    "revenue": 100,
                    "gross_profit": 40,
                    "cost_of_revenue": 60,
                    "operating_income": 20,
                    "net_income": 15,
                    "operating_cash_flow": 25,
                    "capex": 5,
                    "assets": 200,
                    "liabilities": 80,
                    "equity": 120,
                }
            ]
        )
        parsed = financial_csv_from_bytes(frame.to_csv(index=False).encode())
        self.assertEqual(parsed.iloc[0]["input_source"], "uploaded_csv")
        self.assertEqual(parsed.iloc[0]["free_cash_flow"], 20)


if __name__ == "__main__":
    unittest.main()
