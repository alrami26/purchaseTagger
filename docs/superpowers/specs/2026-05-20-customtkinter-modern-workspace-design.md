# CustomTkinter Modern Workspace Design

## Goal

Modernize the PDF Purchase Tagger UI so it feels like a current desktop productivity app while preserving the existing purchase extraction, tagging, filtering, summary, and CSV export behavior.

The redesign will move the app from classic `tkinter/ttk` styling to a `customtkinter` workspace shell. The target experience is a calm financial review tool: easy to scan, efficient for repeated use, and visually clearer than the current single-window utility layout.

## Design Direction

Use a two-region application layout:

- A persistent left sidebar for navigation.
- A main workspace that changes by selected view.

The sidebar will include:

- App title: `Purchase Tagger`.
- Navigation items: `Imports`, `Purchases`, `Summaries`, `Tags`.
- A small status area for last processed state or current file count.

The main workspace will use a light neutral background, white content panels, 8px rounded corners, restrained borders, and a single blue accent for primary actions. Text hierarchy should be tighter and more intentional than the current UI: large page title, small supporting metadata, compact table text, and strong numeric totals.

## Views

### Imports

The `Imports` view is the default first screen. It focuses on selecting PDFs, processing them, and reviewing the resulting purchases.

It will include:

- Header with page title and primary `Load & Tag` action.
- File intake panel showing selected PDF file names.
- `Browse` and `Clear` actions.
- KPI cards for purchase count, untagged count, currency count, and over-limit tag count.
- Filter toolbar with search, currency, month, tag, reset, and export actions.
- Purchase table with date, description, amount, currency, and tag columns.
- Footer showing visible row count and totals by currency.

### Purchases

The first implementation will make `Purchases` a dedicated navigation state that shows the same purchase table and filter toolbar used by `Imports`, without the file intake panel. It focuses on reviewing and correcting rows after import. It should support the existing right-click tag assignment behavior, adapted to CustomTkinter-compatible menus or controls.

`Imports` and `Purchases` can share internal table-refresh code, but the visible layouts should differ: `Imports` includes file selection and processing controls, while `Purchases` is a cleaner review surface.

### Summaries

The `Summaries` view replaces the current summary popup as the primary summary experience.

It will include:

- Chart type selector for the existing summary modes.
- Currency filters.
- Month filter.
- Embedded Matplotlib chart area.
- Table presentation for `Gasto Promedio por Tag/Mes`.

The existing popup summary should be replaced by the embedded `Summaries` view for the first implementation. Summary controls and chart rendering should live inside the workspace.

### Tags

The first implementation will replace the current `TagEditor` popup with a `Tags` workspace view.

It will include:

- Tag list panel.
- Keyword list/editor panel.
- Limit input.
- Add, edit, remove, save, and discard actions.

The save behavior remains backed by `tags.json` through `load_tags` and `save_tags`.

## Component Model

The app should be broken into focused UI units:

- `PurchaseTaggerUI`: root window, app state, navigation, shared actions.
- `Sidebar`: navigation and status display.
- `ImportsView`: file intake, KPI cards, filters, purchase table, totals footer.
- `SummaryView`: summary controls and chart/table rendering.
- `TagsView`: tag and keyword management inside the workspace.
- Small helper functions for styling, KPI calculation, table refresh, and filter state.

This can still live in `purchase_tagger_app.py` at first, but the implementation should create clear class/function boundaries so future extraction into separate files is straightforward.

## Data Flow

The existing data model remains:

- `self.pdf_files`: selected PDF paths.
- `self.tags`: tag configuration loaded from `tags.json`.
- `self.all_rows`: all processed purchase rows.
- `self.filtered_rows`: rows after active filters.

The filter state should expand from text-only search to include:

- Search text.
- Selected currencies.
- Selected month.
- Selected tag.

The table refresh flow should be:

1. User selects files.
2. User runs `Load & Tag`.
3. App calls `process_purchases` for each PDF.
4. Rows are stored in `self.all_rows`.
5. Filters are applied into `self.filtered_rows`.
6. Table, KPI cards, and totals footer refresh from the filtered rows.

## Error Handling And Feedback

The UI should reduce disruptive message boxes where possible.

Use inline status text for:

- Selected file count.
- Loading/processing state.
- Empty table state.
- Export success.

Keep message boxes for:

- File processing errors.
- Save failures.
- Destructive confirmations, such as deleting a tag or keyword.

During PDF processing, disable the primary `Load & Tag` button and show a busy/progress state. If processing remains synchronous for the first implementation, this still improves perceived clarity even without background threading.

## Styling

Use `customtkinter` with a light theme by default.

Recommended style choices:

- Background: `#f4f6f8`.
- Sidebar: `#1f2633`.
- Primary action: `#2563eb`.
- Text: `#171a20`.
- Secondary text: `#6b7280`.
- Panel background: white or near-white.
- Border color: `#e0e5ec`.
- Radius: 8px for panels and compact controls.

Avoid a decorative landing-page feel. This is a finance review utility, so density, scanability, and predictable controls matter more than large hero elements.

## Dependencies

Add `customtkinter` to runtime dependencies.

Existing dependencies remain:

- `pypdf`
- `matplotlib`

Tkinter is still part of the Python standard library and can be used where CustomTkinter does not provide a direct replacement, such as `ttk.Treeview` for the purchase table.

## Testing

Keep existing behavior covered by current tests.

Add or update tests only where non-visual logic changes:

- Filter state calculation.
- KPI calculation.
- Totals by currency.
- Tag save/update behavior if refactored.

Manual verification should cover:

- App starts successfully.
- PDFs can be selected.
- Purchases load and display.
- Search and filters update the table.
- Totals and KPI cards update.
- Summary charts render.
- Tags can be added, edited, removed, and saved.
- CSV export still writes filtered rows.

## Implementation Scope

This redesign should prioritize a working modern shell over a full rewrite. Keep the extraction, summary, tag storage, and testable business logic intact. The main work is reorganizing the UI, adding CustomTkinter styling, and improving feedback and layout.

The first implementation pass should avoid background threading, drag-and-drop, dark mode, and advanced chart redesign unless they become necessary to make the new workspace coherent.
