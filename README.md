# Purchase Tagger Desktop App

A simple Python/Tkinter application to extract purchases from PDF files, tag them with customizable keywords, summarize spending, and export filtered results.

---

## Features

- **Multiple PDF Support**: Select one or more PDFs for batch processing.
- **Custom Tags & Keywords**: Manage tags, keywords, and optional limits in `tags.json` through the built-in Tag Editor.
- **Case-Insensitive Matching**: Keywords match purchase descriptions regardless of case.
- **Search & Filter**: Live text search filters the displayed purchases.
- **Summary Views**: Choose Spend by Tag, Monthly Spend, Cumulative Spend, Límite vs Gasto por Tag, or Gasto Promedio por Tag/Mes.
- **CSV Export**: Export the filtered table to CSV.

---

## Requirements

- Python 3.7 or higher
- `tkinter` (usually included with Python)
- Runtime packages from `requirements.txt`, including CustomTkinter for the desktop UI

Install runtime dependencies with:

```bash
pip install -r requirements.txt
```

For development and tests, install:

```bash
pip install -r requirements-dev.txt
```

---

## Installation

1. Clone or download this repository.
2. Ensure `purchase_tagger_app.py`, `purchase_extractor.py`, and `tags.json` are in the same folder.
3. Optional: create and activate a virtual environment.
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

---

## Usage

1. Run the application:

   ```bash
   python purchase_tagger_app.py
   ```

2. Click **Browse & Tag** and choose one or more PDF files containing purchase data. The app automatically parses the selected PDFs, tags each purchase, and displays the table.
3. Use **Search** to filter rows by any displayed text.
4. Click **Summary** and choose:
   - **Spend by Tag**: Pie chart of total spend per tag.
   - **Monthly Spend**: Bar chart of spend per month.
   - **Cumulative Spend**: Line chart of cumulative spend over time.
   - **Límite vs Gasto por Tag**: Bar chart comparing tag limits to actual spend.
   - **Gasto Promedio por Tag/Mes**: Table of average monthly spend by tag.
   Summary charts and limit comparisons require one selected currency at a time to avoid mixing unrelated monetary totals.
5. Click **Export** to save the current filtered table to CSV.
6. Use the **Tags** sidebar view to add, edit, or remove tags, keywords, and limits.

---

## Configuration (`tags.json`)

`tags.json` lives alongside the app and maps tag names to keyword lists and optional spending limits:

```json
{
  "Groceries": {
    "keywords": ["WALMART", "SAFEWAY"],
    "limit": 500
  },
  "Travel": {
    "keywords": ["AIRLINES", "UBER"],
    "limit": 1000
  }
}
```

Keywords are matched case-insensitively against purchase descriptions.

---

## Testing

Install development and test dependencies, then run the test suite with `pytest`:

```bash
pip install -r requirements-dev.txt
pytest
```

The test workflow is standardized on `pytest`; `unittest discover` does not cover every test file.

---

## Packaging

`purchase_tagger_app.spec` is the tracked PyInstaller build recipe for the desktop app. It includes the app entry point, local helper modules, `tags.json`, and CustomTkinter runtime assets.

Install development/build dependencies, then run:

```bash
pip install -r requirements-dev.txt
python -m PyInstaller purchase_tagger_app.spec
```

PyInstaller outputs are generated under `build/` and `dist/`; those directories stay ignored by git.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
