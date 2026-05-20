# CustomTkinter Modern Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the PDF Purchase Tagger desktop UI as a CustomTkinter modern workspace while preserving extraction, tagging, summaries, filtering, and CSV export behavior.

**Architecture:** Keep existing business modules intact and extract UI-only derived state into a small testable helper module. Replace the classic `tkinter.Tk` root with a `customtkinter.CTk` shell containing a sidebar and workspace views. Use CustomTkinter for layout and controls, while keeping `ttk.Treeview` where it remains the best table widget.

**Tech Stack:** Python, CustomTkinter, Tkinter/ttk, Matplotlib, pypdf, pytest.

---

## File Structure

- Modify `requirements.txt`: add `customtkinter`.
- Create `ui_state.py`: pure helper functions for filters, KPI stats, totals text, selected file labels, and available filter choices.
- Create `test_ui_state.py`: unit tests for the new helper functions.
- Modify `purchase_tagger_app.py`: migrate the root app to CustomTkinter, add sidebar navigation, workspace views, styled table, embedded summaries, and tags workspace.
- Modify `test_purchase_tagger_app.py`: keep the existing row mapping tests compatible with the migrated app.
- Modify `README.md`: mention CustomTkinter dependency and the new sidebar workflow.

Keep `purchase_extractor.py`, `summary.py`, and `tag_store.py` behavior unchanged unless a failing test proves a compatibility issue.

---

### Task 1: Add Testable UI State Helpers

**Files:**
- Create: `C:\Users\alram\PycharmProjects\pdfProject\ui_state.py`
- Create: `C:\Users\alram\PycharmProjects\pdfProject\test_ui_state.py`
- Uses: `C:\Users\alram\PycharmProjects\pdfProject\summary.py`

- [ ] **Step 1: Write failing tests for filter and KPI helpers**

Create `test_ui_state.py` with this content:

```python
from ui_state import (
    available_currencies,
    available_tags,
    build_file_label,
    filter_purchase_rows,
    format_totals,
    kpi_stats,
)


ROWS = [
    ["01-MAY-26", "AUTOMERCADO ESCAZU", "42,300.00", "CRC", "Groceries"],
    ["02-MAY-26", "UBER TRIP", "8.70", "USD", "Transport"],
    ["03-ABR-26", "UNMATCHED VENDOR", "19.95", "USD", "N/A"],
]


def test_filter_purchase_rows_combines_text_currency_month_and_tag():
    result = filter_purchase_rows(
        ROWS,
        search_text="uber",
        currencies={"USD"},
        month_key="2026-05",
        tag_name="Transport",
    )

    assert result == [["02-MAY-26", "UBER TRIP", "8.70", "USD", "Transport"]]


def test_filter_purchase_rows_allows_all_filter_values():
    result = filter_purchase_rows(
        ROWS,
        search_text="",
        currencies=set(),
        month_key="Todos",
        tag_name="Todos",
    )

    assert result == ROWS


def test_available_filter_choices_are_sorted():
    assert available_currencies(ROWS) == ["CRC", "USD"]
    assert available_tags(ROWS) == ["Groceries", "N/A", "Transport"]


def test_kpi_stats_counts_rows_currencies_untagged_and_over_limit_tags():
    tags = {
        "Groceries": {"keywords": [], "limit": 100},
        "Transport": {"keywords": [], "limit": 5},
    }

    stats = kpi_stats(ROWS, ROWS, tags, natag="N/A")

    assert stats == {
        "total_rows": 3,
        "visible_rows": 3,
        "untagged_rows": 1,
        "currency_count": 2,
        "over_limit_tags": 2,
    }


def test_format_totals_outputs_sorted_currency_totals():
    assert format_totals(ROWS) == "Totals: CRC 42,300.00; USD 28.65"
    assert format_totals([]) == "Totals: 0.00"


def test_build_file_label_handles_empty_single_and_multiple_files():
    assert build_file_label([]) == "No PDFs selected"
    assert build_file_label([r"C:\tmp\statement.pdf"]) == "statement.pdf"
    assert build_file_label([r"C:\tmp\a.pdf", r"C:\tmp\b.pdf"]) == "2 PDFs selected"
```

- [ ] **Step 2: Run helper tests and verify they fail**

Run:

```powershell
pytest test_ui_state.py -v
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'ui_state'`.

- [ ] **Step 3: Implement helper module**

Create `ui_state.py` with this content:

