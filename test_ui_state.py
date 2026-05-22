import os
from decimal import Decimal

from ui_state import (
    available_currencies,
    available_tags,
    build_file_label,
    filter_purchase_rows,
    format_totals,
    kpi_stats,
)


ROWS = [
    ["01-MAY-26", "AUTOMERCADO ESCAZU", "42,300.00", "CRC", "Groceries"],
    ["02-MAY-26", "UBER TRIP", "8.70", "USD", "Transport"],
    ["03-ABR-26", "UNMATCHED VENDOR", "19.95", "USD", "N/A"],
]


def test_filter_purchase_rows_combines_text_currency_month_and_tag():
    result = filter_purchase_rows(
        ROWS,
        search_text="uber",
        currencies={"USD"},
        month_key="2026-05",
        tag_name="Transport",
    )

    assert result == [["02-MAY-26", "UBER TRIP", "8.70", "USD", "Transport"]]


def test_filter_purchase_rows_allows_all_filter_values():
    result = filter_purchase_rows(
        ROWS,
        search_text="",
        currencies=set(),
        month_key="Todos",
        tag_name="Todos",
    )

    assert result == ROWS


def test_available_filter_choices_are_sorted():
    assert available_currencies(ROWS) == ["CRC", "USD"]
    assert available_tags(ROWS) == ["Groceries", "N/A", "Transport"]


def test_kpi_stats_counts_rows_currencies_untagged_and_over_limit_tags():
    tags = {
        "Groceries": {"keywords": [], "limit": 100},
        "Transport": {"keywords": [], "limit": 5},
    }

    stats = kpi_stats(ROWS, ROWS, tags, natag="N/A")

    assert stats == {
        "total_rows": 3,
        "visible_rows": 3,
        "untagged_rows": 1,
        "currency_count": 2,
        "over_limit_tags": 2,
    }


def test_kpi_stats_uses_decimal_math_for_limit_comparisons():
    rows = [
        ["01-MAY-26", "SMALL CHARGE", "0.10", "USD", "Misc"],
        ["02-MAY-26", "SMALL CHARGE", "0.20", "USD", "Misc"],
    ]
    tags = {"Misc": {"keywords": [], "limit": Decimal("0.30")}}

    stats = kpi_stats(rows, rows, tags, natag="N/A")

    assert stats["over_limit_tags"] == 0


def test_format_totals_outputs_sorted_currency_totals():
    assert format_totals(ROWS) == "Totals: CRC 42,300.00; USD 28.65"
    assert format_totals([]) == "Totals: 0.00"


def test_format_totals_uses_decimal_math_for_cents():
    rows = [
        ["01-MAY-26", "SMALL CHARGE", "0.10", "USD", "Misc"],
        ["02-MAY-26", "SMALL CHARGE", "0.20", "USD", "Misc"],
    ]

    assert format_totals(rows) == "Totals: USD 0.30"


def test_build_file_label_handles_empty_single_and_multiple_files():
    assert build_file_label([]) == "No PDFs selected"
    assert build_file_label([os.path.join("tmp", "statement.pdf")]) == "statement.pdf"
    assert build_file_label([os.path.join("tmp", "a.pdf"), os.path.join("tmp", "b.pdf")]) == "2 PDFs selected"
