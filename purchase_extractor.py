#!/usr/bin/env python3
from datetime import datetime
from decimal import Decimal
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
MONTH_NAMES = {number: name for name, number in MONTH_NUMBERS.items()}

MONTH_RE = r"ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC"
DEBIT_STATEMENT_MONTH_RE = r"ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC"
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
BANK_BAC = "BAC"
BANK_PROMERICA = "Promerica"
ACCOUNT_TYPE_CREDIT = "Credito"
ACCOUNT_TYPE_DEBIT = "Debito"
SUPPORTED_BANKS = (BANK_BAC, BANK_PROMERICA)
SUPPORTED_ACCOUNT_TYPES = (ACCOUNT_TYPE_CREDIT, ACCOUNT_TYPE_DEBIT)
SUPPORTED_ACCOUNT_TYPES_BY_BANK = {
    BANK_BAC: (ACCOUNT_TYPE_CREDIT, ACCOUNT_TYPE_DEBIT),
    BANK_PROMERICA: (ACCOUNT_TYPE_CREDIT,),
}
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
BAC_DEBIT_LINE_RE = re.compile(
    rf"^\s*\d{{6,}}\s+({DEBIT_STATEMENT_MONTH_RE})/(\d{{1,2}})\s+(.+?)\s+"
    rf"(-?[\d,]+\.[0-9]{{2}}|\([\d,]+\.[0-9]{{2}}\))\s*$",
    re.IGNORECASE,
)
BAC_DEBIT_CUTOFF_RE = re.compile(
    rf"\b(\d{{1,2}})/({DEBIT_STATEMENT_MONTH_RE})/(\d{{2}})\b",
    re.IGNORECASE,
)
BAC_DEBIT_CURRENCIES = {
    "COLONES": "CRC",
    "DOLARES": "USD",
    "DÓLARES": "USD",
}
BAC_CREDIT_PAYMENT_DATE_RE = re.compile(
    rf"^\s*\d{{6,}}\s+(\d{{1,2}}-(?:{MONTH_RE})-\d{{2}})\s+",
    re.IGNORECASE,
)
BAC_CREDIT_AMOUNT_RE = re.compile(
    r"-?\s*[\d,]+\.[0-9]{2}-?|\([\d,]+\.[0-9]{2}\)"
)
PROMERICA_CUTOFF_RE = re.compile(r"\bFecha de Corte\s+(\d{2})/(\d{2})/(\d{4})", re.IGNORECASE)
PROMERICA_DATE_RE = re.compile(r"^\s*(\d{2})/(\d{2})/(\d{4})\b")
PROMERICA_AMOUNT_COLUMNS_RE = re.compile(
    r"(-?\s*[\d,]+\.[0-9]{2})\s+(-?\s*[\d,]+\.[0-9]{2})\s*$"
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


def normalize_numeric_date(day, month, year):
    try:
        date = datetime(int(year), int(month), int(day))
    except ValueError:
        return None
    return f"{date.day:02d}-{MONTH_NAMES[date.month]}-{date.year % 100:02d}"


def extract_text(pdf_path, layout=False):
    """
    Extrae todo el texto de un PDF.
    """
    reader = PdfReader(pdf_path)
    texts = []
    for page in reader.pages:
        if layout:
            text = page.extract_text(extraction_mode="layout")
        else:
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


def _invert_signed_amount(amount):
    normalized = _normalize_signed_amount(amount)
    return f"{-Decimal(normalized):.2f}"


def _bac_credit_payment_columns(header_line):
    columns = []
    transaction_index = 0
    interest_index = 0
    for match in re.finditer(r"Transacción|Interés", header_line, re.IGNORECASE):
        label = match.group(0).casefold()
        if label == "transacción":
            currency = "CRC" if transaction_index == 0 else "USD"
            transaction_index += 1
            columns.append((match.start(), "transaction", currency))
        else:
            currency = "CRC" if interest_index == 0 else "USD"
            interest_index += 1
            columns.append((match.start(), "interest", currency))
    return columns


def _bac_credit_payment_column(amount_start, columns):
    preceding_columns = [column for column in columns if amount_start >= column[0]]
    if not preceding_columns:
        return None
    return preceding_columns[-1]


def _amount_value_start(amount_match):
    amount_text = amount_match.group(0)
    return amount_match.start() + len(amount_text) - len(amount_text.lstrip())


def _parse_bac_credit_payment_line(line, columns):
    date_match = BAC_CREDIT_PAYMENT_DATE_RE.match(line)
    if not date_match:
        return []

    selected_amounts = []
    for amount_match in BAC_CREDIT_AMOUNT_RE.finditer(line, date_match.end()):
        amount_start = _amount_value_start(amount_match)
        column = _bac_credit_payment_column(amount_start, columns)
        if column is None:
            continue
        _column_start, column_type, currency = column
        if column_type != "transaction":
            continue

        amount = _normalize_signed_amount(amount_match.group(0), "+")
        if Decimal(amount) != 0:
            selected_amounts.append((amount_start, amount, currency))

    if not selected_amounts:
        return []

    date_str = normalize_purchase_date(date_match.group(1))
    if date_str is None:
        return []

    first_amount_start = selected_amounts[0][0]
    desc = " ".join(line[date_match.end():first_amount_start].split())
    if not desc:
        return []

    return [(date_str, desc, amount, currency) for _amount_start, amount, currency in selected_amounts]


def extract_bac_credit_payments(full_text):
    in_payment_section = False
    columns = []
    payments = []

    for line in full_text.splitlines():
        folded = line.casefold()
        if "detalle de pago del periodo" in folded:
            in_payment_section = True
            continue
        if in_payment_section and "detalle de compras del periodo" in folded:
            break
        if not in_payment_section:
            continue

        if "n. referencia" in folded and "transacción" in folded and "interés" in folded:
            columns = _bac_credit_payment_columns(line)
            continue
        if not columns:
            continue

        payments.extend(_parse_bac_credit_payment_line(line, columns))

    return payments


def extract_bac_credit_movements(full_text):
    movements = extract_bac_credit_payments(full_text)
    for date_str, desc, amount, currency in extract_purchases(full_text):
        movements.append((date_str, desc, _invert_signed_amount(amount), currency))
    return movements


def _bac_debit_currency(full_text):
    m = re.search(r"\bMoneda:\s*([A-ZÁÉÍÓÚ]+)", full_text, re.IGNORECASE)
    if not m:
        return "CRC"
    name = m.group(1).upper()
    return BAC_DEBIT_CURRENCIES.get(name, name[:3])


def _bac_debit_cutoff_year(full_text):
    matches = BAC_DEBIT_CUTOFF_RE.findall(full_text)
    if not matches:
        return None
    _, month, year = matches[-1]
    return MONTH_NUMBERS[month.upper()], int(year)


def _normalize_bac_debit_date(month, day, cutoff):
    if cutoff is None:
        return None

    month = month.upper()
    try:
        day_number = int(day)
        month_number = MONTH_NUMBERS[month]
    except (KeyError, ValueError):
        return None

    cutoff_month, cutoff_year = cutoff
    year = cutoff_year - 1 if month_number > cutoff_month else cutoff_year

    try:
        datetime(2000 + year, month_number, day_number)
    except ValueError:
        return None
    return f"{day_number:02d}-{month}-{year:02d}"


def _bac_debit_amount_direction(amount_start, debit_col, credit_col):
    if amount_start >= debit_col and amount_start < credit_col:
        return "-"
    if amount_start >= credit_col:
        return "+"
    return None


def _normalize_signed_amount(amount, direction=None):
    normalized = amount.strip().replace(" ", "").replace(",", "")
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    elif normalized.endswith("-"):
        normalized = f"-{normalized[:-1]}"

    value = Decimal(normalized)
    if direction == "-":
        value = -abs(value)
    elif direction == "+":
        value = abs(value)
    return f"{value:.2f}"


def extract_bac_debit_movements(full_text):
    currency = _bac_debit_currency(full_text)
    cutoff = _bac_debit_cutoff_year(full_text)
    lines = full_text.splitlines()
    debit_col = credit_col = None
    movements = []

    for line in lines:
        if "NO. REFERENCIA" in line and "DÉBITOS" in line and "CRÉDITOS" in line:
            debit_col = line.find("DÉBITOS")
            credit_col = line.find("CRÉDITOS")
            continue
        if debit_col is None or credit_col is None:
            continue
        if "ÚLTIMA LÍNEA" in line:
            break

        match = BAC_DEBIT_LINE_RE.match(line)
        if not match:
            continue

        month, day, desc, amount = match.groups()
        amount_start = line.rfind(amount)
        direction = _bac_debit_amount_direction(amount_start, debit_col, credit_col)
        if direction is None:
            continue

        date_str = _normalize_bac_debit_date(month, day, cutoff)
        if date_str is None:
            continue

        movements.append((date_str, " ".join(desc.split()), _normalize_signed_amount(amount, direction), currency))

    return movements


def _normalize_amount(amount):
    return _normalize_signed_amount(amount)


def _non_zero_promerica_amounts(crc_amount, usd_amount, normalize=_normalize_amount):
    amounts = []
    for currency, amount in (("CRC", crc_amount), ("USD", usd_amount)):
        normalized = normalize(amount)
        if Decimal(normalized) != 0:
            amounts.append((normalized, currency))
    return amounts


PROMERICA_ANY_AMOUNT_RE = re.compile(r"-?\s*[\d,]+\.[0-9]{2}")


def _promerica_payment_amounts_from_line(line, date_end):
    amount_matches = list(PROMERICA_ANY_AMOUNT_RE.finditer(line, date_end))
    if not amount_matches:
        return None

    if len(amount_matches) >= 4:
        selected_matches = (amount_matches[-4], amount_matches[-2])
    elif len(amount_matches) >= 2:
        selected_matches = (amount_matches[-2], amount_matches[-1])
    else:
        return None

    amounts = []
    for currency, amount_match in (("CRC", selected_matches[0]), ("USD", selected_matches[1])):
        amount = _normalize_signed_amount(amount_match.group(0), "+")
        if Decimal(amount) != 0:
            amounts.append((amount, currency))
    if not amounts:
        return None
    return selected_matches[0], amounts


def _promerica_cutoff_date(full_text):
    match = PROMERICA_CUTOFF_RE.search(full_text)
    if not match:
        return None
    day, month, year = match.groups()
    return normalize_numeric_date(day, month, year)


def _promerica_description_from_dated_line(line, date_end, amount_start):
    rest = line[date_end:amount_start].strip()
    movement = re.match(r"(.+)\s{2,}\S(?:.*\S)?\s{2,}[A-Z]{2,3}$", rest)
    if movement:
        rest = movement.group(1)
    return " ".join(rest.split())


def _promerica_section(line, current_section):
    folded = line.casefold()
    if "detalle de pagos del periodo" in folded:
        return "payments"
    if "detalle de compras del periodo" in folded:
        return "purchases"
    if "detalle de intereses" in folded:
        return "interest"
    if (
        "detalle de otros cargos" in folded
        or "detalle de productos y servicios" in folded
        or "cargos por gestión" in folded
    ):
        return "charges"
    return current_section


def _is_promerica_total_or_header(line):
    folded = line.casefold().strip()
    if not folded:
        return True
    return (
        folded.startswith("total ")
        or folded.startswith("fecha ")
        or folded.startswith("concepto ")
        or "total por concepto" in folded
        or "total de compras" in folded
        or "total cargos" in folded
        or "monto en" in folded
        or "lugar / moneda" in folded
    )


def _promerica_amounts_from_line(line, normalize=_normalize_amount):
    match = PROMERICA_AMOUNT_COLUMNS_RE.search(line)
    if not match:
        return None
    amounts = _non_zero_promerica_amounts(match.group(1), match.group(2), normalize=normalize)
    if not amounts:
        return None
    return match, amounts


def _parse_promerica_dated_line(line):
    date_match = PROMERICA_DATE_RE.match(line)
    if not date_match:
        return []

    amount_info = _promerica_amounts_from_line(line, normalize=_invert_signed_amount)
    if not amount_info:
        return []
    amount_match, amounts = amount_info

    date_str = normalize_numeric_date(*date_match.groups())
    if date_str is None:
        return []

    desc = _promerica_description_from_dated_line(line, date_match.end(), amount_match.start())
    if not desc or _is_promerica_total_or_header(desc):
        return []

    return [(date_str, desc, amount, currency) for amount, currency in amounts]


def _parse_promerica_payment_line(line):
    date_match = PROMERICA_DATE_RE.match(line)
    if not date_match:
        return []

    amount_info = _promerica_payment_amounts_from_line(line, date_match.end())
    if not amount_info:
        return []
    first_amount_match, amounts = amount_info

    date_str = normalize_numeric_date(*date_match.groups())
    if date_str is None:
        return []

    desc = " ".join(line[date_match.end():first_amount_match.start()].split())
    if not desc or _is_promerica_total_or_header(desc):
        return []

    return [(date_str, desc, amount, currency) for amount, currency in amounts]


def _parse_promerica_interest_line(line, cutoff_date):
    if cutoff_date is None or _is_promerica_total_or_header(line):
        return []

    amount_info = _promerica_amounts_from_line(line, normalize=_invert_signed_amount)
    if not amount_info:
        return []
    amount_match, amounts = amount_info

    desc = " ".join(line[:amount_match.start()].split())
    if not desc:
        return []

    return [(cutoff_date, desc, amount, currency) for amount, currency in amounts]


def extract_promerica_credit_movements(full_text):
    cutoff_date = _promerica_cutoff_date(full_text)
    section = None
    movements = []

    for line in full_text.splitlines():
        section = _promerica_section(line, section)
        if section is None:
            continue
        if section == "payments":
            movements.extend(_parse_promerica_payment_line(line))
        if section in ("purchases", "charges"):
            movements.extend(_parse_promerica_dated_line(line))
        elif section == "interest":
            movements.extend(_parse_promerica_interest_line(line, cutoff_date))

    return movements


PARSER_REGISTRY = {
    (BANK_BAC, ACCOUNT_TYPE_CREDIT): (extract_bac_credit_movements, True),
    (BANK_BAC, ACCOUNT_TYPE_DEBIT): (extract_bac_debit_movements, True),
    (BANK_PROMERICA, ACCOUNT_TYPE_CREDIT): (extract_promerica_credit_movements, True),
}


def process_purchases(pdf_path, bank=BANK_BAC, account_type=ACCOUNT_TYPE_CREDIT):
    """
    Procesa un PDF y devuelve lista de tuplas:
    (date, description, amount, currency, tag, limit)
    """
    parser_config = PARSER_REGISTRY.get((bank, account_type))
    if parser_config is None:
        if bank not in SUPPORTED_BANKS:
            raise ValueError(f"Unsupported bank: {bank}")
        if account_type not in SUPPORTED_ACCOUNT_TYPES:
            raise ValueError(f"Unsupported account type: {account_type}")
        raise ValueError(f"Unsupported bank/account type: {bank} {account_type}")

    parser, layout = parser_config
    full_text = extract_text(pdf_path, layout=layout)
    raw = parser(full_text)
    tags = load_tags()
    purchases = []
    for date, desc, amt, cur in raw:
        tag = tag_purchase(desc, tags)
        limit = tags.get(tag, {}).get("limit", 0)
        purchases.append((date, desc, amt, cur, tag, limit))
    return purchases
