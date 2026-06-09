#!/usr/bin/env python3
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import re

from money import ZERO, parse_amount


MONTH_MAP = {
    'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
}


def filter_rows_by_text(rows, text):
    text = text.lower()
    return [r for r in rows if not text or text in ' '.join(r).lower()]


def currency_totals(rows):
    totals = defaultdict(lambda: ZERO)
    for row in rows:
        try:
            amount = parse_amount(row[2])
            currency = row[3]
            totals[currency] += amount
        except (IndexError, TypeError, ValueError):
            pass
    return dict(totals)


def purchase_spend_amount(amount):
    amount_value = parse_amount(amount)
    if amount_value >= ZERO:
        return None
    return -amount_value


def purchase_rows(rows):
    scoped_rows = []
    for row in rows:
        try:
            if purchase_spend_amount(row[2]) is not None:
                scoped_rows.append(row)
        except (IndexError, TypeError, ValueError):
            pass
    return scoped_rows


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
    selected_currency = _single_selected_currency(selected_currencies)
    tag_totals = defaultdict(lambda: ZERO)
    monthly_totals = defaultdict(lambda: ZERO)
    daily_totals = defaultdict(lambda: ZERO)
    for row in rows:
        try:
            date_str, _desc, amount, currency, tag = row[:5]
        except (TypeError, ValueError):
            continue
        if currency != selected_currency:
            continue
        try:
            amount_value = purchase_spend_amount(amount)
        except (TypeError, ValueError):
            continue
        if amount_value is None:
            continue
        tag_totals[tag] += amount_value

        parsed_date = parse_purchase_date(date_str)
        if parsed_date:
            monthly_totals[parsed_date.strftime('%Y-%m')] += amount_value
            daily_totals[parsed_date] += amount_value

    cumulative_points = []
    running = ZERO
    for date_value in sorted(daily_totals.keys()):
        running += daily_totals[date_value]
        cumulative_points.append((date_value.strftime('%Y-%m-%d'), running))

    return {
        "tag_totals": tag_totals,
        "monthly_totals": monthly_totals,
        "daily_totals": daily_totals,
        "cumulative_points": cumulative_points,
    }


def average_spend_by_tag_month(rows, selected_currencies, limits, month_keys=None):
    selected_currency = _single_selected_currency(selected_currencies)
    data = {}
    totals = {}
    parsed_limits = {tag: parse_amount(limit) for tag, limit in limits.items()}

    for row in rows:
        try:
            date_str, _desc, amount, currency, tag = row[:5]
        except (TypeError, ValueError):
            continue
        if currency != selected_currency:
            continue
        try:
            amount_value = purchase_spend_amount(amount)
        except (TypeError, ValueError):
            continue
        if amount_value is None:
            continue

        parsed_date = parse_purchase_date(date_str)
        if not parsed_date:
            continue
        month_key = parsed_date.strftime('%Y-%m')
        data.setdefault((month_key, currency), {}).setdefault(tag, []).append(amount_value)

    tag_month_totals = {}
    tag_global_totals = defaultdict(lambda: ZERO)
    for (month_key, currency), tag_dict in data.items():
        for tag, values in tag_dict.items():
            month_total = sum(values, ZERO)
            tag_month_totals.setdefault(tag, {}).setdefault(month_key, {})[currency] = month_total
            tag_global_totals[tag] += month_total
        totals.setdefault(month_key, {})[currency] = sum(
            (sum(values, ZERO) for values in tag_dict.values()),
            ZERO,
        )

    months = sorted(set(month_keys)) if month_keys is not None else sorted({month_key for month_key, _currency in data.keys()})

    tag_average_by_month = {}
    for tag in {tag for tag_dict in data.values() for tag in tag_dict}:
        all_values = []
        active_months = set()
        for (month_key, _currency), tag_dict in data.items():
            if tag in tag_dict:
                all_values.extend(tag_dict[tag])
                active_months.add(month_key)
        average_months = months if month_keys is not None else active_months
        tag_average_by_month[tag] = sum(all_values, ZERO) / len(average_months) if average_months else ZERO

    if month_keys is not None:
        currencies_by_month = {month_key: [selected_currency] for month_key in months}
    else:
        currencies_by_month = {
            month_key: sorted({currency for data_month, currency in data.keys() if data_month == month_key})
            for month_key in months
        }

    over_limit_by_tag = {
        tag: tag_average_by_month.get(tag, ZERO) > parsed_limits.get(tag, ZERO)
        for tag in tag_month_totals
    }
    total_limit = sum((parsed_limits.get(tag, ZERO) for tag in sorted(tag_month_totals)), ZERO)
    total_average = sum((tag_average_by_month.get(tag, ZERO) for tag in sorted(tag_month_totals)), ZERO)

    return {
        "tag_month_totals": tag_month_totals,
        "tag_global_totals": dict(tag_global_totals),
        "tag_average_by_month": tag_average_by_month,
        "totals": totals,
        "months": months,
        "currencies_by_month": currencies_by_month,
        "over_limit_by_tag": over_limit_by_tag,
        "total_limit": total_limit,
        "total_average": total_average,
        "total_spend": sum((tag_global_totals.get(tag, ZERO) for tag in sorted(tag_month_totals)), ZERO),
        "total_over_limit": total_average > total_limit,
    }


