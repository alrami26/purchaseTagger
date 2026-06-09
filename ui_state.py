#!/usr/bin/env python3
import os
from collections import Counter

from money import ZERO, format_amount, parse_amount
from summary import currency_totals, filter_rows_by_month, filter_rows_by_text, purchase_spend_amount


ALL_MONTHS = "Todos"
ALL_TAGS = "Todos"


def filter_purchase_rows(rows, search_text="", currencies=None, month_key=ALL_MONTHS, tag_name=ALL_TAGS):
    filtered = filter_rows_by_text(rows, search_text)
    if currencies:
        filtered = [row for row in filtered if len(row) > 3 and row[3] in currencies]
    filtered = filter_rows_by_month(filtered, month_key)
    if tag_name and tag_name != ALL_TAGS:
        filtered = [row for row in filtered if len(row) > 4 and row[4] == tag_name]
    return filtered


def available_currencies(rows):
    return sorted({row[3] for row in rows if len(row) > 3 and row[3]})


def available_tags(rows):
    return sorted({row[4] for row in rows if len(row) > 4 and row[4]})


def kpi_stats(all_rows, filtered_rows, tags, natag="N/A"):
    totals_by_tag = Counter()
    for row in filtered_rows:
        if len(row) < 5:
            continue
        tag = row[4]
        try:
            if len(row) > 5 and row[5] == "+":
                continue
            amount = purchase_spend_amount(row[2])
            if amount is None:
                amount = parse_amount(row[2])
        except (ValueError, AttributeError):
            continue
        totals_by_tag[tag] += amount

    over_limit_tags = 0
    for tag, total in totals_by_tag.items():
        tag_info = tags.get(tag, {})
        limit = parse_amount(tag_info.get("planned_amount", tag_info.get("limit", ZERO)))
        if limit and total > limit:
            over_limit_tags += 1

    return {
        "total_rows": len(all_rows),
        "visible_rows": len(filtered_rows),
        "untagged_rows": sum(1 for row in filtered_rows if len(row) > 4 and row[4] == natag),
        "currency_count": len(available_currencies(filtered_rows)),
        "over_limit_tags": over_limit_tags,
    }


def format_totals(rows):
    totals = currency_totals(rows)
    if not totals:
        return "Totales: 0.00"
    parts = [f"{currency} {format_amount(amount)}" for currency, amount in sorted(totals.items())]
    return f"Totales: {'; '.join(parts)}"


def build_file_label(pdf_files):
    if not pdf_files:
        return "No hay archivos seleccionados"
    if len(pdf_files) == 1:
        return os.path.basename(pdf_files[0])
    return f"{len(pdf_files)} archivos seleccionados"
