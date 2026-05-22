# Imports Overview and Insights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Convert Imports into a PDF loading and overview dashboard with general information and insight data, leaving Purchases as the detailed table workspace.

**Architecture:** Keep the current `PurchaseTaggerUI` structure and add small UI/data helpers in `purchase_tagger_app.py`. Reuse existing `summary_insights()`, `available_months()`, `parse_purchase_date()`, `format_amount()`, and tag limit data instead of creating persisted import batches.

**Tech Stack:** Python, CustomTkinter, tkinter test fakes, pytest.

---

### Task 1: Imports View Composition

**Files:**
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/test_purchase_tagger_app.py`
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/purchase_tagger_app.py`

- [x] **Step 1: Write the failing test**

Add this assertion to `PurchaseTaggerBrowseTest.test_imports_view_has_no_manual_load_and_tag_header_button`:

```python
app._build_import_overview = Mock()
...
app._build_import_overview.assert_called_once()
app._build_filter_toolbar.assert_not_called()
app._build_purchase_table.assert_not_called()
app._build_totals_footer.assert_not_called()
```

- [x] **Step 2: Run the focused failing test**

Run: `python -m pytest test_purchase_tagger_app.py::PurchaseTaggerBrowseTest::test_imports_view_has_no_manual_load_and_tag_header_button -q`

Expected: FAIL because `_build_import_overview` is not called.

- [x] **Step 3: Update Imports composition**

In `_build_imports_view()`, set the content row weight for the overview and replace:

```python
self._build_filter_toolbar(content, row=2)
self._build_purchase_table(content, row=3)
self._build_totals_footer(content, row=4)
self.apply_filter()
```

with:

```python
self._build_import_overview(content, row=2)
self.apply_filter()
```

- [x] **Step 4: Run the focused test**

Run: `python -m pytest test_purchase_tagger_app.py::PurchaseTaggerBrowseTest::test_imports_view_has_no_manual_load_and_tag_header_button -q`

Expected: PASS.

### Task 2: Import Overview Data Helper

**Files:**
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/test_purchase_tagger_app.py`
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/purchase_tagger_app.py`

- [x] **Step 1: Write data helper tests**

Add tests that create a `PurchaseTaggerUI` instance via `object.__new__`, set `pdf_files`, `all_rows`, `tags`, and `natag`, then call `_import_overview_data()`.

Single-currency expected values:

```python
app.pdf_files = ["jan.pdf", "feb.pdf"]
app.all_rows = [
    ["01-ENE-25", "CAFE", "80.00", "USD", "Dining"],
    ["02-FEB-25", "MARKET", "90.00", "USD", "Groceries"],
    ["03-FEB-25", "UNKNOWN", "10.00", "USD", "N/A"],
]
app.tags = {"Dining": {"limit": Decimal("50.00")}, "Groceries": {"limit": Decimal("200.00")}}
app.natag = "N/A"
```

Assert:

```python
data["file_count"] == 2
data["purchase_count"] == 3
data["currencies"] == "USD"
data["untagged_count"] == 1
data["over_limit_count"] == 1
data["month_range"] == "2025-01 to 2025-02"
data["top_tag"] == "Groceries 90.00"
data["largest_purchase"] == "MARKET USD 90.00"
data["headline"] == "Dining is over its limit by USD 30.00."
```

Multiple-currency expected values:

```python
app.pdf_files = ["mixed.pdf"]
app.all_rows = [
    ["01-ENE-25", "CAFE", "80.00", "USD", "Dining"],
    ["02-FEB-25", "MARKET", "90.00", "CRC", "Groceries"],
]
```

Assert:

```python
data["currencies"] == "CRC, USD"
data["top_tag"] == "Select one currency"
data["largest_purchase"] == "Select one currency"
data["headline"] == "Multiple currencies loaded."
```

- [x] **Step 2: Run the new helper tests**

Run: `python -m pytest test_purchase_tagger_app.py -q`

Expected: FAIL because `_import_overview_data()` does not exist.

- [x] **Step 3: Implement the data helper**

Add `_import_overview_data()` plus `_format_import_month_range()` to `PurchaseTaggerUI`. The helper should:

```python
rows = list(getattr(self, "all_rows", []))
currencies = sorted({row[3] for row in rows if len(row) > 3 and row[3]})
limits = {tag: info.get("limit", ZERO) for tag, info in getattr(self, "tags", {}).items()}
```

Use `summary_insights(rows, {currencies[0]}, limits, natag=self.natag)` only when `len(currencies) == 1`; otherwise use neutral insight text. Count untagged rows where `row[4] == self.natag`. Count over-limit tags from the single-currency insight data when available.

- [x] **Step 4: Run the helper tests**

Run: `python -m pytest test_purchase_tagger_app.py -q`

Expected: PASS or failures only in tests that now need UI helper wiring.

### Task 3: Import Overview UI

**Files:**
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/test_purchase_tagger_app.py`
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/purchase_tagger_app.py`

- [x] **Step 1: Write UI construction test**

Add a test that patches `ctk.CTkLabel`, `ctk.CTkFrame`, and `ctk.CTkFont`, calls `_build_import_overview(FakeFrame(), row=2)`, and asserts labels include these text values:

```python
"Import Overview"
"Files"
"Purchases Loaded"
"Currencies"
"Month Coverage"
"Untagged"
"Over Limit"
"Top Tag"
"Largest Purchase"
"Insights"
```

- [x] **Step 2: Run the UI test**

Run: `python -m pytest test_purchase_tagger_app.py::PurchaseTaggerBrowseTest::test_import_overview_renders_general_information_labels -q`

Expected: FAIL because `_build_import_overview()` does not exist.

- [x] **Step 3: Implement the UI helper**

Add `_build_import_overview(parent, row)` to `PurchaseTaggerUI`. It should create a panel, render compact stat blocks from `_import_overview_data()`, and show an insight callout. Use fixed labels and `wraplength` values so long descriptions do not collide.

- [x] **Step 4: Run the UI test**

Run: `python -m pytest test_purchase_tagger_app.py::PurchaseTaggerBrowseTest::test_import_overview_renders_general_information_labels -q`

Expected: PASS.

### Task 4: Verification

**Files:**
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/test_purchase_tagger_app.py`
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/purchase_tagger_app.py`

- [x] **Step 1: Run focused tests**

Run: `python -m pytest test_purchase_tagger_app.py -q`

Expected: PASS.

- [x] **Step 2: Run full suite**

Run: `python -m pytest -q`

Expected: PASS.

- [x] **Step 3: Review git diff**

Run: `git diff -- purchase_tagger_app.py test_purchase_tagger_app.py docs/superpowers/plans/2026-05-21-imports-overview-insights.md`

Expected: Diff contains only the Imports overview implementation, tests, and this plan.
