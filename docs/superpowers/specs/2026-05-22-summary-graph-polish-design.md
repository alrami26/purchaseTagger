# Summary Graph Polish Design

## Goal

Make the existing summary graphs easier to read and more useful for budget review, with an analytical visual style that highlights important spending status without changing the underlying summary calculations.

## Current Behavior

The Summaries view renders embedded Matplotlib charts from `purchase_tagger_app.py`:

- Spend by Tag pie chart.
- Monthly Spend bar chart.
- Cumulative Spend line chart.
- Limite vs Gasto por Tag grouped bar chart.

The charts use mostly default Matplotlib styling. They work functionally, but the visual hierarchy is plain and the limit comparison does not strongly communicate which tags need attention.

## Proposed Behavior

Apply the approved analytical chart direction:

- Use a clean light chart surface with muted axes and subtle horizontal grid lines.
- Use readable titles and label spacing across all chart types.
- Use consistent colors for ordinary spending charts.
- Use status colors in the limit-vs-spend chart so over-limit categories are immediately visible.
- Keep all existing chart choices, filters, currency rules, and empty-state behavior.
- Keep chart rendering inside the existing `summary_frame`.

## Architecture

The change should stay in `purchase_tagger_app.py` and focus on chart presentation only.

Add small helper methods on `PurchaseTaggerUI` for chart styling and status coloring, such as:

- `_style_summary_axes(ax, title, ylabel=None)`
- `_summary_status_color(spend, limit)`
- `_finalize_summary_figure(fig)`

`draw_summary()` should continue to gather rows, selected currency, month filters, and summary aggregates exactly as it does now. Each chart branch should call the shared styling helpers after plotting.

## Data Flow

The data flow remains unchanged:

1. `draw_summary()` reads `self.all_rows`.
2. Month and currency filters are applied.
3. `summary_aggregates()` computes tag totals, monthly totals, cumulative spend, and limit comparison data.
4. Matplotlib renders the selected chart.
5. `FigureCanvasTkAgg` embeds the result in `summary_frame`.

Only the Matplotlib presentation layer changes.

## Error and Empty States

Existing empty and invalid selection messages should remain unchanged:

- No loaded purchases.
- No selected currency.
- More than one selected currency.
- No chart data for the selected summary.

The styling helpers should not run when no figure is created.

## Testing

Tests should verify presentation intent without depending on exact pixels:

- Shared summary chart styling sets titles, grid visibility, and a light figure surface.
- Limit-vs-spend bars use an alert color when spend exceeds the configured limit.
- Existing `draw_summary()` behavior still uses all rows and respects selected month and currency.

Manual verification should open the app, load sample rows, and inspect each summary chart for readable labels, clean spacing, and clear over-limit emphasis.

## Scope

This design does not add new chart types, change summary calculations, add interactive tooltips, replace Matplotlib, or redesign the full Summaries view layout.