def budget_metadata_aggregates(rows, selected_currencies, tags):
    selected_currency = _single_selected_currency(selected_currencies)
    groups = {
        "by_budget_type": defaultdict(lambda: ZERO),
        "by_parent_category": defaultdict(lambda: ZERO),
        "by_financial_purpose": defaultdict(lambda: ZERO),
    }

    for row in rows:
        try:
            _date_str, _desc, amount, currency, tag = row[:5]
        except (TypeError, ValueError):
            continue
        if currency != selected_currency:
            continue
        try:
            amount_value = purchase_spend_amount(amount)
        except (TypeError, ValueError):
            continue
        if amount_value is None:
            continue

        tag_info = tags.get(tag, {})
        groups["by_budget_type"][_metadata_label(tag_info, "budget_type")] += amount_value
        groups["by_parent_category"][_metadata_label(tag_info, "parent_category")] += amount_value
        groups["by_financial_purpose"][_metadata_label(tag_info, "financial_purpose")] += amount_value

    return {name: dict(values) for name, values in groups.items()}


def summary_insights(rows, selected_currencies, limits, month_key='Todos', natag='N/A', top_n=3):
    selected_currency = _single_selected_currency(selected_currencies)
    parsed_limits = _parse_limits(limits)
    all_currency_rows = []

    for row in rows:
        parsed_row = _parse_insight_row(row, selected_currency)
        if parsed_row:
            all_currency_rows.append(parsed_row)

    if month_key == 'Todos':
        scoped_rows = list(all_currency_rows)
    else:
        scoped_rows = [row for row in all_currency_rows if row["month_key"] == month_key]

    total_spend = sum((row["amount"] for row in scoped_rows), ZERO)
    tag_totals = defaultdict(lambda: ZERO)
    for row in scoped_rows:
        tag_totals[row["tag"]] += row["amount"]

    top_tags = sorted(tag_totals.items(), key=lambda item: (-item[1], item[0]))[:top_n]
    largest_purchases = [
        row["source"]
        for row in sorted(scoped_rows, key=lambda item: item["amount"], reverse=True)[:top_n]
    ]
    over_limit_tags = _over_limit_tags(tag_totals, parsed_limits)
    comparison = _month_comparison(all_currency_rows, month_key)

    return {
        "total_spend": total_spend,
        "purchase_count": len(scoped_rows),
        "top_tags": top_tags,
        "over_limit_tags": over_limit_tags,
        "largest_purchases": largest_purchases,
        "comparison": comparison,
        "headline": _insight_headline(top_tags, over_limit_tags, selected_currency),
        "detail": _insight_detail(total_spend, len(scoped_rows), top_tags, over_limit_tags, selected_currency),
        "messages": _insight_messages(total_spend, len(scoped_rows), top_tags, over_limit_tags, comparison, natag),
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


def _single_selected_currency(selected_currencies):
    currencies = sorted(selected_currencies or [])
    if len(currencies) != 1:
        raise ValueError("summary calculations require exactly one selected currency")
    return currencies[0]


def _metadata_label(tag_info, field):
    value = tag_info.get(field)
    if not value:
        return "Sin clasificar"
    return value


def _parse_limits(limits):
    parsed_limits = {}
    for tag, limit in limits.items():
        try:
            parsed_limits[tag] = parse_amount(limit)
        except (TypeError, ValueError):
            parsed_limits[tag] = ZERO
    return parsed_limits


def _parse_insight_row(row, selected_currency):
    try:
        date_str, description, amount, currency, tag = row[:5]
    except (TypeError, ValueError):
        return None
    if currency != selected_currency:
        return None
    try:
        amount_value = purchase_spend_amount(amount)
    except (TypeError, ValueError):
        return None
    if amount_value is None:
        return None

    return {
        "source": row,
        "date": _safe_purchase_date(date_str),
        "month_key": _safe_month_key(date_str),
        "description": description,
        "amount": amount_value,
        "currency": currency,
        "tag": tag,
    }


def _safe_purchase_date(date_str):
    try:
        return parse_purchase_date(date_str)
    except (TypeError, ValueError, KeyError):
        return None


def _safe_month_key(date_str):
    parsed_date = _safe_purchase_date(date_str)
    if not parsed_date:
        return None
    return parsed_date.strftime('%Y-%m')


def _over_limit_tags(tag_totals, parsed_limits):
    over_limit = []
    for tag, total in tag_totals.items():
        limit = parsed_limits.get(tag, ZERO)
        if limit and total > limit:
            over_limit.append((tag, total, limit))
    return sorted(over_limit, key=lambda item: (-(item[1] - item[2]), item[0]))


def _month_comparison(rows, month_key):
    monthly_totals = defaultdict(lambda: ZERO)
    for row in rows:
        if row["month_key"]:
            monthly_totals[row["month_key"]] += row["amount"]
    if not monthly_totals:
        return None

    current_month = max(monthly_totals) if month_key == 'Todos' else month_key
    previous_month = _previous_month_key(current_month)
    current_total = monthly_totals.get(current_month, ZERO)
    previous_total = monthly_totals.get(previous_month, ZERO)
    if current_total == ZERO and previous_total == ZERO:
        return None

    delta = current_total - previous_total
    percent_change = ZERO
    if previous_total:
        percent_change = ((delta / previous_total) * Decimal("100")).quantize(Decimal("0.01"), ROUND_HALF_UP)

    return {
        "current_month": current_month,
        "previous_month": previous_month,
        "current_total": current_total,
        "previous_total": previous_total,
        "delta": delta,
        "percent_change": percent_change,
    }


def _previous_month_key(month_key):
    year, month = (int(part) for part in month_key.split("-"))
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def _insight_messages(total_spend, purchase_count, top_tags, over_limit_tags, comparison, natag):
    purchase_label = "compra" if purchase_count == 1 else "compras"
    messages = [f"El gasto total es {format_insight_amount(total_spend)} en {purchase_count} {purchase_label}."]
    if top_tags:
        tag, amount = top_tags[0]
        if tag != natag:
            messages.append(f"{tag} es la etiqueta con mayor gasto: {format_insight_amount(amount)}.")
    for tag, total, limit in over_limit_tags[:2]:
        messages.append(f"{tag} supera su presupuesto por {format_insight_amount(total - limit)}.")
    if comparison:
        delta = comparison["delta"]
        if delta > ZERO:
            direction = "más que"
            amount = delta
        elif delta < ZERO:
            direction = "menos que"
            amount = -delta
        else:
            direction = "igual que"
            amount = ZERO
        messages.append(
            f"El gasto de {comparison['current_month']} es {format_insight_amount(amount)} "
            f"{direction} {comparison['previous_month']}."
        )
    return messages[:4]


def _insight_headline(top_tags, over_limit_tags, currency):
    if over_limit_tags:
        tag, total, limit = over_limit_tags[0]
        return f"{tag} supera su presupuesto por {currency} {format_insight_amount(total - limit)}."
    if top_tags:
        tag, _amount = top_tags[0]
        return f"{tag} concentra el gasto de este periodo."
    return "No hay hallazgos principales para esta selección."


def _insight_detail(total_spend, purchase_count, top_tags, over_limit_tags, currency):
    details = []
    if top_tags and total_spend:
        tag, amount = top_tags[0]
        percent = ((amount / total_spend) * Decimal("100")).quantize(Decimal("0.1"), ROUND_HALF_UP)
        details.append(f"{tag} representa el {percent}% del gasto.")
    if len(over_limit_tags) > 1:
        tag, total, limit = over_limit_tags[1]
        details.append(f"{tag} también supera el presupuesto por {currency} {format_insight_amount(total - limit)}.")
    purchase_label = "compra" if purchase_count == 1 else "compras"
    details.append(
        f"El gasto total es {currency} {format_insight_amount(total_spend)} en {purchase_count} {purchase_label}."
    )
    return "\n".join(f"- {detail}" for detail in details)


def format_insight_amount(amount):
    return f"{amount:,.2f}"
