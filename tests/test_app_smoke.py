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
        self.assertIn("1. 财务趋势与提示", tab_labels)
        self.assertIn("2. 用户选择的年度比较", tab_labels)
        self.assertIn("3. 估值与回报情景", tab_labels)
        self.assertIn("4. 证据、公式与报告", tab_labels)
        self.assertEqual(app.radio[0].label, "数据模式")
        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