```python
#!/usr/bin/env python3
import os
from collections import Counter

from summary import currency_totals, filter_rows_by_month, filter_rows_by_text


ALL_MONTHS = "Todos"
ALL_TAGS = "Todos"


def filter_purchase_rows(rows, search_text="", currencies=None, month_key=ALL_MONTHS, tag_name=ALL_TAGS):
    filtered = filter_rows_by_text(rows, search_text)
    if currencies:
        filtered = [row for row in filtered if len(row) > 3 and row[3] in currencies]
    filtered = filter_rows_by_month(filtered, month_key)
    if tag_name and tag_name != ALL_TAGS:
        filtered = [row for row in filtered if len(row) > 4 and row[4] == tag_name]
    return filtered


def available_currencies(rows):
    return sorted({row[3] for row in rows if len(row) > 3 and row[3]})


def available_tags(rows):
    return sorted({row[4] for row in rows if len(row) > 4 and row[4]})


def kpi_stats(all_rows, filtered_rows, tags, natag="N/A"):
    totals_by_tag = Counter()
    for row in filtered_rows:
        if len(row) < 5:
            continue
        tag = row[4]
        try:
            amount = float(row[2].replace(",", ""))
        except (ValueError, AttributeError):
            continue
        totals_by_tag[tag] += amount

    over_limit_tags = 0
    for tag, total in totals_by_tag.items():
        limit = tags.get(tag, {}).get("limit", 0)
        if limit and total > limit:
            over_limit_tags += 1

    return {
        "total_rows": len(all_rows),
        "visible_rows": len(filtered_rows),
        "untagged_rows": sum(1 for row in filtered_rows if len(row) > 4 and row[4] == natag),
        "currency_count": len(available_currencies(filtered_rows)),
        "over_limit_tags": over_limit_tags,
    }


def format_totals(rows):
    totals = currency_totals(rows)
    if not totals:
        return "Totals: 0.00"
    parts = [f"{currency} {amount:,.2f}" for currency, amount in sorted(totals.items())]
    return f"Totals: {'; '.join(parts)}"


def build_file_label(pdf_files):
    if not pdf_files:
        return "No PDFs selected"
    if len(pdf_files) == 1:
        return os.path.basename(pdf_files[0])
    return f"{len(pdf_files)} PDFs selected"
```

- [ ] **Step 4: Run helper tests and verify they pass**

Run:

```powershell
pytest test_ui_state.py -v
```

Expected: PASS for all tests in `test_ui_state.py`.

- [ ] **Step 5: Run current full test suite**

Run:

```powershell
pytest -q
```

Expected: existing tests pass, plus the new helper tests pass.

- [ ] **Step 6: Commit helper module**

Run:

```powershell
git add ui_state.py test_ui_state.py
git commit -m "Add UI state helpers"
```

---

### Task 2: Add CustomTkinter Dependency

**Files:**
- Modify: `C:\Users\alram\PycharmProjects\pdfProject\requirements.txt`

- [ ] **Step 1: Update runtime requirements**

Edit `requirements.txt` so it contains exactly:

```text
pypdf
matplotlib
customtkinter
```

- [ ] **Step 2: Install dependencies in the active environment**

Run:

```powershell
pip install -r requirements.txt
```

Expected: pip reports `customtkinter` installed or already satisfied.

- [ ] **Step 3: Verify CustomTkinter import**

Run:

```powershell
python -c "import customtkinter; print(customtkinter.__version__)"
```

Expected: command exits with code 0 and prints a version string.

- [ ] **Step 4: Commit dependency update**

Run:

```powershell
git add requirements.txt
git commit -m "Add CustomTkinter dependency"
```

---

### Task 3: Convert Root Window To CustomTkinter Shell

**Files:**
- Modify: `C:\Users\alram\PycharmProjects\pdfProject\purchase_tagger_app.py`
- Test: `C:\Users\alram\PycharmProjects\pdfProject\test_purchase_tagger_app.py`

- [ ] **Step 1: Write compatibility test for non-UI row assignment**

Append this test to `PurchaseTaggerRowMappingTest` in `test_purchase_tagger_app.py`:

```python
    def test_row_mapping_helper_returns_original_row(self):
        rows = [
            ["01-ENE-25", "APPLE STORE", "10.00", "USD", "N/A"],
            ["02-ENE-25", "BANANA MARKET", "20.00", "USD", "N/A"],
        ]
        app = self.make_app(rows, ["item-b", "item-a"])

        assert app._row_for_item("item-b") is rows[1]
```

- [ ] **Step 2: Run compatibility test**

Run:

```powershell
pytest test_purchase_tagger_app.py::PurchaseTaggerRowMappingTest::test_row_mapping_helper_returns_original_row -v
```

Expected: PASS, confirming existing non-UI behavior remains available before shell work.

- [ ] **Step 3: Update imports and root class**

In `purchase_tagger_app.py`, add these imports near the top:

```python
import customtkinter as ctk
from ui_state import (
    ALL_MONTHS,
    ALL_TAGS,
    available_currencies,
    available_tags,
    build_file_label,
    filter_purchase_rows,
    format_totals,
    kpi_stats,
)
```

Change:

```python
class PurchaseTaggerUI(tk.Tk):
```

to:

```python
class PurchaseTaggerUI(ctk.CTk):
```

At the start of `PurchaseTaggerUI.__init__`, before `super().__init__()`, set the theme:

```python
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
```

- [ ] **Step 4: Replace the old root layout setup**

Replace the body of `PurchaseTaggerUI.__init__` after state initialization with a shell structure using these instance variables:

```python
        self.active_view = "Imports"
        self.search_var = tk.StringVar()
        self.currency_var = tk.StringVar(value="All currencies")
        self.month_var = tk.StringVar(value=ALL_MONTHS)
        self.tag_filter_var = tk.StringVar(value=ALL_TAGS)
        self.status_var = tk.StringVar(value="Ready")
        self.file_label_var = tk.StringVar(value=build_file_label(self.pdf_files))
        self.total_var = tk.StringVar(value="Totals: 0.00")
        self.kpi_vars = {
            "total_rows": tk.StringVar(value="0"),
            "visible_rows": tk.StringVar(value="0"),
            "untagged_rows": tk.StringVar(value="0"),
            "currency_count": tk.StringVar(value="0"),
            "over_limit_tags": tk.StringVar(value="0"),
        }

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=190, corner_radius=0, fg_color="#1f2633")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self.workspace = ctk.CTkFrame(self, corner_radius=0, fg_color="#f4f6f8")
        self.workspace.grid(row=0, column=1, sticky="nsew")
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(1, weight=1)

        self._build_sidebar()
        self.show_view("Imports")
```

