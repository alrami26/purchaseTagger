# Imports Overview and Insights Design

## Goal

Make the Imports view distinct from Purchases. Imports should focus on loading PDFs and showing general information about the imported data, while Purchases remains the detailed searchable and editable purchase table.

## Current Behavior

The Imports view currently builds the file picker, KPI row, filters, purchase table, and totals footer. Purchases builds almost the same KPI, filter, table, and footer workflow. This makes the two views feel nearly identical once PDFs are loaded.

## Proposed Behavior

Imports becomes a load-and-overview dashboard:

- Keep the existing selected-PDF panel with Browse & Tag and Clear actions.
- Replace the duplicated filter toolbar, purchase table, and totals footer with import-level overview panels.
- Show general import information from all loaded rows:
  - total purchases loaded
  - number of selected PDF files
  - detected currencies
  - untagged purchase count
  - over-limit tag count
  - month coverage or date range
  - top spending tag, when one currency can be inferred
  - largest purchase, when one currency can be inferred
- Show an insight callout using the existing summary insight logic when the imported rows contain exactly one currency.
- Show a clear fallback message when no data has been loaded.
- Preserve the existing Purchases view as the place for row search, filtering, tag correction, totals, and CSV export.

## Architecture

The change should stay inside the current UI structure in `purchase_tagger_app.py` and reuse existing helpers before adding new ones.

The Imports view should continue to call `_build_file_panel()` and `_build_kpi_row()`. It should then build a new overview section instead of calling `_build_filter_toolbar()`, `_build_purchase_table()`, and `_build_totals_footer()`.

The overview section can use small focused helpers on `PurchaseTaggerUI`, such as:

- `_build_import_overview(parent, row)`
- `_import_overview_data()`
- `_format_import_month_range(rows)`

Those helpers should read from `self.all_rows`, `self.pdf_files`, `self.tags`, and existing summary helpers. They should not introduce a new persisted data shape.

## Data Flow

Loading PDFs stays unchanged:

1. User selects PDFs in Imports.
2. `browse_pdf()` stores paths and calls `load()`.
3. `load()` populates `self.all_rows`.
4. `apply_filter()` refreshes shared KPI state.
5. The Imports overview renders aggregate information from `self.all_rows`.

Purchases continues to use `self.filtered_rows` for table display and filter/export behavior.

## Error and Empty States

When no PDFs are selected or no rows are loaded, Imports should show a calm empty overview message rather than a blank table.

When imported rows contain multiple currencies, the overview should still show general counts and currency names. Currency-specific insight fields should use a neutral message, because the existing summary calculations intentionally require exactly one selected currency.

If malformed dates or amounts exist, the overview should tolerate them and show available information from valid rows.

## Testing

Tests should verify:

- `_build_imports_view()` no longer builds the purchase table, filter toolbar, or totals footer.
- `_build_imports_view()` builds the file panel, KPI row, and import overview.
- Import overview data reports selected file count, total purchases, currencies, untagged count, and over-limit count.
- Single-currency imports can display top-tag and largest-purchase insight data.
- Multiple-currency imports avoid currency-specific insights while still showing general import information.

## Scope

This design does not add import history, persistent batch records, PDF-level row grouping, or a new export flow. Those can be added later if the app needs deeper audit or reconciliation features.
