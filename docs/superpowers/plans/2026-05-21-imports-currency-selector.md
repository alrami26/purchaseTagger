# Imports Currency Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Imports overview select a currency so mixed-currency imports can populate insight fields.

**Architecture:** Add a separate `import_currency_var` state on `PurchaseTaggerUI`. `_import_overview_data()` will choose a valid selected currency from loaded rows and compute top tag, largest purchase, over-limit count, headline, and detail for that selected currency while keeping general import counts across all rows. `_build_import_overview()` will render a CustomTkinter option menu when currency choices exist.

**Tech Stack:** Python, CustomTkinter, tkinter test fakes, pytest.

---

### Task 1: Selected Currency Data

**Files:**
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/test_purchase_tagger_app.py`
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/purchase_tagger_app.py`

- [ ] **Step 1: Write failing tests**

Update the multiple-currency overview test so `app.import_currency_var = SimpleVar("USD")` and assert:

```python
data["selected_currency"] == "USD"
data["currency_options"] == ["CRC", "USD"]
data["top_tag"] == "Dining 80.00"
data["largest_purchase"] == "CAFE USD 80.00"
data["headline"] == "Dining is driving this period's spend."
```

Add a second test where `app.import_currency_var = SimpleVar("EUR")` with only USD/CRC loaded, and assert it falls back to `"CRC"` because options are sorted alphabetically.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest test_purchase_tagger_app.py::PurchaseTaggerBrowseTest::test_import_overview_data_keeps_general_counts_for_multiple_currencies -q`

Expected: FAIL because mixed-currency overview still returns neutral insight text.

- [ ] **Step 3: Implement selected currency handling**

Add `self.import_currency_var = tk.StringVar(value="")` in `__init__`. Update `_clear_workspace_widget_refs()` to clear `import_currency_menu`. Update `_import_overview_data()` to return `currency_options` and `selected_currency`, choose the current import currency when valid, and set the variable to the chosen currency when the variable exists.

- [ ] **Step 4: Run data tests**

Run: `python -m pytest test_purchase_tagger_app.py::PurchaseTaggerBrowseTest::test_import_overview_data_keeps_general_counts_for_multiple_currencies -q`

Expected: PASS.

### Task 2: Imports Currency Selector UI

**Files:**
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/test_purchase_tagger_app.py`
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/purchase_tagger_app.py`

- [ ] **Step 1: Write failing UI tests**

Extend the import overview UI test data with:

```python
"currency_options": ["CRC", "USD"],
"selected_currency": "USD",
```

Patch `purchase_tagger_app.ctk.CTkOptionMenu` and assert it is created with those values and `variable is app.import_currency_var`.

- [ ] **Step 2: Run UI test and verify failure**

Run: `python -m pytest test_purchase_tagger_app.py::PurchaseTaggerBrowseTest::test_import_overview_renders_general_information_labels -q`

Expected: FAIL because the option menu is not created.

- [ ] **Step 3: Implement option menu**

In `_build_import_overview()`, render a `"Currency"` label and `CTkOptionMenu` near the overview heading when `data["currency_options"]` is non-empty. Its command should call `self.show_view("Imports")` so the overview is rebuilt using the new selected currency.

- [ ] **Step 4: Run UI test**

Run: `python -m pytest test_purchase_tagger_app.py::PurchaseTaggerBrowseTest::test_import_overview_renders_general_information_labels -q`

Expected: PASS.

### Task 3: Verification

**Files:**
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/test_purchase_tagger_app.py`
- Modify: `C:/Users/alram/PycharmProjects/pdfProject/purchase_tagger_app.py`

- [ ] **Step 1: Run focused tests**

Run: `python -m pytest test_purchase_tagger_app.py -q`

Expected: PASS.

- [ ] **Step 2: Run full suite**

Run: `python -m pytest -q`

Expected: PASS.