- [ ] **Step 5: Add sidebar builder and view switching methods**

Add these methods inside `PurchaseTaggerUI`:

```python
    def _build_sidebar(self):
        title = ctk.CTkLabel(
            self.sidebar,
            text="Purchase Tagger",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#f8fafc",
        )
        title.pack(anchor="w", padx=16, pady=(20, 2))

        subtitle = ctk.CTkLabel(
            self.sidebar,
            text="PDF finance workspace",
            font=ctk.CTkFont(size=12),
            text_color="#aeb8c7",
        )
        subtitle.pack(anchor="w", padx=16, pady=(0, 22))

        self.nav_buttons = {}
        for view in ("Imports", "Purchases", "Summaries", "Tags"):
            button = ctk.CTkButton(
                self.sidebar,
                text=view,
                anchor="w",
                fg_color="transparent",
                hover_color="#334155",
                text_color="#cbd5e1",
                command=lambda name=view: self.show_view(name),
            )
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[view] = button

        ctk.CTkLabel(
            self.sidebar,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=11),
            text_color="#aeb8c7",
            wraplength=150,
            justify="left",
        ).pack(side="bottom", anchor="w", padx=16, pady=18)

    def show_view(self, view_name):
        self.active_view = view_name
        for name, button in self.nav_buttons.items():
            if name == view_name:
                button.configure(fg_color="#334155", text_color="#f8fafc")
            else:
                button.configure(fg_color="transparent", text_color="#cbd5e1")

        for child in self.workspace.winfo_children():
            child.destroy()

        if view_name == "Imports":
            self._build_imports_view()
        elif view_name == "Purchases":
            self._build_purchases_view()
        elif view_name == "Summaries":
            self._build_summary_view()
        elif view_name == "Tags":
            self._build_tags_view()
```

- [ ] **Step 6: Add temporary view stubs**

Add these temporary methods so the app can run before later tasks fill the views:

```python
    def _build_placeholder_view(self, title):
        ctk.CTkLabel(
            self.workspace,
            text=title,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#171a20",
        ).grid(row=0, column=0, sticky="w", padx=24, pady=24)

    def _build_imports_view(self):
        self._build_placeholder_view("Imports")

    def _build_purchases_view(self):
        self._build_placeholder_view("Purchases")

    def _build_summary_view(self):
        self._build_placeholder_view("Summaries")

    def _build_tags_view(self):
        self._build_placeholder_view("Tags")
```

- [ ] **Step 7: Run tests**

Run:

```powershell
pytest -q
```

Expected: PASS.

- [ ] **Step 8: Manually launch app**

Run:

```powershell
python purchase_tagger_app.py
```

Expected: app opens with dark sidebar and simple workspace view labels.

- [ ] **Step 9: Commit shell migration**

Run:

```powershell
git add purchase_tagger_app.py test_purchase_tagger_app.py
git commit -m "Create CustomTkinter workspace shell"
```

---

### Task 4: Build Imports And Purchases Views

**Files:**
- Modify: `C:\Users\alram\PycharmProjects\pdfProject\purchase_tagger_app.py`
- Uses: `C:\Users\alram\PycharmProjects\pdfProject\ui_state.py`

- [ ] **Step 1: Add reusable panel and heading helpers**

Add these methods to `PurchaseTaggerUI`:

```python
    def _panel(self, parent, **grid_options):
        frame = ctk.CTkFrame(parent, fg_color="#ffffff", border_width=1, border_color="#e0e5ec", corner_radius=8)
        frame.grid(**grid_options)
        return frame

    def _build_page_header(self, parent, title, subtitle, action_text=None, action_command=None):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#171a20",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text=subtitle,
            font=ctk.CTkFont(size=12),
            text_color="#6b7280",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        if action_text and action_command:
            ctk.CTkButton(header, text=action_text, command=action_command, fg_color="#2563eb").grid(
                row=0, column=1, rowspan=2, sticky="e"
            )
```

- [ ] **Step 2: Replace `_build_imports_view`**

Replace the temporary `_build_imports_view` with:

```python
    def _build_imports_view(self):
        self.workspace.grid_rowconfigure(1, weight=1)
        self._build_page_header(
            self.workspace,
            "Imports",
            "Load PDFs, tag purchases, and review results.",
            action_text="Load & Tag",
            action_command=self.load,
        )

        content = ctk.CTkFrame(self.workspace, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(3, weight=1)

        self._build_file_panel(content, row=0)
        self._build_kpi_row(content, row=1)
        self._build_filter_toolbar(content, row=2)
        self._build_purchase_table(content, row=3)
        self._build_totals_footer(content, row=4)
        self.apply_filter()
```

- [ ] **Step 3: Replace `_build_purchases_view`**

Replace the temporary `_build_purchases_view` with:

```python
    def _build_purchases_view(self):
        self.workspace.grid_rowconfigure(1, weight=1)
        self._build_page_header(
            self.workspace,
            "Purchases",
            "Review, search, and correct tagged purchase rows.",
        )

        content = ctk.CTkFrame(self.workspace, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)

        self._build_kpi_row(content, row=0)
        self._build_filter_toolbar(content, row=1)
        self._build_purchase_table(content, row=2)
        self._build_totals_footer(content, row=3)
        self.apply_filter()
```

