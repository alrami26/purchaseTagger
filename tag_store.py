#!/usr/bin/env python3
import json
import os
import shutil
import sys
import tempfile
from decimal import Decimal
from pathlib import Path


TAG_FILENAME = 'tags.json'
APP_NAME = 'PurchaseTagger'
BUDGET_TYPES = ("Expense", "Savings", "Debt", "Donation", "Investment", "Income")
BUDGET_PERIODS = ("monthly", "annual", "weekly", "one-time")
EXPENSE_NATURES = ("fixed", "variable")
FINANCIAL_PURPOSES = ("Necesidad", "Deseo", "Ahorro/Inversión", "Compromiso")
DEFAULT_PARENT_CATEGORY = "Sin clasificar"
TAG_METADATA_FIELDS = (
    "budget_type",
    "parent_category",
    "budget_period",
    "planned_amount",
    "expense_nature",
    "financial_purpose",
)


def default_tag_file_path():
    if getattr(sys, 'frozen', False):
        return _user_config_dir() / TAG_FILENAME
    return _source_tag_file_path()

def load_tags(path=None):
    """
    Carga tags desde JSON, migrando el formato antiguo (lista de keywords)
    al formato enriquecido de presupuesto.
    """
    custom_path = path is not None
    path = _resolve_tag_file_path(path)
    if not path.exists():
        if not custom_path:
            _copy_bundled_default_tags(path)
        if not path.exists():
            save_tags({}, path)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return _validate_and_migrate_tags(data, path=path)


def save_tags(tags, path=None):
    path = _resolve_tag_file_path(path)
    validated = _validate_and_migrate_tags(tags, path=path, allow_decimal=True)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = None
    with tempfile.NamedTemporaryFile(
        'w',
        encoding='utf-8',
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as f:
        tmp_path = Path(f.name)
        json.dump(validated, f, indent=2, default=_json_default)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())

    if path.exists():
        shutil.copy2(path, _backup_path(path))

    try:
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
        raise


def merge_tags(current_tags, imported_tags):
    current = _validate_and_migrate_tags(current_tags, allow_decimal=True)
    imported = _validate_and_migrate_tags(imported_tags, allow_decimal=True)
    merged = {tag: _copy_tag_info(info) for tag, info in current.items()}
    counts = {"tags_added": 0, "keywords_added": 0, "limits_updated": 0, "metadata_updated": 0}

    for tag, info in imported.items():
        imported_keywords = list(info.get("keywords", []))
        if tag not in merged:
            merged[tag] = _copy_tag_info(info)
            counts["tags_added"] += 1
            counts["keywords_added"] += len(imported_keywords)
            continue

        existing_keywords = merged[tag].setdefault("keywords", [])
        for keyword in imported_keywords:
            if keyword not in existing_keywords:
                existing_keywords.append(keyword)
                counts["keywords_added"] += 1

        imported_limit = info.get("planned_amount", info.get("limit", 0))
        if merged[tag].get("planned_amount", merged[tag].get("limit", 0)) != imported_limit:
            counts["limits_updated"] += 1
        merged[tag]["limit"] = imported_limit
        merged[tag]["planned_amount"] = imported_limit

        for field in TAG_METADATA_FIELDS:
            if field == "planned_amount":
                continue
            if merged[tag].get(field) != info.get(field):
                counts["metadata_updated"] += 1
                merged[tag][field] = info.get(field)

    return merged, counts


def default_tag_info(tag, keywords=None, planned_amount=0):
    return _default_tag_info(tag, keywords=keywords, planned_amount=planned_amount)


def _backup_path(path):
    return path.with_suffix(path.suffix + ".bak")


def _resolve_tag_file_path(path):
    return default_tag_file_path() if path is None else Path(path)


def _source_tag_file_path():
    return Path(__file__).resolve().parent / TAG_FILENAME


def _user_config_dir():
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".config" / APP_NAME


def _copy_bundled_default_tags(target_path):
    if not getattr(sys, 'frozen', False):
        return
    bundled_path = _bundled_default_tag_file_path(target_path)
    if bundled_path is None:
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bundled_path, target_path)


def _bundled_default_tag_file_path(target_path):
    candidates = []
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(Path(meipass) / TAG_FILENAME)
    executable = getattr(sys, 'executable', None)
    if executable:
        candidates.append(Path(executable).resolve().parent / TAG_FILENAME)
    candidates.append(_source_tag_file_path())

    target_path = target_path.resolve()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate.exists() and candidate != target_path:
            return candidate
    return None


TAG_FILE = default_tag_file_path()


