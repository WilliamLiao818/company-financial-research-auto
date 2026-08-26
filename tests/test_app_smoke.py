import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class AppSmokeTests(unittest.TestCase):
    def test_app_opens_with_clear_company_and_input_selection(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path), default_timeout=20)
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([title.value for title in app.title], ["Choose the company or evidence path first."])
        button_labels = [button.label for button in app.button]
        self.assertIn("Open MSFT", button_labels)
        self.assertIn("Open ORCL", button_labels)
        self.assertIn("Continue", button_labels)
        self.assertEqual(app.selectbox[0].label, "Research mode")


if __name__ == "__main__":
    unittest.main()