- [ ] **Step 4: Add file panel, KPI row, filters, table, and footer**

Add these methods:

```python
    def _build_file_panel(self, parent, row):
        panel = self._panel(parent, row=row, column=0, sticky="ew", pady=(0, 12))
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="Selected PDFs", text_color="#6b7280", font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 0)
        )
        ctk.CTkLabel(panel, textvariable=self.file_label_var, text_color="#171a20", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=1, column=0, sticky="w", padx=14, pady=(2, 12)
        )
        ctk.CTkButton(panel, text="Browse", command=self.browse_pdf, width=90).grid(row=0, column=1, rowspan=2, padx=(0, 8))
        ctk.CTkButton(panel, text="Clear", command=self.clear_pdfs, width=80, fg_color="#64748b").grid(
            row=0, column=2, rowspan=2, padx=(0, 14)
        )

    def _build_kpi_row(self, parent, row):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        for index in range(5):
            frame.grid_columnconfigure(index, weight=1)
        cards = [
            ("Purchases", "total_rows"),
            ("Visible", "visible_rows"),
            ("Untagged", "untagged_rows"),
            ("Currencies", "currency_count"),
            ("Over Limit", "over_limit_tags"),
        ]
        for index, (label, key) in enumerate(cards):
            card = ctk.CTkFrame(frame, fg_color="#ffffff", border_width=1, border_color="#e0e5ec", corner_radius=8)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            ctk.CTkLabel(card, text=label, text_color="#6b7280", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(card, textvariable=self.kpi_vars[key], text_color="#171a20", font=ctk.CTkFont(size=22, weight="bold")).pack(
                anchor="w", padx=12, pady=(2, 10)
            )

    def _build_filter_toolbar(self, parent, row):
        panel = self._panel(parent, row=row, column=0, sticky="ew", pady=(0, 12))
        panel.grid_columnconfigure(0, weight=1)
        self.search_var.trace_add("write", lambda *args: self.apply_filter())
        search = ctk.CTkEntry(panel, textvariable=self.search_var, placeholder_text="Search purchases, descriptions, tags")
        search.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.currency_menu = ctk.CTkOptionMenu(panel, variable=self.currency_var, values=["All currencies"], command=lambda _: self.apply_filter())
        self.currency_menu.grid(row=0, column=1, padx=(0, 8))
        self.month_menu = ctk.CTkOptionMenu(panel, variable=self.month_var, values=[ALL_MONTHS], command=lambda _: self.apply_filter())
        self.month_menu.grid(row=0, column=2, padx=(0, 8))
        self.tag_menu = ctk.CTkOptionMenu(panel, variable=self.tag_filter_var, values=[ALL_TAGS], command=lambda _: self.apply_filter())
        self.tag_menu.grid(row=0, column=3, padx=(0, 8))
        ctk.CTkButton(panel, text="Reset", command=self.reset_filters, width=72, fg_color="#64748b").grid(row=0, column=4, padx=(0, 8))
        ctk.CTkButton(panel, text="Export", command=self.export_csv, width=76).grid(row=0, column=5, padx=(0, 10))

    def _build_purchase_table(self, parent, row):
        table_frame = self._panel(parent, row=row, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        cols = ("date", "description", "amount", "currency", "tag")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        for col in cols:
            self.tree.heading(col, text=col.title(), command=lambda selected_col=col: self.sort_column(selected_col, False))
        self.tree.column("date", width=110, anchor="w")
        self.tree.column("description", width=360, anchor="w")
        self.tree.column("amount", width=120, anchor="e")
        self.tree.column("currency", width=90, anchor="center")
        self.tree.column("tag", width=140, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(1, 0), pady=1)
        self.tree.bind("<Button-3>", self.on_right_click)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self._style_treeview()

    def _build_totals_footer(self, parent, row):
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.grid(row=row, column=0, sticky="ew", pady=(8, 0))
        footer.grid_columnconfigure(0, weight=1)
        self.visible_count_var = tk.StringVar(value="Showing 0 purchases")
        ctk.CTkLabel(footer, textvariable=self.visible_count_var, text_color="#6b7280", font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(footer, textvariable=self.total_var, text_color="#171a20", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=1, sticky="e"
        )
```

- [ ] **Step 5: Add styling and filter update helpers**

Add these methods:

```python
    def _style_treeview(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#171a20",
            rowheight=30,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#eef2f7",
            foreground="#475569",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#171a20")])

    def _refresh_filter_options(self):
        if hasattr(self, "currency_menu"):
            currency_values = ["All currencies"] + available_currencies(self.all_rows)
            self.currency_menu.configure(values=currency_values)
            if self.currency_var.get() not in currency_values:
                self.currency_var.set("All currencies")
        if hasattr(self, "month_menu"):
            month_values = [ALL_MONTHS] + available_months(self.all_rows)
            self.month_menu.configure(values=month_values)
            if self.month_var.get() not in month_values:
                self.month_var.set(ALL_MONTHS)
        if hasattr(self, "tag_menu"):
            tag_values = [ALL_TAGS] + available_tags(self.all_rows)
            self.tag_menu.configure(values=tag_values)
            if self.tag_filter_var.get() not in tag_values:
                self.tag_filter_var.set(ALL_TAGS)

    def _update_kpis(self):
        stats = kpi_stats(self.all_rows, self.filtered_rows, self.tags, self.natag)
        for key, value in stats.items():
            self.kpi_vars[key].set(str(value))
```

