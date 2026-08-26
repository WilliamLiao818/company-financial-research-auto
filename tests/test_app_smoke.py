import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class AppSmokeTests(unittest.TestCase):
    def test_app_renders_all_research_sections(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path), default_timeout=20)
        app.run()
        self.assertEqual(len(app.exception), 0)
        tab_labels = [tab.label for tab in app.tabs]
        self.assertEqual(
            tab_labels,
            ["Executive View", "Financial Diagnostics", "Accounting Quality", "Valuation & Scenarios", "Evidence & PDF"],
        )
        self.assertEqual(app.radio[0].label, "Research mode")
        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
