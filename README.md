# Purchase Tagger Desktop App

Current release: **v1.0** (`2026-06-08`)

A Python/Tkinter desktop application to extract purchases from bank statement PDFs, tag them with customizable keywords, summarize spending, and export filtered results.

---

## Features

- **Multiple PDF Support**: Select one or more PDFs for batch processing.
- **Bank & Account Type Selection**: Choose the statement bank (`BAC` or `Promerica`) and whether the import is `Credito` or `Debito`.
- **Custom Tags & Keywords**: Manage tags, keywords, categories, budget metadata, optional limits, and JSON import/export through the built-in Tags view.
- **Case-Insensitive Matching**: Keywords match purchase descriptions regardless of case.
- **Search & Filter**: Live text search filters the displayed purchases.
- **Summary Views**: Choose spend by tag, monthly spend, cumulative spend, budget comparisons, average spend by tag/month, and metadata summaries.
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

   The window title shows `Etiquetador de compras PDF v1.0`.

2. Choose the bank (`BAC` or `Promerica`) and account type (`Credito` or `Debito`), then click **Browse & Tag** and choose one or more PDF files containing purchase data. The app automatically parses the selected PDFs, tags each purchase, and displays the table.
3. Use **Search** to filter rows by any displayed text.
4. Click **Summary** and choose:
   - **Gasto por etiqueta**: Pie chart of total spend per tag.
   - **Gasto mensual**: Bar chart of spend per month.
   - **Gasto acumulado**: Line chart of cumulative spend over time.
   - **Presupuesto vs gasto por etiqueta**: Bar chart comparing tag budgets to actual spend.
   - **Gasto promedio por etiqueta/mes**: Table of average monthly spend by tag, grouped by parent category.
   - **Gasto por tipo de presupuesto**, **Gasto por categoría padre**, or **Gasto por propósito financiero**: Metadata-based breakdowns.
   Summary charts and limit comparisons require one selected currency at a time to avoid mixing unrelated monetary totals.
5. Click **Export** to save the current filtered table to CSV.
6. Use the **Tags** sidebar view to add, edit, remove, import, or export tags, keywords, and limits. **Export JSON** saves the tag list with `tag_list.json` as the suggested filename.

For the full operator guide, see [docs/USER_MANUAL.md](docs/USER_MANUAL.md). Release history is in [CHANGELOG.md](CHANGELOG.md).

---

## Configuration (`tags.json`)

`tags.json` lives alongside the app and maps tag names to keyword lists and optional spending limits:

```json
{
  "tag_name": {
    "keywords": ["KEYWORD"],
    "limit": 0,
    "planned_amount": 0,
    "budget_type": "Expense",
    "parent_category": "Sin clasificar",
    "budget_period": "monthly",
    "expense_nature": "variable",
    "financial_purpose": "Necesidad"
  }
}
```

Each top-level key is the tag name. Keywords are matched case-insensitively against purchase descriptions. Older list-only tag files are migrated automatically when loaded.

The **Tags** view can export this structure to a JSON file or import another JSON file with the same structure. Imports are additive: new tags are added, missing keywords are appended to existing tags, duplicate keywords are skipped, and imported limits replace current limits for matching tag names.

---

## Testing

Install development and test dependencies, then run the test suite with `pytest`:

```bash
pip install -r requirements-dev.txt
pytest
```

The test workflow is standardized on `pytest`; `unittest discover` does not cover every test file.

For a quick syntax check, run:

```bash
python -m compileall purchase_tagger_app.py purchase_extractor.py tag_store.py summary.py ui_state.py money.py views version.py
```

---

## Packaging

`purchase_tagger_app.spec` is the tracked PyInstaller build recipe for the desktop app. It includes the app entry point, local helper modules, `tags.json`, and CustomTkinter runtime assets.

Install development/build dependencies, then run:

```bash
pip install -r requirements-dev.txt
python -m PyInstaller purchase_tagger_app.spec
```

PyInstaller outputs are generated under `build/` and `dist/`; those directories stay ignored by git.

To generate a shareable Windows installer plus a portable ZIP, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\installer\build_installer.ps1
```

This creates:

- `dist\PurchaseTagger-v1.0-Setup.exe`: per-user installer. It installs to `%LOCALAPPDATA%\Programs\PurchaseTagger` and creates Desktop and Start Menu shortcuts.
- `dist\PurchaseTagger-v1.0-portable.zip`: portable package containing the executable, manual, default tags, license, README, and changelog.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