- [ ] **Step 6: Update `browse_pdf`, add `clear_pdfs`, and replace `apply_filter`**

In `browse_pdf`, replace direct entry updates with:

```python
            self.file_label_var.set(build_file_label(self.pdf_files))
            self.status_var.set(f"{len(self.pdf_files)} PDF file(s) selected")
```

Add:

```python
    def clear_pdfs(self):
        self.pdf_files = []
        self.file_label_var.set(build_file_label(self.pdf_files))
        self.status_var.set("No PDFs selected")
```

Replace `apply_filter` with:

```python
    def apply_filter(self):
        selected_currency = self.currency_var.get()
        currencies = set() if selected_currency == "All currencies" else {selected_currency}
        self.filtered_rows = filter_purchase_rows(
            self.all_rows,
            search_text=self.search_var.get(),
            currencies=currencies,
            month_key=self.month_var.get(),
            tag_name=self.tag_filter_var.get(),
        )
        self.tree_item_rows.clear()
        if hasattr(self, "tree"):
            for item in self.tree.get_children():
                self.tree.delete(item)
            for index, row in enumerate(self.filtered_rows):
                tags = ("odd",) if index % 2 else ("even",)
                iid = self.tree.insert("", "end", values=row, tags=tags)
                self.tree_item_rows[iid] = row
            self.tree.tag_configure("even", background="#ffffff")
            self.tree.tag_configure("odd", background="#fafbfc")
        self._refresh_filter_options()
        self._update_kpis()
        self.total_var.set(format_totals(self.filtered_rows))
        if hasattr(self, "visible_count_var"):
            self.visible_count_var.set(f"Showing {len(self.filtered_rows)} purchases")
```

Add:

```python
    def reset_filters(self):
        self.search_var.set("")
        self.currency_var.set("All currencies")
        self.month_var.set(ALL_MONTHS)
        self.tag_filter_var.set(ALL_TAGS)
        self.apply_filter()
```

- [ ] **Step 7: Update `load` feedback**

In `load`, before processing rows, add:

```python
        self.status_var.set("Processing PDFs...")
        self.update_idletasks()
```

At the end of successful processing, replace the success message box with:

```python
        self.status_var.set(f"Loaded and tagged {len(self.all_rows)} purchases")
```

Keep the warning and error message boxes.

- [ ] **Step 8: Run tests**

Run:

```powershell
pytest -q
```

Expected: PASS.

- [ ] **Step 9: Manually verify Imports and Purchases views**

Run:

```powershell
python purchase_tagger_app.py
```

Expected:
- Sidebar switches between `Imports` and `Purchases`.
- File panel appears only on `Imports`.
- Table renders in both views.
- Search/filter changes visible rows.
- Totals and KPI cards update.

- [ ] **Step 10: Commit Imports/Purchases views**

Run:

```powershell
git add purchase_tagger_app.py
git commit -m "Build imports and purchases workspace views"
```

---

### Task 5: Embed Summary View In Workspace

**Files:**
- Modify: `C:\Users\alram\PycharmProjects\pdfProject\purchase_tagger_app.py`
- Uses: `C:\Users\alram\PycharmProjects\pdfProject\summary.py`

- [ ] **Step 1: Replace `_build_summary_view`**

Replace the temporary `_build_summary_view` with a workspace version:

```python
    def _build_summary_view(self):
        self.workspace.grid_rowconfigure(1, weight=1)
        self._build_page_header(
            self.workspace,
            "Summaries",
            "Analyze spending by tag, month, cumulative trend, and limits.",
        )

        content = ctk.CTkFrame(self.workspace, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        controls = self._panel(content, row=0, column=0, sticky="ew", pady=(0, 12))
        controls.grid_columnconfigure(5, weight=1)

        self.summary_choice_var = tk.StringVar(value="Spend by Tag")
        self.summary_chart_menu = ctk.CTkOptionMenu(
            controls,
            variable=self.summary_choice_var,
            values=["Spend by Tag", "Monthly Spend", "Cumulative Spend", "Limite vs Gasto por Tag", "Gasto Promedio por Tag/Mes"],
            command=lambda _: self.draw_summary(),
            width=220,
        )
        self.summary_chart_menu.grid(row=0, column=0, padx=10, pady=10)

        self.summary_month_var = tk.StringVar(value=ALL_MONTHS)
        month_values = [ALL_MONTHS] + available_months(self.filtered_rows or self.all_rows)
        self.summary_month_menu = ctk.CTkOptionMenu(
            controls,
            variable=self.summary_month_var,
            values=month_values,
            command=lambda _: self.draw_summary(),
            width=130,
        )
        self.summary_month_menu.grid(row=0, column=1, padx=(0, 10), pady=10)

        self.summary_currency_vars = {}
        for index, currency in enumerate(available_currencies(self.filtered_rows or self.all_rows)):
            var = tk.BooleanVar(value=True)
            self.summary_currency_vars[currency] = var
            ctk.CTkCheckBox(controls, text=currency, variable=var, command=self.draw_summary, width=70).grid(
                row=0, column=2 + index, padx=(0, 8), pady=10
            )

        self.summary_frame = self._panel(content, row=1, column=0, sticky="nsew")
        self.summary_frame.grid_columnconfigure(0, weight=1)
        self.summary_frame.grid_rowconfigure(0, weight=1)
        self.draw_summary()
```

