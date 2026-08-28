import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from research_catalog import COMPANY_NAMES


class AppSmokeTests(unittest.TestCase):
    def test_app_opens_with_search_and_fifteen_prebuilt_packs(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path), default_timeout=20)
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([title.value for title in app.title], ["Start with a company."])
        self.assertEqual(app.selectbox[0].label, "Search ticker or company")
        button_labels = [button.label for button in app.button]
        self.assertEqual(button_labels.count("Open"), 15)
        self.assertIn("Open company", button_labels)

    def test_prebuilt_company_opens_full_research_architecture(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path), default_timeout=30)
        app.run()
        next(button for button in app.button if button.label == "Open").click()
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([title.value for title in app.title], ["Microsoft Corporation"])
        self.assertEqual(
            [tab.label for tab in app.tabs],
            ["Overview", "Business & moat", "Financials & quality", "Competition", "Market performance", "Valuation & scenarios", "Catalysts & risks"],
        )

    def test_every_prebuilt_company_renders_without_an_exception(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        for ticker, company_name in COMPANY_NAMES.items():
            with self.subTest(ticker=ticker):
                app = AppTest.from_file(str(app_path), default_timeout=30)
                app.query_params["ticker"] = ticker
                app.run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual([title.value for title in app.title], [company_name])


if __name__ == "__main__":
    unittest.main()
