import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from measurements import first_available_fact, supplier_rollforward, conditional_maturity


class MeasurementTests(unittest.TestCase):
    def test_vintage_not_latest_revision(self):
        rows = [dict(start="2023-01-01", end="2023-12-31", filed=d, val=v, accn=d, form="10-K")
                for d, v in [("2024-02-01", 10), ("2025-02-01", 99)]]
        self.assertIsNone(first_available_fact(rows, "2023-01-01", "2023-12-31", "2024-01-31"))
        self.assertEqual(first_available_fact(rows, "2023-01-01", "2023-12-31", "2025-03-01")["val"], 10)

    def test_missing_not_zero(self):
        self.assertEqual(supplier_rollforward(None, 10, 10, 0, 100)["status"], "missing_input")
        self.assertIsNone(supplier_rollforward(0, 0, 0, 0, 100)["gross_turnover"])

    def test_reconciliation(self):
        self.assertEqual(supplier_rollforward(20, 100, 105, 15, 1000)["status"], "reconciled")
        self.assertEqual(supplier_rollforward(20, 100, 105, 16, 1000)["status"], "review_required")

    def test_separate_drawn_and_undrawn(self):
        row = dict(instrument_id="synthetic", source_filed="2024-01-01", nominal_maturity="2028-01-01",
                   conditional_maturity="2025-01-01", drawn_usd=100, undrawn_available_usd=50)
        result = conditional_maturity([row], "2024-02-01", "2025-02-01")
        self.assertEqual(result["conditional_extra_drawn_usd"], 100)
        self.assertEqual(result["conditional_lost_undrawn_usd"], 50)
        with self.assertRaises(ValueError):
            conditional_maturity([row, row], "2024-02-01", "2025-02-01")
        with self.assertRaises(ValueError):
            conditional_maturity([row], "2023-02-01", "2025-02-01")


if __name__ == "__main__":
    unittest.main()