- [ ] **Step 2: Add embedded summary draw method**

Add this method by adapting the existing body from `open_summary`:

```python
    def draw_summary(self):
        if not hasattr(self, "summary_frame"):
            return
        for child in self.summary_frame.winfo_children():
            child.destroy()

        rows = self.filtered_rows or self.all_rows
        if not rows:
            ctk.CTkLabel(
                self.summary_frame,
                text="Load purchases to see summaries.",
                text_color="#6b7280",
                font=ctk.CTkFont(size=14),
            ).grid(row=0, column=0, padx=24, pady=24)
            return

        selected = {currency for currency, var in self.summary_currency_vars.items() if var.get()}
        if not selected:
            ctk.CTkLabel(
                self.summary_frame,
                text="Select at least one currency.",
                text_color="#6b7280",
                font=ctk.CTkFont(size=14),
            ).grid(row=0, column=0, padx=24, pady=24)
            return

        data_rows = filter_rows_by_month(rows, self.summary_month_var.get())
        aggregates = summary_aggregates(data_rows, selected)
        tag_totals = aggregates["tag_totals"]
        monthly = aggregates["monthly_totals"]
        cumulative_points = aggregates["cumulative_points"]
        choice = self.summary_choice_var.get()

        if choice == "Spend by Tag":
            fig, ax = plt.subplots(figsize=(7, 4))
            if tag_totals:
                ax.pie(tag_totals.values(), labels=tag_totals.keys(), autopct="%1.1f%%")
            ax.set_title("Spend by Tag")
            FigureCanvasTkAgg(fig, master=self.summary_frame).get_tk_widget().grid(row=0, column=0, sticky="nsew")
            return

        if choice == "Monthly Spend":
            fig, ax = plt.subplots(figsize=(7, 4))
            months = sorted(monthly.keys())
            ax.bar(months, [monthly[month] for month in months])
            ax.set_title("Monthly Spend")
            ax.tick_params(axis="x", rotation=45)
            FigureCanvasTkAgg(fig, master=self.summary_frame).get_tk_widget().grid(row=0, column=0, sticky="nsew")
            return

        if choice == "Cumulative Spend":
            fig, ax = plt.subplots(figsize=(7, 4))
            xs = [date_label for date_label, _running in cumulative_points]
            ys = [running for _date_label, running in cumulative_points]
            ax.plot(xs, ys, marker="o")
            ax.set_title("Cumulative Spend Over Time")
            ax.set_ylabel("Total")
            ax.tick_params(axis="x", rotation=45)
            FigureCanvasTkAgg(fig, master=self.summary_frame).get_tk_widget().grid(row=0, column=0, sticky="nsew")
            return

        if choice == "Limite vs Gasto por Tag":
            labels = list(tag_totals.keys())
            gastos = [tag_totals[tag] for tag in labels]
            limites = [self.tags.get(tag, {}).get("limit", 0) for tag in labels]
            fig, ax = plt.subplots(figsize=(7, 4))
            positions = range(len(labels))
            ax.bar([i - 0.2 for i in positions], gastos, width=0.4, label="Gasto")
            ax.bar([i + 0.2 for i in positions], limites, width=0.4, label="Limite")
            ax.set_xticks(list(positions))
            ax.set_xticklabels(labels, rotation=45, ha="right")
            ax.set_title("Limite vs Gasto por Tag")
            ax.legend()
            FigureCanvasTkAgg(fig, master=self.summary_frame).get_tk_widget().grid(row=0, column=0, sticky="nsew")
            return

        self._draw_average_spend_table(data_rows, selected)
```

- [ ] **Step 3: Add average spend summary table method**

Add this method:

```python
    def _draw_average_spend_table(self, data_rows, selected):
        limits = {tag: info.get("limit", 0) for tag, info in self.tags.items()}
        summary_data = average_spend_by_tag_month(data_rows, selected, limits)
        months = summary_data["months"]
        currencies_by_month = summary_data["currencies_by_month"]
        cols = ["Tag", "Limite", "Promedio", "Tag Total"] + [
            f"{month_key}_{currency}"
            for month_key in months
            for currency in currencies_by_month[month_key]
        ]

        table = ttk.Treeview(self.summary_frame, columns=cols, show="headings")
        table.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        vsb = ttk.Scrollbar(self.summary_frame, orient="vertical", command=table.yview)
        hsb = ttk.Scrollbar(self.summary_frame, orient="horizontal", command=table.xview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for column in cols:
            table.heading(column, text=column, anchor="center")
            table.column(column, width=110, anchor="e" if column != "Tag" else "w")
        table.tag_configure("over_limit", foreground="red")

        for tag in sorted(summary_data["tag_month_totals"]):
            limit = limits.get(tag, 0)
            average = summary_data["tag_average_by_month"].get(tag, 0)
            total = summary_data["tag_global_totals"].get(tag, 0)
            detail = [
                f"{summary_data['tag_month_totals'][tag].get(month_key, {}).get(currency):,.2f}"
                if summary_data["tag_month_totals"][tag].get(month_key, {}).get(currency)
                else ""
                for month_key in months
                for currency in currencies_by_month[month_key]
            ]
            row_tags = ["over_limit"] if summary_data["over_limit_by_tag"].get(tag) else []
            table.insert("", "end", values=[tag, f"{limit:,.2f}", f"{average:,.2f}", f"{total:,.2f}", *detail], tags=row_tags)
```

