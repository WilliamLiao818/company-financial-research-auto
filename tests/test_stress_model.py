import json
import unittest
from dataclasses import asdict
from pathlib import Path

from streamlit.testing.v1 import AppTest

from company_profiles import profile_for
from research import latest_company_summary, load_financials
from stress_model import Assumptions, PRESETS, case_record, compare, preset_cases, scenario_note


class StressModelTests(unittest.TestCase):
    def test_attribution_reconciles_and_assumptions_have_expected_direction(self):
        base = Assumptions(.10, .30, 15.)
        stress = Assumptions(.04, .22, 12.)
        result = compare(100., 3, base, stress)
        self.assertAlmostEqual(result["base"]["enterprise_value"], 100 * 1.1 ** 3 * .3 * 15)
        self.assertAlmostEqual(result["stress"]["enterprise_value"], 100 * 1.04 ** 3 * .22 * 12)
        self.assertAlmostEqual(sum(result["contributions"].values()), result["difference"])
        self.assertLess(max(result["contributions"].values()), 0)
        self.assertAlmostEqual(result["relative_difference"], result["stress"]["enterprise_value"] / result["base"]["enterprise_value"] - 1)
        self.assertEqual(compare(100., 3, base, base)["difference"], 0)

    def test_nonpositive_profit_is_preserved_without_an_ev_multiple(self):
        base = Assumptions(.10, .20, 15.)
        for margin in (0., -.1):
            tested = compare(100, 2, base, Assumptions(.10, margin, 15.))
            self.assertAlmostEqual(tested["stress"]["operating_profit"], 121 * margin)
            self.assertIsNone(tested["stress"]["enterprise_value"])
            self.assertIsNone(tested["relative_difference"])
            self.assertEqual(tested["contributions"], {})
        for revenue in (0., -1., float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                compare(revenue, 3, base, base)

    def test_export_can_reproduce_all_company_cases_in_annual_series_currency(self):
        frame = load_financials()
        for ticker in frame["ticker"].unique():
            summary = latest_company_summary(frame, ticker)
            defaults = profile_for(ticker)["scenario_defaults"]
            for preset in PRESETS:
                with self.subTest(ticker=ticker, preset=preset):
                    base, stress = preset_cases(defaults, preset)
                    record = json.loads(json.dumps(case_record(summary, defaults["years"], base, stress, preset), allow_nan=False))
                    note = scenario_note(record)
                    self.assertIn(record["formula"], note)
                    saved_record = json.loads(note.split("```json\n")[1].split("\n```")[0])
                    self.assertEqual(saved_record, record)
                    self.assertEqual(record["currency"], summary["currency"])
                    self.assertEqual(record["reported_facts"]["period_end"], str(summary["fiscal_year_end"]))
                    self.assertTrue(record["reported_facts"]["public_source"].startswith("https://"))
                    self.assertEqual(record["assumptions"]["base"], asdict(base))
                    repeat = compare(record["reported_facts"]["annual_revenue"], record["horizon_years"],
                                     Assumptions(**record["assumptions"]["base"]), Assumptions(**record["assumptions"]["stress"]))
                    self.assertEqual(repeat, record["outputs"])


class CompanyModeTests(unittest.TestCase):
    def test_lite_pro_round_trip_and_reset(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30)
        app.query_params["ticker"] = "ORCL"
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.radio[0].value, "Lite")
        self.assertFalse(app.number_input)
        self.assertFalse(app.tabs)
        self.assertIn("Save this scenario", [button.label for button in app.get("download_button")])
        self.assertIn("Download full PDF", [button.label for button in app.get("download_button")])
        app.selectbox(key="preset:ORCL").select("Combined downside").run()
        expected = next(m.value for m in app.metric if m.label == "Stress terminal EV")
        app.radio[0].set_value("Pro").run()
        self.assertFalse(app.exception)
        self.assertEqual(next(m.value for m in app.metric if m.label == "Stress terminal EV"), expected)
        next(i for i in app.number_input if i.label == "Stress terminal margin (%)").set_value(-1.).run()
        self.assertFalse(app.exception)
        self.assertEqual(next(m.value for m in app.metric if m.label == "Stress terminal EV"), "N/M")
        app.radio[0].set_value("Lite").run()
        self.assertFalse(app.number_input)
        self.assertEqual(next(m.value for m in app.metric if m.label == "Stress terminal EV"), expected)
        app.radio[0].set_value("Pro").run()
        self.assertEqual(next(m.value for m in app.metric if m.label == "Stress terminal EV"), "N/M")
        next(button for button in app.button if button.label == "Reset this preset").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(next(m.value for m in app.metric if m.label == "Stress terminal EV"), expected)
