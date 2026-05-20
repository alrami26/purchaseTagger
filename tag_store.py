#!/usr/bin/env python3
import json
import sys
from pathlib import Path


TAG_FILENAME = 'tags.json'


def default_tag_file_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent / TAG_FILENAME
    return Path(__file__).resolve().parent / TAG_FILENAME


TAG_FILE = default_tag_file_path()


def load_tags(path=TAG_FILE):
    """
    Carga tags desde JSON, migrando el formato antiguo (lista de keywords)
    al nuevo: { tag: { "keywords": [...], "limit": int } }.
    """
    path = Path(path)
    if not path.exists():
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    migrated = {}
    for tag, v in data.items():
        if isinstance(v, list):
            migrated[tag] = {"keywords": v, "limit": 0}
        else:
            migrated[tag] = {
                "keywords": v.get("keywords", []),
                "limit": v.get("limit", 0)
            }
    return migrated


def save_tags(tags, path=TAG_FILE):
    path = Path(path)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(tags, f, indent=2)


def tag_purchase(description, tags, natag='N/A'):
    desc_upper = description.upper()
    for tag, info in tags.items():
        for kw in info["keywords"]:
            if kw.upper() in desc_upper:
                return tag
    return natag