- [ ] **Step 4: Remove the old Summary popup button route**

Keep `open_summary` only if a menu still calls it. If no UI calls it, delete `open_summary` after verifying `draw_summary` covers all summary modes.

- [ ] **Step 5: Run tests**

Run:

```powershell
pytest -q
```

Expected: PASS.

- [ ] **Step 6: Manually verify summary view**

Run:

```powershell
python purchase_tagger_app.py
```

Expected:
- `Summaries` opens inside the workspace.
- Empty state appears before loading purchases.
- Chart controls are visible.
- After loading rows, each chart type renders without opening a popup.

- [ ] **Step 7: Commit summary view**

Run:

```powershell
git add purchase_tagger_app.py
git commit -m "Embed summaries in workspace"
```

---

### Task 6: Replace Tag Editor Popup With Tags Workspace

**Files:**
- Modify: `C:\Users\alram\PycharmProjects\pdfProject\purchase_tagger_app.py`

- [ ] **Step 1: Replace `_build_tags_view`**

Replace the temporary `_build_tags_view` with:

```python
    def _build_tags_view(self):
        self.workspace.grid_rowconfigure(1, weight=1)
        self._build_page_header(
            self.workspace,
            "Tags",
            "Manage tag names, keyword matching, and monthly limits.",
        )

        content = ctk.CTkFrame(self.workspace, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        left = self._panel(content, row=0, column=0, sticky="nsew", padx=(0, 12))
        right = self._panel(content, row=0, column=1, sticky="nsew")
        left.grid_rowconfigure(1, weight=1)
        right.grid_rowconfigure(3, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Tags", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))
        self.tag_listbox = tk.Listbox(left, exportselection=False, bd=0, highlightthickness=0)
        self.tag_listbox.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 10))
        self.tag_listbox.bind("<<ListboxSelect>>", self.load_tag_details)

        tag_buttons = ctk.CTkFrame(left, fg_color="transparent")
        tag_buttons.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        ctk.CTkButton(tag_buttons, text="Add", command=self.add_tag, width=70).pack(side="left", padx=(0, 8))
        ctk.CTkButton(tag_buttons, text="Edit", command=self.edit_tag, width=70, fg_color="#64748b").pack(side="left", padx=(0, 8))
        ctk.CTkButton(tag_buttons, text="Remove", command=self.remove_tag, width=80, fg_color="#b91c1c").pack(side="left")

        ctk.CTkLabel(right, text="Selected Tag", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))
        self.limit_var = tk.StringVar(value="0")
        ctk.CTkEntry(right, textvariable=self.limit_var, placeholder_text="Monthly limit").grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        ctk.CTkLabel(right, text="Keywords", text_color="#6b7280", font=ctk.CTkFont(size=12)).grid(row=2, column=0, sticky="w", padx=14)
        self.keyword_listbox = tk.Listbox(right, exportselection=False, bd=0, highlightthickness=0)
        self.keyword_listbox.grid(row=3, column=0, sticky="nsew", padx=14, pady=(6, 10))

        keyword_buttons = ctk.CTkFrame(right, fg_color="transparent")
        keyword_buttons.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 14))
        ctk.CTkButton(keyword_buttons, text="Add Keyword", command=self.add_keyword, width=110).pack(side="left", padx=(0, 8))
        ctk.CTkButton(keyword_buttons, text="Edit", command=self.edit_keyword, width=70, fg_color="#64748b").pack(side="left", padx=(0, 8))
        ctk.CTkButton(keyword_buttons, text="Remove", command=self.remove_keyword, width=85, fg_color="#b91c1c").pack(side="left", padx=(0, 8))
        ctk.CTkButton(keyword_buttons, text="Save", command=self.save_tags_from_view, width=80).pack(side="right")

        self.refresh_tag_lists()
```

- [ ] **Step 2: Add tag workspace helpers**

Add these methods or adapt existing `TagEditor` methods onto `PurchaseTaggerUI`:

```python
    def refresh_tag_lists(self):
        if not hasattr(self, "tag_listbox"):
            return
        self.tag_listbox.delete(0, "end")
        for tag in sorted(self.tags):
            self.tag_listbox.insert("end", tag)
        self.keyword_listbox.delete(0, "end")
        self.limit_var.set("0")

    def selected_tag_name(self):
        selection = self.tag_listbox.curselection()
        if not selection:
            return None
        return self.tag_listbox.get(selection[0])

    def load_tag_details(self, event=None):
        tag = self.selected_tag_name()
        if not tag:
            return
        self.keyword_listbox.delete(0, "end")
        for keyword in self.tags[tag]["keywords"]:
            self.keyword_listbox.insert("end", keyword)
        self.limit_var.set(str(self.tags[tag].get("limit", 0)))

    def save_current_tag_limit(self):
        tag = self.selected_tag_name()
        if not tag:
            return
        try:
            self.tags[tag]["limit"] = int(self.limit_var.get())
        except ValueError:
            messagebox.showwarning("Invalid Limit", "Limit must be a whole number.")
```

- [ ] **Step 3: Move tag add/edit/remove methods onto root**

