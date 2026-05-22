#!/usr/bin/env python3
from decimal import Decimal, InvalidOperation


CENT = Decimal("0.01")
ZERO = Decimal("0")


def parse_amount(value):
    if isinstance(value, Decimal):
        return value
    if value is None:
        raise ValueError("amount is required")
    text = str(value).strip().replace(",", "")
    if not text:
        raise ValueError("amount is required")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount: {value}") from exc


def format_amount(value):
    return f"{parse_amount(value).quantize(CENT):,.2f}"
