from datetime import datetime
import unittest

from summary import (
    available_months,
    average_spend_by_tag_month,
    currency_totals,
    filter_rows_by_month,
    filter_rows_by_text,
    summary_aggregates,
)


class SummaryTest(unittest.TestCase):
    def setUp(self):
        self.rows = [
            ["01-ENE-25", "CITY MARKET", "1,000.00", "CRC", "Food"],
            ["15-ENE-25", "CAFE", "500.00", "CRC", "Food"],
            ["02-FEB-25", "UBER", "20.00", "USD", "Travel"],
            ["03-FEB-25", "MARKET", "300.00", "CRC", "Food"],
            ["04-MAR-25", "OUT OF SCOPE", "9.00", "EUR", "Other"],
        ]

    def test_filter_rows_by_text_matches_any_displayed_cell(self):
        self.assertEqual(filter_rows_by_text(self.rows, "uber"), [self.rows[2]])
        self.assertEqual(filter_rows_by_text(self.rows, ""), self.rows)

    def test_currency_totals_sums_amounts_by_currency(self):
        self.assertEqual(
            currency_totals(self.rows),
            {"CRC": 1800.0, "EUR": 9.0, "USD": 20.0},
        )

    def test_available_months_and_month_filter_accept_spanish_dates(self):
        self.assertEqual(available_months(self.rows), ["2025-01", "2025-02", "2025-03"])
        self.assertEqual(filter_rows_by_month(self.rows, "2025-02"), [self.rows[2], self.rows[3]])
        self.assertEqual(filter_rows_by_month(self.rows, "Todos"), self.rows)

    def test_summary_aggregates_computes_chart_data_for_selected_currencies(self):
        result = summary_aggregates(self.rows, {"CRC", "USD"})

        self.assertEqual(dict(result["tag_totals"]), {"Food": 1800.0, "Travel": 20.0})
        self.assertEqual(dict(result["monthly_totals"]), {"2025-01": 1500.0, "2025-02": 320.0})
        self.assertEqual(result["daily_totals"][datetime(2025, 1, 1)], 1000.0)
        self.assertEqual(
            result["cumulative_points"],
            [
                ("2025-01-01", 1000.0),
                ("2025-01-15", 1500.0),
                ("2025-02-02", 1520.0),
                ("2025-02-03", 1820.0),
            ],
        )

    def test_average_spend_by_tag_month_preserves_current_table_semantics(self):
        result = average_spend_by_tag_month(
            self.rows,
            {"CRC", "USD"},
            {"Food": 1000, "Travel": 10},
        )

        self.assertEqual(result["months"], ["2025-01", "2025-02"])
        self.assertEqual(
            result["currencies_by_month"],
            {"2025-01": ["CRC"], "2025-02": ["CRC", "USD"]},
        )
        self.assertEqual(
            result["tag_month_totals"],
            {
                "Food": {"2025-01": {"CRC": 1500.0}, "2025-02": {"CRC": 300.0}},
                "Travel": {"2025-02": {"USD": 20.0}},
            },
        )
        self.assertEqual(result["tag_global_totals"], {"Food": 1800.0, "Travel": 20.0})
        self.assertEqual(result["tag_average_by_month"], {"Food": 900.0, "Travel": 20.0})
        self.assertEqual(
            result["totals"],
            {"2025-01": {"CRC": 1500.0}, "2025-02": {"CRC": 300.0, "USD": 20.0}},
        )
        self.assertEqual(result["over_limit_by_tag"], {"Food": False, "Travel": True})
        self.assertFalse(result["total_over_limit"])


if __name__ == "__main__":
    unittest.main()
