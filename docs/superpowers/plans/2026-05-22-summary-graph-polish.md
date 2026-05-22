# Summary Graph Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the existing summary graph styling with an analytical visual direction that makes spending and over-limit status easier to read.

**Architecture:** Keep summary data flow unchanged in `PurchaseTaggerUI.draw_summary()`. Add small chart presentation helpers in `purchase_tagger_app.py` and focused unit tests in `test_purchase_tagger_app.py`.

**Tech Stack:** Python, CustomTkinter, Tkinter, Matplotlib, pytest/unittest.

---

## File Structure

- Modify `purchase_tagger_app.py`: add shared Matplotlib styling helpers and apply them inside `draw_summary()`.
- Modify `test_purchase_tagger_app.py`: extend fake Matplotlib classes and add presentation-focused tests.

### Task 1: Add Summary Chart Styling Tests

**Files:**
- Modify: `test_purchase_tagger_app.py`

- [ ] **Step 1: Extend fake Matplotlib helpers**

Update `FakeAxes` and `FakeFigure` so tests can inspect styling calls:

```python
class FakeAxis:
    def __init__(self):
        self.visible = True

    def set_visible(self, visible):
        self.visible = visible


class FakeSpine:
    def __init__(self):
        self.visible = True

    def set_visible(self, visible):
        self.visible = visible


class FakeAxes:
    def __init__(self):
        self.title = None
        self.ylabel = None
        self.facecolor = None
        self.grid_calls = []
        self.tick_params_calls = []
        self.bar_calls = []
        self.spines = {name: FakeSpine() for name in ("top", "right", "left", "bottom")}
        self.yaxis = FakeAxis()

    def bar(self, *args, **kwargs):
        self.bar_calls.append((args, kwargs))
```

- [ ] **Step 2: Add tests for helper styling and status colors**

Add tests near the existing summary tests:

```python
def test_style_summary_axes_applies_analytical_presentation(self):
    app = object.__new__(PurchaseTaggerUI)
    ax = FakeAxes()

    app._style_summary_axes(ax, "Monthly Spend", ylabel="Total")

    self.assertEqual(ax.title, "Monthly Spend")
    self.assertEqual(ax.ylabel, "Total")
    self.assertEqual(ax.facecolor, "#ffffff")
    self.assertTrue(ax.grid_calls)
    self.assertFalse(ax.spines["top"].visible)
    self.assertFalse(ax.spines["right"].visible)


def test_summary_status_color_marks_over_limit_spend(self):
    app = object.__new__(PurchaseTaggerUI)

    self.assertEqual(app._summary_status_color(80.0, 50.0), "#dc2626")
    self.assertEqual(app._summary_status_color(40.0, 50.0), "#2563eb")
    self.assertEqual(app._summary_status_color(40.0, 0.0), "#2563eb")
```

- [ ] **Step 3: Run tests to verify failure**

Run: `python -m pytest test_purchase_tagger_app.py::PurchaseTaggerUITest::test_style_summary_axes_applies_analytical_presentation test_purchase_tagger_app.py::PurchaseTaggerUITest::test_summary_status_color_marks_over_limit_spend -q`

Expected: FAIL because `_style_summary_axes` and `_summary_status_color` do not exist yet.

### Task 2: Implement Shared Chart Styling Helpers

**Files:**
- Modify: `purchase_tagger_app.py`

- [ ] **Step 1: Add helpers before `draw_summary()`**

```python
    def _style_summary_axes(self, ax, title, ylabel=None):
        ax.set_facecolor("#ffffff")
        ax.set_title(title, loc="left", pad=14, fontsize=13, fontweight="bold", color="#111827")
        if ylabel:
            ax.set_ylabel(ylabel, color="#4b5563")
        ax.grid(axis="y", color="#e5e7eb", linewidth=0.8)
        ax.tick_params(axis="both", colors="#4b5563", labelsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color("#d1d5db")
        ax.yaxis.set_visible(True)

    def _summary_status_color(self, spend, limit):
        if limit and spend > limit:
            return "#dc2626"
        return "#2563eb"

    def _finalize_summary_figure(self, fig):
        fig.patch.set_facecolor("#ffffff")
        fig.tight_layout(pad=2.0)
```

