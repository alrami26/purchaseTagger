# purchase_extractor.py
#!/usr/bin/env python3
import re
from pypdf import PdfReader

# Extract all text from the PDF
def extract_text(pdf_path):
    reader = PdfReader(pdf_path)
    texts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.append(text)
    return "\n".join(texts)

# Parse out purchase lines from the text
def extract_purchases(full_text):
    line_re = re.compile(
        r'^\d+\s+'                                   # transaction ID
        r'(\d{2}-(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)-\d{2})\s+'  # date
        r'(.+?)\s+'                                   # description
        r'([A-Z]{3})\s+'                              # currency code
        r'([\d,]+\.[0-9]{2})$'                       # amount
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
            purchases.append((date, desc.strip(), amt.replace(',',''), cur))
    return purchases

# Combined processing: returns list of tuples (date, description, amount, currency)
def process_purchases(pdf_path):
    full_text = extract_text(pdf_path)
    return extract_purchases(full_text)