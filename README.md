# Purchase Tagger Desktop App

A simple Python/Tkinter application to extract purchases from PDF files, automatically tag them based on customizable keywords, and provide interactive summaries and exports.

---

## Features

- **Multiple PDF Support**: Select one or more PDFs at once for batch processing.
- **Custom Tags & Keywords**: Define your own tags and associated keywords in `tags.json` via the built-in Tag Editor.
- **Case‑Insensitive Matching**: Keywords match regardless of case.
- **Search & Filter**: Live text search to filter the displayed purchases.
- **Summary Charts**: Choose between Spend by Tag, Monthly Spend, or Cumulative Spend via a dropdown.
- **CSV Export**: Export the filtered table to CSV in one click.
- **Watch Mode (Optional)**: Monitor a folder and auto-load any new PDFs dropped in.

---

## Requirements

- Python 3.7 or higher
- The following Python packages:
  - `tkinter` (usually included with Python)
  - `matplotlib`

You can install dependencies with:

```bash
pip install matplotlib
```

---

## Installation

1. **Clone or download** this repository.

2. Ensure `purchase_tagger_app.py`, `purchase_extractor.py`, and `tags.json` are in the same folder.

3. (Optional) Create a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate   # macOS/Linux
   venv\Scripts\activate    # Windows
   ```

4. Install dependencies:

   ```bash
   pip install matplotlib
   ```

---

## Usage

1. **Run the application**:

   ```bash
   python purchase_tagger_app.py
   ```

2. **Select PDF(s)**:

   - Click **Browse** and choose one or more PDF files containing purchase data.
   - Selected filenames will appear in the entry box.

3. **Load & Tag**:

   - Click **Load & Tag** to parse all selected PDFs, tag each purchase, and display them in the table.

4. **Search**:

   - Use the **Search** field to filter rows by any text (date, description, tag, etc.).

5. **Summary**:

   - Click **Summary**.
   - In the dropdown, choose:
     - **Spend by Tag**: Pie chart of total spend per tag.
     - **Monthly Spend**: Bar chart of spend per month.
     - **Cumulative Spend**: Line chart of cumulative spend over time.

6. **Export CSV**:

   - Click **Export** to save the currently filtered table to a CSV file.

7. **Manage Tags**:

   - From the **Tags** menu, select **Manage Tags...**
   - Add/Edit/Remove tags and keywords. Changes are saved to `tags.json`.

8. **Watch Mode (Optional)**:

   - From the **Watch** menu, click **Start Watching...** and choose a folder.
   - Any new PDF placed in that folder will be auto-loaded and tagged.
   - To stop, click **Stop Watching...** in the same menu.

---

## Configuration (`tags.json`)

- Located alongside the app.

- JSON object mapping tag names to lists of keywords, e.g.:

  ```json
  {
    "Groceries": ["WALMART", "SAFEWAY"],
    "Travel": ["AMAZON AIRLINES", "UBER"],
    "Dining": ["STARBUCKS", "MCDONALDS"]
  }
  ```

- Keywords are matched case-insensitively against purchase descriptions.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
