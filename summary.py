#!/usr/bin/env python3
from collections import Counter
from datetime import datetime
import re


MONTH_MAP = {
    'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
}


def filter_rows_by_text(rows, text):
    text = text.lower()
    return [r for r in rows if not text or text in ' '.join(r).lower()]


def currency_totals(rows):
    totals = {}
    for row in rows:
        try:
            amount = _parse_amount(row[2])
            currency = row[3]
            totals[currency] = totals.get(currency, 0.0) + amount
        except (IndexError, TypeError, ValueError):
            pass
    return totals


def available_months(rows):
    months = set()
    for row in rows:
        try:
            month_key = month_key_from_date(row[0])
        except IndexError:
            month_key = None
        if month_key:
            months.add(month_key)
    return sorted(months)


def filter_rows_by_month(rows, month_key):
    if month_key == 'Todos':
        return list(rows)
    return [row for row in rows if row and month_key_from_date(row[0]) == month_key]


def summary_aggregates(rows, selected_currencies):
    tag_totals = Counter()
    monthly_totals = Counter()
    daily_totals = Counter()
    for date_str, _desc, amount, currency, tag in rows:
        if currency not in selected_currencies:
            continue
        try:
            amount_value = _parse_amount(amount)
        except ValueError:
            continue
        tag_totals[tag] += amount_value

        parsed_date = parse_purchase_date(date_str)
        if parsed_date:
            monthly_totals[parsed_date.strftime('%Y-%m')] += amount_value
            daily_totals[parsed_date] += amount_value

    cumulative_points = []
    running = 0.0
    for date_value in sorted(daily_totals.keys()):
        running += daily_totals[date_value]
        cumulative_points.append((date_value.strftime('%Y-%m-%d'), running))

    return {
        "tag_totals": tag_totals,
        "monthly_totals": monthly_totals,
        "daily_totals": daily_totals,
        "cumulative_points": cumulative_points,
    }


def average_spend_by_tag_month(rows, selected_currencies, limits):
    data = {}
    totals = {}

    for date_str, _desc, amount, currency, tag in rows:
        if currency not in selected_currencies:
            continue
        try:
            amount_value = _parse_amount(amount)
        except ValueError:
            continue

        parsed_date = parse_purchase_date(date_str)
        if not parsed_date:
            continue
        month_key = parsed_date.strftime('%Y-%m')
        data.setdefault((month_key, currency), {}).setdefault(tag, []).append(amount_value)

    tag_month_totals = {}
    tag_global_totals = {}
    for (month_key, currency), tag_dict in data.items():
        for tag, values in tag_dict.items():
            month_total = sum(values)
            tag_month_totals.setdefault(tag, {}).setdefault(month_key, {})[currency] = month_total
            tag_global_totals[tag] = tag_global_totals.get(tag, 0.0) + month_total
        totals.setdefault(month_key, {})[currency] = sum(sum(values) for values in tag_dict.values())

    tag_average_by_month = {}
    for tag in {tag for tag_dict in data.values() for tag in tag_dict}:
        all_values = []
        active_months = set()
        for (month_key, _currency), tag_dict in data.items():
            if tag in tag_dict:
                all_values.extend(tag_dict[tag])
                active_months.add(month_key)
        tag_average_by_month[tag] = sum(all_values) / len(active_months) if active_months else 0

    months = sorted({month_key for month_key, _currency in data.keys()})
    currencies_by_month = {
        month_key: sorted({currency for data_month, currency in data.keys() if data_month == month_key})
        for month_key in months
    }

    over_limit_by_tag = {
        tag: tag_average_by_month.get(tag, 0) > limits.get(tag, 0)
        for tag in tag_month_totals
    }
    total_limit = sum(limits.get(tag, 0) for tag in sorted(tag_month_totals))
    total_average = sum(tag_average_by_month.get(tag, 0) for tag in sorted(tag_month_totals))

    return {
        "tag_month_totals": tag_month_totals,
        "tag_global_totals": tag_global_totals,
        "tag_average_by_month": tag_average_by_month,
        "totals": totals,
        "months": months,
        "currencies_by_month": currencies_by_month,
        "over_limit_by_tag": over_limit_by_tag,
        "total_limit": total_limit,
        "total_average": total_average,
        "total_spend": sum(tag_global_totals.get(tag, 0) for tag in sorted(tag_month_totals)),
        "total_over_limit": total_average > total_limit,
    }


def parse_purchase_date(date_str):
    match = re.match(r"(\d{1,2})-([A-Z]{3})-(\d{2})", date_str)
    if not match:
        return None
    day, month, year = match.groups()
    return datetime(int('20' + year), MONTH_MAP[month], int(day))


def month_key_from_date(date_str):
    parsed_date = parse_purchase_date(date_str)
    if not parsed_date:
        return None
    return parsed_date.strftime('%Y-%m')


def _parse_amount(amount):
    return float(amount.replace(',', ''))
