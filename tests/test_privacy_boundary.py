import unittest
from pathlib import Path

import pandas as pd

from research import PUBLIC_FINANCIAL_INPUT_COLUMNS


ROOT = Path(__file__).resolve().parents[1]


class PrivacyBoundaryTests(unittest.TestCase):
    def test_public_financial_snapshot_uses_only_allowlisted_columns(self) -> None:
        columns = set(pd.read_csv(ROOT / "data" / "financials.csv", nrows=0).columns)
        self.assertTrue(columns.issubset(PUBLIC_FINANCIAL_INPUT_COLUMNS))

    def test_public_runtime_has_no_private_broker_integration(self) -> None:
        restricted_fingerprints = (
            "ib" + "kr",
            "interactive " + "brokers",
            "ib_" + "insync",
            "ib" + "api",
            "net_" + "liquidation",
            "buying_" + "power",
        )
        runtime_files = [
            *ROOT.glob("*.py"),
            *ROOT.joinpath("scripts").glob("*.py"),
        ]
        for path in runtime_files:
            source = path.read_text(encoding="utf-8").casefold()
            for fingerprint in restricted_fingerprints:
                with self.subTest(path=path.name, fingerprint=fingerprint):
                    self.assertNotIn(fingerprint, source)

        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").casefold()
        for fingerprint in restricted_fingerprints:
            self.assertNotIn(fingerprint, requirements)


if __name__ == "__main__":
    unittest.main()