def _validate_and_migrate_tags(data, path=None, allow_decimal=False):
    if path is None:
        path = default_tag_file_path()
    if not isinstance(data, dict):
        _raise_invalid(path, "expected an object mapping tag names to tag settings")

    migrated = {}
    for tag, value in data.items():
        if not isinstance(tag, str) or not tag:
            _raise_invalid(path, "tag names must be non-empty strings")

        if isinstance(value, list):
            keywords = _validate_keywords(value, path, tag)
            migrated[tag] = _default_tag_info(tag, keywords=keywords)
            continue

        if not isinstance(value, dict):
            _raise_invalid(path, f"tag {tag!r} must be an object or a keyword list")

        keywords = _validate_keywords(value.get("keywords", []), path, tag)
        planned_amount = value.get("planned_amount", value.get("limit", 0))
        if not _is_number(planned_amount, allow_decimal=allow_decimal):
            _raise_invalid(path, f"tag {tag!r} planned_amount must be a number")

        limit = value.get("limit", planned_amount)
        if not _is_number(limit, allow_decimal=allow_decimal):
            _raise_invalid(path, f"tag {tag!r} limit must be a number")

        migrated[tag] = {
            "keywords": keywords,
            "limit": planned_amount,
            "budget_type": _validate_choice(
                value.get("budget_type", "Expense"),
                BUDGET_TYPES,
                path,
                tag,
                "budget_type",
            ),
            "parent_category": _validate_string(
                _normalized_parent_category(value.get("parent_category", DEFAULT_PARENT_CATEGORY), tag),
                path,
                tag,
                "parent_category",
            ),
            "budget_period": _validate_choice(
                value.get("budget_period", "monthly"),
                BUDGET_PERIODS,
                path,
                tag,
                "budget_period",
            ),
            "planned_amount": planned_amount,
            "expense_nature": _validate_nullable_choice(
                value.get("expense_nature"),
                EXPENSE_NATURES,
                path,
                tag,
                "expense_nature",
            ),
            "financial_purpose": _validate_nullable_choice(
                value.get("financial_purpose"),
                FINANCIAL_PURPOSES,
                path,
                tag,
                "financial_purpose",
            ),
        }
    return migrated


def _default_tag_info(tag, keywords=None, planned_amount=0):
    return {
        "keywords": list(keywords or []),
        "limit": planned_amount,
        "budget_type": "Expense",
        "parent_category": DEFAULT_PARENT_CATEGORY,
        "budget_period": "monthly",
        "planned_amount": planned_amount,
        "expense_nature": None,
        "financial_purpose": None,
    }


def _copy_tag_info(info):
    copied = {field: info.get(field) for field in ("limit", *TAG_METADATA_FIELDS)}
    copied["keywords"] = list(info.get("keywords", []))
    return {
        "keywords": copied["keywords"],
        "limit": copied["limit"],
        "budget_type": copied["budget_type"],
        "parent_category": copied["parent_category"],
        "budget_period": copied["budget_period"],
        "planned_amount": copied["planned_amount"],
        "expense_nature": copied["expense_nature"],
        "financial_purpose": copied["financial_purpose"],
    }


def _normalized_parent_category(value, tag):
    if not isinstance(value, str):
        return value
    parent_category = value.strip()
    if not parent_category or parent_category == tag:
        return DEFAULT_PARENT_CATEGORY
    return parent_category


def _validate_keywords(keywords, path, tag):
    if not isinstance(keywords, list):
        _raise_invalid(path, f"tag {tag!r} keywords must be a list")
    if not all(isinstance(keyword, str) for keyword in keywords):
        _raise_invalid(path, f"tag {tag!r} keywords must contain only strings")
    return keywords


def _is_number(value, allow_decimal=False):
    allowed = (int, float)
    if allow_decimal:
        allowed = allowed + (Decimal,)
    return isinstance(value, allowed) and not isinstance(value, bool)


def _validate_string(value, path, tag, field):
    if not isinstance(value, str):
        _raise_invalid(path, f"tag {tag!r} {field} must be a string")
    return value


def _validate_choice(value, choices, path, tag, field):
    if value not in choices:
        _raise_invalid(path, f"tag {tag!r} {field} must be one of {', '.join(choices)}")
    return value


def _validate_nullable_choice(value, choices, path, tag, field):
    if value is None:
        return None
    return _validate_choice(value, choices, path, tag, field)


def _raise_invalid(path, message):
    raise ValueError(f"Invalid tags.json at {Path(path)}: {message}")


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def tag_purchase(description, tags, natag='N/A'):
    desc_upper = description.upper()
    for tag, info in tags.items():
        for kw in info["keywords"]:
            if kw.upper() in desc_upper:
                return tag
    return natag