Ensure `PurchaseTaggerUI` has these methods:

```python
    def add_tag(self):
        name = simple_input(self, "New Tag", "Tag name:")
        if name and name not in self.tags:
            self.tags[name] = {"keywords": [], "limit": 0}
            self.refresh_tag_lists()
            self.status_var.set(f"Added tag {name}")

    def edit_tag(self):
        old = self.selected_tag_name()
        if not old:
            return
        new = simple_input(self, "Edit Tag", f'New name for tag "{old}":', default=old)
        if new and new != old and new not in self.tags:
            self.tags[new] = self.tags.pop(old)
            self.refresh_tag_lists()
            self.status_var.set(f"Renamed tag {old} to {new}")

    def remove_tag(self):
        tag = self.selected_tag_name()
        if not tag:
            return
        if messagebox.askyesno("Confirm", f'Remove tag "{tag}"?'):
            del self.tags[tag]
            self.refresh_tag_lists()
            self.status_var.set(f"Removed tag {tag}")

    def add_keyword(self):
        tag = self.selected_tag_name()
        if not tag:
            return
        keyword = simple_input(self, "New Keyword", "Keyword:")
        if keyword:
            self.tags[tag]["keywords"].append(keyword)
            self.load_tag_details()

    def edit_keyword(self):
        tag = self.selected_tag_name()
        selection = self.keyword_listbox.curselection()
        if not tag or not selection:
            return
        index = selection[0]
        old = self.keyword_listbox.get(index)
        new = simple_input(self, "Edit Keyword", f'New value for keyword "{old}":', default=old)
        if new and new != old:
            self.tags[tag]["keywords"][index] = new
            self.load_tag_details()

    def remove_keyword(self):
        tag = self.selected_tag_name()
        selection = self.keyword_listbox.curselection()
        if not tag or not selection:
            return
        keyword = self.keyword_listbox.get(selection[0])
        if messagebox.askyesno("Confirm", f'Remove keyword "{keyword}"?'):
            self.tags[tag]["keywords"].remove(keyword)
            self.load_tag_details()

    def save_tags_from_view(self):
        self.save_current_tag_limit()
        save_tags(self.tags)
        self.status_var.set("Tags saved")
```

- [ ] **Step 4: Update tag assignment refresh behavior**

At the end of `assign_tag`, add:

```python
        self.apply_filter()
        self.status_var.set(f"Assigned tag {tag}")
```

At the end of `create_and_assign`, add:

```python
        self._refresh_filter_options()
```

- [ ] **Step 5: Remove old menu route**

Remove the old `Tags > Manage Tags...` menu from `__init__`, because tag editing now lives in the sidebar `Tags` view.

- [ ] **Step 6: Run tests**

Run:

```powershell
pytest -q
```

Expected: PASS.

- [ ] **Step 7: Manually verify Tags view**

Run:

```powershell
python purchase_tagger_app.py
```

Expected:
- `Tags` view lists tags.
- Selecting a tag shows keywords and limit.
- Add/edit/remove tag works.
- Add/edit/remove keyword works.
- Save writes `tags.json`.
- Right-click assignment in purchase table still works.

- [ ] **Step 8: Commit Tags view**

Run:

```powershell
git add purchase_tagger_app.py
git commit -m "Move tag management into workspace"
```

---

### Task 7: Final Polish, Docs, And Verification

**Files:**
- Modify: `C:\Users\alram\PycharmProjects\pdfProject\purchase_tagger_app.py`
- Modify: `C:\Users\alram\PycharmProjects\pdfProject\README.md`

- [ ] **Step 1: Add README dependency note**

In `README.md`, update the requirements section to mention that the desktop UI uses CustomTkinter. The runtime install command remains:

```bash
pip install -r requirements.txt
```

- [ ] **Step 2: Add README workflow note**

In the Usage section, replace references to `Tags > Manage Tags...` with:

```markdown
7. Use the **Tags** sidebar view to add, edit, or remove tags, keywords, and limits.
```

- [ ] **Step 3: Run full automated tests**

Run:

```powershell
pytest -q
```

Expected: PASS.

- [ ] **Step 4: Run import smoke checks**

Run:

```powershell
python -c "import customtkinter; import purchase_tagger_app; print('ok')"
```

Expected: prints `ok` and exits with code 0.

- [ ] **Step 5: Manual app verification**

Run:

```powershell
python purchase_tagger_app.py
```

Verify:
- Window opens with CustomTkinter sidebar.
- Sidebar navigation highlights active view.
- `Imports` contains file intake, KPI cards, filters, table, and totals.
- `Purchases` contains review table without file intake.
- `Summaries` renders embedded charts/tables.
- `Tags` manages tags and saves to `tags.json`.
- CSV export writes filtered rows.
- Search, currency, month, and tag filters work together.

- [ ] **Step 6: Commit final polish**

Run:

```powershell
git add purchase_tagger_app.py README.md
git commit -m "Polish CustomTkinter workspace UI"
```

---

## Self-Review Notes

- Spec coverage: sidebar shell, Imports, Purchases, Summaries, Tags, dependencies, feedback, styling, and testing are each mapped to tasks.
- Test-first coverage: pure filter/KPI/totals behavior is covered before UI migration. Existing row assignment behavior remains covered.
- Manual verification covers visual behavior that automated tests cannot safely assert in a desktop GUI.
