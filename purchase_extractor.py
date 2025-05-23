#!/usr/bin/env python3
import json
import os
import re
from pypdf import PdfReader

TAG_FILE = 'tags.json'

def load_tags(path=TAG_FILE):
    """
    Carga tags desde JSON, migrando el formato antiguo (lista de keywords)
    al nuevo: { tag: { "keywords": [...], "limit": <int> } }.
    """
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Migración de formato antiguo a nuevo
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

def extract_purchases(full_text):
    """
    Parsea líneas de compras del texto completo extraído.
    Devuelve lista de tuplas (date, description, amount, currency).
    """
    line_re = re.compile(
        r'^\d+\s+'                                   # transaction ID
        r'(\d{2}-(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)-\d{2})\s+'
        r'(.+?)\s+'                                   # descripción
        r'([A-Z]{3})\s+'                              # código de moneda
        r'([\d,]+\.[0-9]{2})$'                       # importe
    )
    try:
        sect = full_text.split("Purchases Made", 1)[1]
        sect = sect.split("Interest Charges", 1)[0]
    except IndexError:
        sect = full_text
    purchases = []
    for line in sect.splitlines():
        match = line_re.match(line.strip())
        if match:
            date, desc, cur, amt = match.groups()
            purchases.append((date, desc.strip(), amt.replace(',', ''), cur))
    return purchases

def tag_purchase(description, tags, natag='N/A'):
    """
    Asigna un tag según keywords en tags[tag]["keywords"].
    """
    desc_upper = description.upper()
    for tag, info in tags.items():
        for kw in info["keywords"]:
            if kw.upper() in desc_upper:
                return tag
    return natag

def process_purchases(pdf_path):
    """
    Procesa un PDF y devuelve lista de tuplas:
    (date, description, amount, currency, tag, limit)
    """
    # 1️⃣ extraer texto y líneas de compras
    full_text = extract_text(pdf_path)
    raw = extract_purchases(full_text)
    # 2️⃣ cargar tags y asignar tag+limit a cada compra
    tags = load_tags()
    purchases = []
    for date, desc, amt, cur in raw:
        tag = tag_purchase(desc, tags)
        limit = tags.get(tag, {}).get("limit", 0)
        purchases.append((date, desc, amt, cur, tag, limit))
    return purchases
