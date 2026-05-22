from datetime import datetime
from decimal import Decimal
import unittest

from summary import (
    available_months,
    average_spend_by_tag_month,
    currency_totals,
    filter_rows_by_month,
    filter_rows_by_text,
    summary_insights,
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
        result = currency_totals(self.rows)

        self.assertEqual(result, {"CRC": Decimal("1800.00"), "EUR": Decimal("9.00"), "USD": Decimal("20.00")})
        self.assertIsInstance(result["CRC"], Decimal)

    def test_currency_totals_uses_decimal_math_for_cents(self):
        rows = [
            ["01-ENE-25", "SMALL CHARGE", "0.10", "USD", "Misc"],
            ["02-ENE-25", "SMALL CHARGE", "0.20", "USD", "Misc"],
        ]

        self.assertEqual(currency_totals(rows)["USD"], Decimal("0.30"))

    def test_available_months_and_month_filter_accept_spanish_dates(self):
        self.assertEqual(available_months(self.rows), ["2025-01", "2025-02", "2025-03"])
        self.assertEqual(filter_rows_by_month(self.rows, "2025-02"), [self.rows[2], self.rows[3]])
        self.assertEqual(filter_rows_by_month(self.rows, "Todos"), self.rows)

    def test_summary_aggregates_computes_chart_data_for_one_selected_currency(self):
        result = summary_aggregates(self.rows, {"CRC"})

        self.assertEqual(dict(result["tag_totals"]), {"Food": Decimal("1800.00")})
        self.assertEqual(dict(result["monthly_totals"]), {"2025-01": Decimal("1500.00"), "2025-02": Decimal("300.00")})
        self.assertEqual(result["daily_totals"][datetime(2025, 1, 1)], Decimal("1000.00"))
        self.assertEqual(
            result["cumulative_points"],
            [
                ("2025-01-01", Decimal("1000.00")),
                ("2025-01-15", Decimal("1500.00")),
                ("2025-02-03", Decimal("1800.00")),
            ],
        )

    def test_summary_aggregates_rejects_multiple_currencies(self):
        with self.assertRaises(ValueError):
            summary_aggregates(self.rows, {"CRC", "USD"})

    def test_average_spend_by_tag_month_preserves_single_currency_table_semantics(self):
        result = average_spend_by_tag_month(
            self.rows,
            {"CRC"},
            {"Food": Decimal("1000.00")},
        )

        self.assertEqual(result["months"], ["2025-01", "2025-02"])
        self.assertEqual(
            result["currencies_by_month"],
            {"2025-01": ["CRC"], "2025-02": ["CRC"]},
        )
        self.assertEqual(
            result["tag_month_totals"],
            {
                "Food": {"2025-01": {"CRC": Decimal("1500.00")}, "2025-02": {"CRC": Decimal("300.00")}},
            },
        )
        self.assertEqual(result["tag_global_totals"], {"Food": Decimal("1800.00")})
        self.assertEqual(result["tag_average_by_month"], {"Food": Decimal("900.00")})
        self.assertEqual(
            result["totals"],
            {"2025-01": {"CRC": Decimal("1500.00")}, "2025-02": {"CRC": Decimal("300.00")}},
        )
        self.assertEqual(result["over_limit_by_tag"], {"Food": False})
        self.assertFalse(result["total_over_limit"])

    def test_average_spend_by_tag_month_rejects_multiple_currencies(self):
        with self.assertRaises(ValueError):
            average_spend_by_tag_month(self.rows, {"CRC", "USD"}, {"Food": 1000})

    def test_summary_insights_calculates_totals_top_tags_and_largest_purchases(self):
        rows = [
            ["01-ABR-26", "MARKET", "100.00", "USD", "Groceries"],
            ["02-ABR-26", "CAFE", "50.00", "USD", "Dining"],
            ["03-ABR-26", "SUPERMARKET", "25.00", "USD", "Groceries"],
            ["04-ABR-26", "IGNORED", "999.00", "CRC", "Groceries"],
        ]

        result = summary_insights(rows, {"USD"}, {}, month_key="Todos", top_n=2)

        self.assertEqual(result["total_spend"], Decimal("175.00"))
        self.assertEqual(result["purchase_count"], 3)
        self.assertEqual(result["top_tags"], [("Groceries", Decimal("125.00")), ("Dining", Decimal("50.00"))])
        self.assertEqual(result["largest_purchases"], [rows[0], rows[1]])
        self.assertIn("Total spend is 175.00 across 3 purchases.", result["messages"])

    def test_summary_insights_detects_over_limit_tags_with_decimal_math(self):
        rows = [
            ["01-MAY-26", "SMALL CHARGE", "0.10", "USD", "Misc"],
            ["02-MAY-26", "SMALL CHARGE", "0.21", "USD", "Misc"],
            ["03-MAY-26", "NO LIMIT", "500.00", "USD", "Travel"],
        ]

        result = summary_insights(rows, {"USD"}, {"Misc": Decimal("0.30"), "Travel": Decimal("0")})

        self.assertEqual(result["over_limit_tags"], [("Misc", Decimal("0.31"), Decimal("0.30"))])
        self.assertIn("Misc is 0.01 over its limit.", result["messages"])

    def test_summary_insights_leads_with_budget_takeaway_when_tag_is_over_limit(self):
        rows = [
            ["01-MAY-26", "MARKET", "100.00", "CRC", "Super"],
            ["02-MAY-26", "PHARMACY", "80.00", "CRC", "Salud"],
            ["03-MAY-26", "CAFE", "20.00", "CRC", "Dining"],
        ]

        result = summary_insights(
            rows,
            {"CRC"},
            {"Super": Decimal("70.00"), "Salud": Decimal("75.00")},
        )

        self.assertEqual(result["headline"], "Super is over its limit by CRC 30.00.")
        self.assertEqual(
            result["detail"],
            "- Super accounts for 50.0% of spend.\n"
            "- Salud is also over by CRC 5.00.\n"
            "- Total spend is CRC 200.00 across 3 purchases.",
        )

    def test_summary_insights_compares_latest_month_to_previous_when_all_months_selected(self):
        rows = [
            ["01-ABR-26", "APRIL", "100.00", "USD", "Dining"],
            ["01-MAY-26", "MAY", "150.00", "USD", "Dining"],
            ["02-MAY-26", "MAY EXTRA", "50.00", "USD", "Dining"],
        ]

        result = summary_insights(rows, {"USD"}, {}, month_key="Todos")

        self.assertEqual(
            result["comparison"],
            {
                "current_month": "2026-05",
                "previous_month": "2026-04",
                "current_total": Decimal("200.00"),
                "previous_total": Decimal("100.00"),
                "delta": Decimal("100.00"),
                "percent_change": Decimal("100.00"),
            },
        )
        self.assertIn("2026-05 spend is 100.00 more than 2026-04.", result["messages"])

    def test_summary_insights_compares_selected_month_to_previous_calendar_month(self):
        rows = [
            ["01-DIC-25", "DECEMBER", "75.00", "USD", "Dining"],
            ["01-ENE-26", "JANUARY", "100.00", "USD", "Dining"],
        ]

        result = summary_insights(rows, {"USD"}, {}, month_key="2026-01")

        self.assertEqual(result["total_spend"], Decimal("100.00"))
        self.assertEqual(result["comparison"]["current_month"], "2026-01")
        self.assertEqual(result["comparison"]["previous_month"], "2025-12")
        self.assertEqual(result["comparison"]["percent_change"], Decimal("33.33"))

    def test_summary_insights_rejects_multiple_currencies(self):
        with self.assertRaises(ValueError):
            summary_insights(self.rows, {"CRC", "USD"}, {})

    def test_summary_insights_skips_malformed_rows_and_amounts(self):
        rows = [
            ["01-MAY-26", "VALID", "10.00", "USD", "Misc"],
            ["02-MAY-26", "BAD AMOUNT", "oops", "USD", "Misc"],
            ["03-MAY-26", "TOO SHORT"],
        ]

        result = summary_insights(rows, {"USD"}, {"Misc": Decimal("20.00")})

        self.assertEqual(result["total_spend"], Decimal("10.00"))
        self.assertEqual(result["purchase_count"], 1)
        self.assertEqual(result["top_tags"], [("Misc", Decimal("10.00"))])


if __name__ == "__main__":
    unittest.main()
