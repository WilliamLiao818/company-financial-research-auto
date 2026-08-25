import unittest

import pandas as pd

from research import (
    add_metrics,
    financial_health_prompts,
    latest_peer_comparison,
    quality_flags,
    scenario_sensitivity,
    valuation_scenario,
)


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "TEST",
                "fiscal_year": 2025,
                "revenue": 100.0,
                "gross_profit": 40.0,
                "operating_income": 20.0,
                "net_income": 15.0,
                "operating_cash_flow": 25.0,
                "capex": 5.0,
                "assets": 200.0,
                "liabilities": 80.0,
                "equity": 120.0,
            },
            {
                "ticker": "TEST",
                "fiscal_year": 2026,
                "revenue": 120.0,
                "gross_profit": 48.0,
                "operating_income": 24.0,
                "net_income": 18.0,
                "operating_cash_flow": 30.0,
                "capex": 6.0,
                "assets": 220.0,
                "liabilities": 88.0,
                "equity": 132.0,
            },
        ]
    )


class ResearchTests(unittest.TestCase):
    def test_metrics_are_transparent_and_deterministic(self) -> None:
        result = add_metrics(sample_frame())
        latest = result.iloc[-1]
        self.assertEqual(latest["gross_margin"], 0.4)
        self.assertEqual(latest["operating_margin"], 0.2)
        self.assertEqual(latest["free_cash_flow"], 24.0)
        self.assertEqual(round(latest["revenue_growth"], 6), 0.2)
        self.assertEqual(latest["capex_intensity"], 0.05)
        self.assertEqual(round(latest["cash_conversion"], 6), round(30 / 18, 6))
        self.assertEqual(latest["debt_to_assets_proxy"], 0.4)

    def test_quality_check_has_a_result(self) -> None:
        result = add_metrics(sample_frame())
        self.assertEqual(
            quality_flags(result, "TEST"),
            ["No rule-based data quality warning for the latest fiscal year."],
        )

    def test_health_prompts_are_questions_not_recommendations(self) -> None:
        frame = sample_frame()
        frame.loc[1, "revenue"] = 80.0
        frame.loc[1, "operating_income"] = 4.0
        frame.loc[1, "operating_cash_flow"] = 5.0
        frame.loc[1, "capex"] = 30.0
        result = add_metrics(frame)
        prompts = " ".join(financial_health_prompts(result, "TEST"))
        self.assertIn("营收同比下降", prompts)
        self.assertIn("简化自由现金流为负", prompts)
        self.assertNotIn("买入", prompts)

    def test_latest_peer_comparison_returns_one_row_per_ticker(self) -> None:
        other = sample_frame().assign(ticker="OTHER")
        result = latest_peer_comparison(add_metrics(pd.concat([sample_frame(), other], ignore_index=True)))
        self.assertEqual(len(result), 2)
        self.assertEqual(set(result["ticker"]), {"TEST", "OTHER"})

    def test_valuation_scenario_exposes_moic_and_irr(self) -> None:
        scenario = valuation_scenario(
            base_metric_value=100.0,
            metric="revenue",
            annual_growth_rate=0.10,
            holding_period_years=2,
            entry_multiple=5.0,
            exit_multiple=6.0,
        )
        self.assertAlmostEqual(scenario["exit_metric_value"], 121.0)
        self.assertAlmostEqual(scenario["moic"], 726 / 500)
        self.assertAlmostEqual(scenario["irr"], (726 / 500) ** 0.5 - 1)

    def test_valuation_rejects_nonpositive_base_metric(self) -> None:
        with self.assertRaises(ValueError):
            valuation_scenario(
                base_metric_value=0,
                metric="revenue",
                annual_growth_rate=0.10,
                holding_period_years=5,
                entry_multiple=5.0,
                exit_multiple=5.0,
            )

    def test_sensitivity_keeps_every_assumption_pair(self) -> None:
        result = scenario_sensitivity(
            base_metric_value=100.0,
            metric="revenue",
            annual_growth_rates=[0.05, 0.10, 0.15],
            holding_period_years=5,
            entry_multiple=5.0,
            exit_multiples=[4.0, 5.0, 6.0],
        )
        self.assertEqual(len(result), 9)
        self.assertTrue({"annual_growth_rate", "exit_multiple", "moic", "irr"}.issubset(result.columns))


if __name__ == "__main__":
    unittest.main()