- [ ] **Step 2: Run helper tests**

Run: `python -m pytest test_purchase_tagger_app.py::PurchaseTaggerUITest::test_style_summary_axes_applies_analytical_presentation test_purchase_tagger_app.py::PurchaseTaggerUITest::test_summary_status_color_marks_over_limit_spend -q`

Expected: PASS.

### Task 3: Apply Styling To Summary Charts

**Files:**
- Modify: `purchase_tagger_app.py`
- Modify: `test_purchase_tagger_app.py`

- [ ] **Step 1: Update chart branches in `draw_summary()`**

Use the helpers after each plot:

```python
        fig, ax = plt.subplots(figsize=(7, 4.5))
        if choice == "Spend by Tag":
            if tag_totals:
                colors = ["#2563eb", "#16a34a", "#f59e0b", "#7c3aed", "#0891b2", "#db2777", "#64748b"]
                ax.pie(
                    [float(value) for value in tag_totals.values()],
                    labels=tag_totals.keys(),
                    autopct="%1.1f%%",
                    startangle=90,
                    colors=colors[:len(tag_totals)],
                    wedgeprops={"linewidth": 1, "edgecolor": "#ffffff"},
                    textprops={"color": "#374151", "fontsize": 9},
                )
            self._style_summary_axes(ax, "Spend by Tag")
        elif choice == "Monthly Spend":
            months = sorted(monthly.keys())
            ax.bar(months, [float(monthly[month]) for month in months], color="#2563eb", width=0.6)
            self._style_summary_axes(ax, "Monthly Spend", ylabel="Total")
            ax.tick_params(axis="x", rotation=45)
```

For limit comparison, color spend bars per status:

```python
            spend_colors = [self._summary_status_color(spend_value, limit_value) for spend_value, limit_value in zip(spend, limits)]
            ax.bar([x - 0.2 for x in x_values], spend, width=0.4, label="Gasto", color=spend_colors)
            ax.bar([x + 0.2 for x in x_values], limits, width=0.4, label="Limite", color="#9ca3af")
            self._style_summary_axes(ax, "Comparacion: Limite vs Gasto por Tag", ylabel="Total")
```

Replace `fig.tight_layout()` with:

```python
        self._finalize_summary_figure(fig)
```

- [ ] **Step 2: Add a draw test for over-limit bar colors**

```python
def test_draw_summary_limit_chart_uses_alert_color_for_over_limit_tags(self):
    app = object.__new__(PurchaseTaggerUI)
    app.all_rows = [["01-ENE-25", "CAFE", "80.00", "USD", "Dining"]]
    app.summary_frame = FakeFrame()
    app.summary_currency_vars = {"USD": SimpleVar(True)}
    app.summary_month_var = SimpleVar("Todos")
    app.summary_choice_var = SimpleVar("Limite vs Gasto por Tag")
    app.tags = {"Dining": {"limit": 50}}
    ax = FakeAxes()

    with patch("purchase_tagger_app.filter_rows_by_month", side_effect=lambda rows, month: list(rows)), \
            patch("purchase_tagger_app.summary_aggregates", return_value={
                "tag_totals": {"Dining": Decimal("80.00")},
                "monthly_totals": {},
                "cumulative_points": [],
            }), \
            patch("purchase_tagger_app.plt.subplots", return_value=(FakeFigure(), ax)), \
            patch("purchase_tagger_app.FigureCanvasTkAgg", return_value=FakeCanvas()):
        app.draw_summary()

    self.assertEqual(ax.bar_calls[0][1]["color"], ["#dc2626"])
```

- [ ] **Step 3: Run focused summary tests**

Run: `python -m pytest test_purchase_tagger_app.py -q`

Expected: PASS.

### Task 4: Final Verification

**Files:**
- No code changes unless verification finds a defect.

- [ ] **Step 1: Run the project tests**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 2: Check git status**

Run: `git status --short --branch`

Expected: only graph polish implementation files are modified unless commits were created during execution.
