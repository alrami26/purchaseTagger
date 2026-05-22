#!/usr/bin/env python3
from datetime import datetime
import re
from pypdf import PdfReader
from tag_store import load_tags, tag_purchase

MONTH_NUMBERS = {
    "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DIC": 12,
}

MONTH_RE = r"ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC"
PURCHASE_SECTION_MARKERS = (
    "Purchases Made",
    "Purchase Activity",
    "Compras Realizadas",
    "Detalle de Compras",
)
PURCHASE_SECTION_END_MARKERS = (
    "Interest Charges",
    "Cargos por Intereses",
    "Intereses",
)
TRANSACTION_START_RE = re.compile(
    rf"^(?:\d+\s+)?\d{{1,2}}-(?:{MONTH_RE})-\d{{2}}\b",
    re.IGNORECASE,
)
TRANSACTION_LINE_RE = re.compile(
    rf"^(?:\d+\s+)?"
    rf"(\d{{1,2}}-(?:{MONTH_RE})-\d{{2}})\s+"
    rf"(.+?)\s+"
    rf"([A-Z]{{3}})\s+"
    rf"(-?[\d,]+\.[0-9]{{2}}|\([\d,]+\.[0-9]{{2}}\))$",
    re.IGNORECASE,
)


def normalize_purchase_date(date_str):
    m = re.match(r'(\d{1,2})-([A-Z]{3})-(\d{2})$', date_str.upper())
    if not m:
        return None

    d, mon, yy = m.groups()
    try:
        datetime(2000 + int(yy), MONTH_NUMBERS[mon], int(d))
    except (KeyError, ValueError):
        return None

    return f"{int(d):02d}-{mon}-{yy}"


def extract_text(pdf_path):
    """
    Extrae todo el texto de un PDF.
    """
    reader = PdfReader(pdf_path)
    texts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.append(text)
    return "\n".join(texts)


def _line_has_marker(line, markers):
    folded = line.casefold()
    return any(marker.casefold() in folded for marker in markers)


def _purchase_section_lines(full_text):
    lines = full_text.splitlines()
    start_index = None
    for i, line in enumerate(lines):
        if _line_has_marker(line, PURCHASE_SECTION_MARKERS):
            start_index = i + 1
            break

    if start_index is None:
        return lines

    end_index = len(lines)
    for i in range(start_index, len(lines)):
        if _line_has_marker(lines[i], PURCHASE_SECTION_END_MARKERS):
            end_index = i
            break
    return lines[start_index:end_index]


def _parse_purchase_line(line):
    m = TRANSACTION_LINE_RE.match(line)
    if not m:
        return None
    date_str, desc, cur, amt = m.groups()

    date_str = normalize_purchase_date(date_str)
    if date_str is None:
        return None

    if amt.startswith("(") and amt.endswith(")"):
        amt = f"-{amt[1:-1]}"

    return (date_str, " ".join(desc.split()), amt.replace(',', ''), cur.upper())


def _logical_purchase_lines(lines):
    pending = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if TRANSACTION_START_RE.match(line):
            if pending is not None:
                yield pending
            pending = line
        elif pending is not None:
            pending = f"{pending} {line}"
        else:
            pending = line

        if _parse_purchase_line(pending):
            yield pending
            pending = None

    if pending is not None:
        yield pending


def extract_purchases(full_text):
    """
    Parsea lineas de compras del texto completo extraido.
    Devuelve lista de tuplas (date, description, amount, currency).
    - ID inicial opcional
    - Dia de 1 o 2 digitos
    - Normaliza la fecha a DD-MMM-YY
    """
    purchases = []
    for line in _logical_purchase_lines(_purchase_section_lines(full_text)):
        purchase = _parse_purchase_line(line)
        if purchase is None:
            continue
        purchases.append(purchase)
    return purchases


def process_purchases(pdf_path):
    """
    Procesa un PDF y devuelve lista de tuplas:
    (date, description, amount, currency, tag, limit)
    """
    full_text = extract_text(pdf_path)
    raw = extract_purchases(full_text)
    tags = load_tags()
    purchases = []
    for date, desc, amt, cur in raw:
        tag = tag_purchase(desc, tags)
        limit = tags.get(tag, {}).get("limit", 0)
        purchases.append((date, desc, amt, cur, tag, limit))
    return purchases
