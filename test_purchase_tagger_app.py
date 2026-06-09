import unittest
import json
from decimal import Decimal
import os
import tempfile
from unittest.mock import Mock, patch

from purchase_tagger_app import (
    DEFAULT_WINDOW_GEOMETRY,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    PurchaseTaggerUI,
    display_purchase_row,
)
from views import tags as tags_view


class FakeTree:
    def __init__(self, visible_order=None):
        if visible_order is None:
            visible_order = []
        self.visible_order = list(visible_order)
        self.items = {}
        self.deleted = []
        self.tags = {}

    def index(self, item_iid):
        return self.visible_order.index(item_iid)

    def item(self, item_iid, values=None):
        if values is not None:
            self.items[item_iid] = list(values)
        return {"values": self.items.get(item_iid)}

    def get_children(self, parent=""):
        return list(self.visible_order)

    def delete(self, item_iid):
        self.deleted.append(item_iid)
        self.items.pop(item_iid, None)
        if item_iid in self.visible_order:
            self.visible_order.remove(item_iid)

    def insert(self, parent, index, values=None, tags=()):
        iid = f"item-{len(self.items) + 1}"
        self.visible_order.append(iid)
        self.items[iid] = list(values or [])
        self.tags[iid] = tags
        return iid

    def tag_configure(self, tag_name, **options):
        self.tags[tag_name] = options

    def set(self, item_iid, column):
        values = self.items[item_iid]
        if len(values) > 5:
            columns = {"date": 0, "description": 1, "sign": 2, "amount": 3, "currency": 4, "tag": 5}
        else:
            columns = {"date": 0, "description": 1, "amount": 2, "currency": 3, "tag": 4}
        return values[columns[column]]

    def move(self, item_iid, parent, index):
        self.visible_order.remove(item_iid)
        self.visible_order.insert(index, item_iid)

    def heading(self, col, command=None):
        pass

    def winfo_exists(self):
        return 1


class FakeMenu:
    def __init__(self):
        self.values = []
        self.state = "normal"

    def configure(self, **kwargs):
        if "values" in kwargs:
            self.values = list(kwargs["values"])
        if "state" in kwargs:
            self.state = kwargs["state"]


class DeadTree:
    def winfo_exists(self):
        return 0

    def get_children(self):
        raise AssertionError("destroyed tree should not be queried")


class SimpleVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeListbox:
    def __init__(self):
        self.items = []
        self.selection = []
        self.grid_options = None
        self.bound_events = {}
        self.state = "normal"
        self.visible = False

    def grid(self, **kwargs):
        if kwargs:
            self.grid_options = kwargs
        self.visible = True

    def grid_remove(self):
        self.visible = False

    def bind(self, event, callback):
        self.bound_events[event] = callback

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]

    def delete(self, first, last=None):
        if first == 0 and last == "end":
            self.items = []
            self.selection = []
            return
        del self.items[first]
        self.selection = [index for index in self.selection if index != first]

    def insert(self, index, value):
        if index == "end":
            self.items.append(value)
        else:
            self.items.insert(index, value)

    def curselection(self):
        return tuple(self.selection)

    def get(self, index):
        return self.items[index]

    def selection_set(self, index):
        self.selection = [index]

    def selection_clear(self, first, last=None):
        self.selection = []


class FakeFrame:
    def __init__(self, children=None):
        self.children = list(children or [])
        self.grid_rows = {}
        self.grid_columns = {}

    def winfo_children(self):
        return list(self.children)

    def grid_rowconfigure(self, row, weight=0, **kwargs):
        self.grid_rows[row] = {"weight": weight, **kwargs}

    def grid_columnconfigure(self, column, weight=0, **kwargs):
        self.grid_columns[column] = {"weight": weight, **kwargs}

    def update_idletasks(self):
        pass


class FakeWidget:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.grid_options = None
        self.packed = False
        self.destroyed = False
        self.state = kwargs.get("state", "normal")
        self.visible = False
        self.textvariable = kwargs.get("textvariable")
        self.value = ""

    def grid(self, **kwargs):
        if kwargs:
            self.grid_options = kwargs
        self.visible = True

    def grid_remove(self):
        self.visible = False

    def pack(self, **kwargs):
        self.packed = True

    def destroy(self):
        self.destroyed = True

    def set(self, *args):
        if args:
            self.value = args[0]
            if self.textvariable is not None:
                self.textvariable.set(args[0])

    def get(self):
        if self.textvariable is not None:
            return self.textvariable.get()
        return self.value

    def delete(self, first, last=None):
        self.value = ""
        if self.textvariable is not None:
            self.textvariable.set("")

    def insert(self, index, value):
        self.value = value
        if self.textvariable is not None:
            self.textvariable.set(value)

    def configure(self, **kwargs):
        self.kwargs.update(kwargs)
        if "state" in kwargs:
            self.state = kwargs["state"]


class FakeCtkFrame(FakeFrame):
    instances = []

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.args = args
        self.kwargs = kwargs
        self.grid_options = None
        self.visible = False
        FakeCtkFrame.instances.append(self)

    def grid(self, **kwargs):
        if kwargs:
            self.grid_options = kwargs
        self.visible = True

    def grid_remove(self):
        self.visible = False


class FakeCtkTabview:
    instances = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.grid_options = None
        self.tab_names = []
        self.tabs = {}
        self.selected = None
        self.command = kwargs.get("command")
        FakeCtkTabview.instances.append(self)

    def add(self, name):
        self.tab_names.append(name)
        if self.selected is None:
            self.selected = name
        self.tabs[name] = FakeCtkFrame()
        return self.tabs[name]

    def get(self):
        return self.selected

    def set(self, name):
        self.selected = name
        if self.command is not None:
            self.command()

    def grid(self, **kwargs):
        self.grid_options = kwargs


def fake_widget_descends_from(widget, ancestor):
    current = widget
    while current is not None:
        if current is ancestor:
            return True
        args = getattr(current, "args", ())
        current = args[0] if args else None
    return False


def attach_tag_detail_widgets(app):
    widgets = [FakeWidget(), FakeMenu(), FakeListbox(), FakeWidget()]
    app.tag_detail_widgets = widgets
    return widgets


class FakeCanvas:
    def __init__(self):
        self.widget = FakeWidget()

    def get_tk_widget(self):
        return self.widget

    def draw(self):
        pass


class FakeAxis:
    def __init__(self):
        self.visible = True

    def set_visible(self, visible):
        self.visible = visible


class FakeSpine:
    def __init__(self):
        self.visible = True
        self.color = None

    def set_visible(self, visible):
        self.visible = visible

    def set_color(self, color):
        self.color = color

    def set_facecolor(self, color):
        self.color = color


class FakeAxes:
    def __init__(self):
        self.title = None
        self.title_kwargs = {}
        self.ylabel = None
        self.ylabel_kwargs = {}
        self.facecolor = None
        self.grid_calls = []
        self.tick_params_calls = []
        self.bar_calls = []
        self.pie_calls = []
        self.plot_calls = []
        self.spines = {name: FakeSpine() for name in ("top", "right", "left", "bottom")}
        self.yaxis = FakeAxis()

    def pie(self, *args, **kwargs):
        self.pie_calls.append((args, kwargs))

    def bar(self, *args, **kwargs):
        self.bar_calls.append((args, kwargs))

    def plot(self, *args, **kwargs):
        self.plot_calls.append((args, kwargs))

    def set_title(self, *args, **kwargs):
        self.title = args[0] if args else None
        self.title_kwargs = kwargs

    def set_ylabel(self, *args, **kwargs):
        self.ylabel = args[0] if args else None
        self.ylabel_kwargs = kwargs

    def tick_params(self, *args, **kwargs):
        self.tick_params_calls.append((args, kwargs))

    def set_xticks(self, *args, **kwargs):
        pass

    def set_xticklabels(self, *args, **kwargs):
        pass

    def legend(self, *args, **kwargs):
        pass

    def set_facecolor(self, color):
        self.facecolor = color

    def grid(self, *args, **kwargs):
        self.grid_calls.append((args, kwargs))


class FakeFigure:
    def __init__(self):
        self.patch = FakeSpine()
        self.tight_layout_kwargs = None

    def tight_layout(self, *args, **kwargs):
        self.tight_layout_kwargs = kwargs


class FakeSummaryTree(FakeWidget):
    instances = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.columns = list(kwargs["columns"])
        self.headings = {}
        self.column_options = {}
        self.rows = []
        self.tag_options = {}
        self.configure_options = {}
        FakeSummaryTree.instances.append(self)

    def configure(self, **kwargs):
        self.configure_options.update(kwargs)

    def yview(self, *args):
        pass

    def xview(self, *args):
        pass

    def heading(self, column, **kwargs):
        self.headings[column] = kwargs

    def column(self, column, **kwargs):
        self.column_options[column] = kwargs

    def tag_configure(self, tag_name, **kwargs):
        self.tag_options[tag_name] = kwargs

    def insert(self, parent, index, values=None, tags=()):
        self.rows.append({"values": list(values or []), "tags": list(tags)})
        return f"summary-{len(self.rows)}"


class FakePurchaseTree(FakeWidget):
    instances = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.columns = list(kwargs["columns"])
        self.displaycolumns = list(kwargs.get("displaycolumns", []))
        self.show = kwargs.get("show")
        self.headings = {}
        self.column_options = {}
        self.configure_options = {}
        self.bound_events = {}
        FakePurchaseTree.instances.append(self)

    def heading(self, column, **kwargs):
        self.headings[column] = kwargs

    def column(self, column, **kwargs):
        self.column_options[column] = kwargs

    def configure(self, **kwargs):
        self.configure_options.update(kwargs)

    def yview(self, *args):
        pass

    def xview(self, *args):
        pass

    def bind(self, event, callback):
        self.bound_events[event] = callback


class PurchaseTaggerBrowseTest(unittest.TestCase):
    def test_default_window_size_is_about_thirteen_percent_larger(self):
        self.assertEqual(DEFAULT_WINDOW_WIDTH, 1020)
        self.assertEqual(DEFAULT_WINDOW_HEIGHT, 680)
        self.assertEqual(DEFAULT_WINDOW_GEOMETRY, "1020x680")

    def make_app(self, files=None):
        app = object.__new__(PurchaseTaggerUI)
        app.pdf_files = list(files or [])
        app.file_label_var = SimpleVar("No hay PDFs seleccionados")
        app.status_var = SimpleVar("")
        app.bank_var = SimpleVar("BAC")
        app.account_type_var = SimpleVar("Credito")
        app.load = Mock()
        return app

    def test_browse_pdf_loads_and_tags_selected_pdfs(self):
        app = self.make_app()

        with patch(
            "purchase_tagger_app.filedialog.askopenfilenames",
            return_value=(r"C:\tmp\a.pdf", r"C:\tmp\b.pdf"),
        ):
            app.browse_pdf()

        self.assertEqual(app.pdf_files, [r"C:\tmp\a.pdf", r"C:\tmp\b.pdf"])
        self.assertEqual(app.file_label_var.get(), "2 PDFs seleccionados")
        app.load.assert_called_once_with()

    def test_browse_pdf_cancel_keeps_current_selection_without_loading(self):
        app = self.make_app([r"C:\tmp\statement.pdf"])
        app.file_label_var.set("statement.pdf")

        with patch("purchase_tagger_app.filedialog.askopenfilenames", return_value=()):
            app.browse_pdf()

        self.assertEqual(app.pdf_files, [r"C:\tmp\statement.pdf"])
        self.assertEqual(app.file_label_var.get(), "statement.pdf")
        app.load.assert_not_called()

    def test_clear_pdfs_resets_imported_state_to_startup_defaults(self):
        app = object.__new__(PurchaseTaggerUI)
        rows = [
            ["01-ENE-25", "APPLE STORE", "10.00", "USD", "Shopping"],
            ["02-FEB-25", "BANANA MARKET", "20.00", "CRC", "Groceries"],
        ]
        app.pdf_files = ["jan.pdf", "feb.pdf"]
        app.all_rows = list(rows)
        app.filtered_rows = list(rows)
        app.tree_item_rows = {"old": rows[0]}
        app.tree = FakeTree(["old"])
        app.tree.items["old"] = rows[0]
        app.file_label_var = SimpleVar("2 PDFs seleccionados")
        app.status_var = SimpleVar("Se cargaron y etiquetaron 2 compras")
        app.search_var = SimpleVar("banana")
        app.currency_var = SimpleVar("CRC")
        app.import_currency_var = SimpleVar("USD")
        app.month_var = SimpleVar("2025-02")
        app.tag_filter_var = SimpleVar("Groceries")
        app.bank_var = SimpleVar("Promerica")
        app.account_type_var = SimpleVar("Credito")
        app.total_var = SimpleVar("Totales: CRC 20.00")
        app.visible_count_var = SimpleVar("Mostrando 2 compras")
        app.kpi_vars = {
            "total_rows": SimpleVar("2"),
            "visible_rows": SimpleVar("2"),
            "untagged_rows": SimpleVar("0"),
            "currency_count": SimpleVar("2"),
            "over_limit_tags": SimpleVar("0"),
        }
        app.currency_menu = FakeMenu()
        app.month_menu = FakeMenu()
        app.tag_menu = FakeMenu()
        app.account_type_menu = FakeMenu()
        app.tags = {"Groceries": {"keywords": [], "limit": 0}}
        app.natag = "N/A"
        app.active_view = "Purchases"

        app.clear_pdfs()

        self.assertEqual(app.pdf_files, [])
        self.assertEqual(app.all_rows, [])
        self.assertEqual(app.filtered_rows, [])
        self.assertEqual(app.tree_item_rows, {})
        self.assertEqual(app.tree.deleted, ["old"])
        self.assertEqual(app.file_label_var.get(), "No hay PDFs seleccionados")
        self.assertEqual(app.status_var.get(), "No hay PDFs seleccionados")
        self.assertEqual(app.search_var.get(), "")
        self.assertEqual(app.currency_var.get(), "Todas las monedas")
        self.assertEqual(app.import_currency_var.get(), "")
        self.assertEqual(app.month_var.get(), "Todos")
        self.assertEqual(app.tag_filter_var.get(), "Todos")
        self.assertEqual(app.bank_var.get(), "BAC")
        self.assertEqual(app.account_type_var.get(), "Credito")
        self.assertEqual(app.total_var.get(), "Totales: 0.00")
        self.assertEqual(app.visible_count_var.get(), "Mostrando 0 compras")
        self.assertEqual(app.kpi_vars["total_rows"].get(), "0")
        self.assertEqual(app.kpi_vars["visible_rows"].get(), "0")
        self.assertEqual(app.currency_menu.values, ["Todas las monedas"])
        self.assertEqual(app.month_menu.values, ["Todos"])
        self.assertEqual(app.tag_menu.values, ["Todos"])
        self.assertEqual(app.account_type_menu.values, ["Credito", "Debito"])

    def test_clear_pdfs_refreshes_visible_import_overview(self):
        app = object.__new__(PurchaseTaggerUI)
        app.pdf_files = ["statement.pdf"]
        app.all_rows = [["01-ENE-25", "CAFE", "-10.00", "USD", "Dining"]]
        app.filtered_rows = list(app.all_rows)
        app.tree_item_rows = {}
        app.file_label_var = SimpleVar("statement.pdf")
        app.status_var = SimpleVar("Se cargaron y etiquetaron 1 compras")
        app.search_var = SimpleVar("")
        app.currency_var = SimpleVar("Todas las monedas")
        app.import_currency_var = SimpleVar("USD")
        app.month_var = SimpleVar("Todos")
        app.tag_filter_var = SimpleVar("Todos")
        app.bank_var = SimpleVar("Promerica")
        app.account_type_var = SimpleVar("Credito")
        app.total_var = SimpleVar("Totales: USD 10.00")
        app.account_type_menu = FakeMenu()
        app.kpi_vars = {
            "total_rows": SimpleVar("1"),
            "visible_rows": SimpleVar("1"),
            "untagged_rows": SimpleVar("0"),
            "currency_count": SimpleVar("1"),
            "over_limit_tags": SimpleVar("0"),
        }
        app.tags = {}
        app.natag = "N/A"
        app.active_view = "Imports"
        app.apply_filter = Mock()
        app.show_view = Mock()

        app.clear_pdfs()

        app.show_view.assert_called_once_with("Imports")

    def test_file_panel_uses_browse_and_tag_button_label(self):
        app = self.make_app()
        app.browse_pdf = Mock()
        app.clear_pdfs = Mock()
        app._panel = lambda parent, **kwargs: FakeFrame()

        with patch("purchase_tagger_app.ctk.CTkFont", return_value="font"), \
                patch("purchase_tagger_app.ctk.CTkLabel", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkButton", side_effect=FakeWidget) as button, \
                patch("purchase_tagger_app.ctk.CTkOptionMenu", side_effect=FakeWidget):
            app._build_file_panel(FakeFrame(), row=0)

        button_texts = [call.kwargs["text"] for call in button.call_args_list]
        self.assertIn("Buscar y etiquetar", button_texts)
        self.assertNotIn("Buscar", button_texts)

    def test_file_panel_renders_bank_and_account_type_selectors(self):
        app = self.make_app()
        app.browse_pdf = Mock()
        app.clear_pdfs = Mock()
        app._panel = lambda parent, **kwargs: FakeFrame()

        with patch("purchase_tagger_app.ctk.CTkFont", return_value="font"), \
                patch("purchase_tagger_app.ctk.CTkLabel", side_effect=FakeWidget) as label, \
                patch("purchase_tagger_app.ctk.CTkButton", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkOptionMenu", side_effect=FakeWidget) as option_menu:
            app._build_file_panel(FakeFrame(), row=0)

        label_texts = [call.kwargs.get("text") for call in label.call_args_list]
        self.assertIn("Banco", label_texts)
        self.assertIn("Tipo", label_texts)
        self.assertEqual(option_menu.call_args_list[0].kwargs["values"], ["BAC", "Promerica"])
        self.assertIs(option_menu.call_args_list[0].kwargs["variable"], app.bank_var)
        self.assertEqual(option_menu.call_args_list[1].kwargs["values"], ["Credito", "Debito"])
        self.assertIs(option_menu.call_args_list[1].kwargs["variable"], app.account_type_var)

    def test_account_type_selector_refreshes_for_selected_bank(self):
        app = self.make_app()
        app.bank_var = SimpleVar("Promerica")
        app.account_type_var = SimpleVar("Debito")
        app.account_type_menu = FakeMenu()

        app._refresh_account_type_options()

        self.assertEqual(app.account_type_menu.values, ["Credito"])
        self.assertEqual(app.account_type_var.get(), "Credito")

    def test_imports_view_has_no_manual_load_and_tag_header_button(self):
        app = object.__new__(PurchaseTaggerUI)
        app.workspace = FakeFrame()
        app._build_page_header = Mock()
        app._build_file_panel = Mock()
        app._build_kpi_row = Mock()
        app._build_filter_toolbar = Mock()
        app._build_purchase_table = Mock()
        app._build_totals_footer = Mock()
        app._build_import_overview = Mock()
        app.apply_filter = Mock()

        with patch("purchase_tagger_app.ctk.CTkFrame", side_effect=FakeCtkFrame):
            app._build_imports_view()

        header_kwargs = app._build_page_header.call_args.kwargs
        self.assertNotIn("action_text", header_kwargs)
        self.assertNotIn("action_command", header_kwargs)
        app._build_import_overview.assert_called_once()
        app._build_filter_toolbar.assert_not_called()
        app._build_purchase_table.assert_not_called()
        app._build_totals_footer.assert_not_called()

    def test_import_overview_data_summarizes_single_currency_import(self):
        app = object.__new__(PurchaseTaggerUI)
        app.pdf_files = ["jan.pdf", "feb.pdf"]
        app.all_rows = [
            ["01-ENE-25", "CARD PAYMENT", "250.00", "USD", "Payments"],
            ["01-ENE-25", "CAFE", "-80.00", "USD", "Dining"],
            ["02-FEB-25", "MARKET", "-90.00", "USD", "Groceries"],
            ["03-FEB-25", "UNKNOWN", "-10.00", "USD", "N/A"],
        ]
        app.tags = {
            "Dining": {"limit": Decimal("50.00")},
            "Groceries": {"limit": Decimal("200.00")},
        }
        app.natag = "N/A"

        data = app._import_overview_data()

        self.assertEqual(data["file_count"], 2)
        self.assertEqual(data["purchase_count"], 3)
        self.assertEqual(data["currencies"], "USD")
        self.assertEqual(data["untagged_count"], 1)
        self.assertEqual(data["over_limit_count"], 1)
        self.assertEqual(data["month_range"], "2025-01 a 2025-02")
        self.assertEqual(data["top_tag"], "Groceries 90.00")
        self.assertEqual(data["largest_purchase"], "MARKET USD 90.00")
        self.assertEqual(data["headline"], "Dining supera su presupuesto por USD 30.00.")

    def test_import_overview_data_keeps_general_counts_for_multiple_currencies(self):
        app = object.__new__(PurchaseTaggerUI)
        app.pdf_files = ["mixed.pdf"]
        app.all_rows = [
            ["01-ENE-25", "CARD PAYMENT", "250.00", "USD", "Payments"],
            ["01-ENE-25", "CAFE", "-80.00", "USD", "Dining"],
            ["02-FEB-25", "MARKET", "-90.00", "CRC", "Groceries"],
        ]
        app.tags = {}
        app.natag = "N/A"
        app.import_currency_var = SimpleVar("USD")

        data = app._import_overview_data()

        self.assertEqual(data["file_count"], 1)
        self.assertEqual(data["purchase_count"], 2)
        self.assertEqual(data["currencies"], "CRC, USD")
        self.assertEqual(data["currency_options"], ["CRC", "USD"])
        self.assertEqual(data["selected_currency"], "USD")
        self.assertEqual(data["untagged_count"], 0)
        self.assertEqual(data["top_tag"], "Dining 80.00")
        self.assertEqual(data["largest_purchase"], "CAFE USD 80.00")
        self.assertEqual(data["headline"], "Dining concentra el gasto de este periodo.")

    def test_import_overview_data_falls_back_to_first_available_currency(self):
        app = object.__new__(PurchaseTaggerUI)
        app.pdf_files = ["mixed.pdf"]
        app.all_rows = [
            ["01-ENE-25", "CARD PAYMENT", "250.00", "USD", "Payments"],
            ["01-ENE-25", "CAFE", "-80.00", "USD", "Dining"],
            ["02-FEB-25", "MARKET", "-90.00", "CRC", "Groceries"],
        ]
        app.tags = {}
        app.natag = "N/A"
        app.import_currency_var = SimpleVar("EUR")

        data = app._import_overview_data()

        self.assertEqual(data["currency_options"], ["CRC", "USD"])
        self.assertEqual(data["selected_currency"], "CRC")
        self.assertEqual(app.import_currency_var.get(), "CRC")
        self.assertEqual(data["top_tag"], "Groceries 90.00")

    def test_import_overview_renders_general_information_labels(self):
        app = object.__new__(PurchaseTaggerUI)
        app._panel = lambda parent, **kwargs: FakeFrame()
        app._import_overview_data = Mock(return_value={
            "file_count": 2,
            "purchase_count": 3,
            "currencies": "USD",
            "untagged_count": 1,
            "over_limit_count": 1,
            "month_range": "2025-01 a 2025-02",
            "top_tag": "Groceries 90.00",
            "largest_purchase": "MARKET USD 90.00",
            "headline": "Dining supera su presupuesto por USD 30.00.",
            "detail": "- Groceries representa el 50.0% del gasto.",
            "currency_options": ["CRC", "USD"],
            "selected_currency": "USD",
        })
        app.import_currency_var = SimpleVar("USD")
        app.show_view = Mock()

        with patch("purchase_tagger_app.ctk.CTkFont", return_value="font"), \
                patch("purchase_tagger_app.ctk.CTkFrame", side_effect=FakeCtkFrame), \
                patch("purchase_tagger_app.ctk.CTkLabel", side_effect=FakeWidget) as label, \
                patch("purchase_tagger_app.ctk.CTkOptionMenu", side_effect=FakeWidget) as option_menu:
            app._build_import_overview(FakeFrame(), row=2)

        label_texts = [call.kwargs.get("text") for call in label.call_args_list]
        for expected in (
            "Resumen de importación",
            "Archivos",
            "Compras cargadas",
            "Monedas",
            "Rango de meses",
            "Sin etiqueta",
            "Sobre presupuesto",
            "Etiqueta principal",
            "Compra mayor",
            "Hallazgos",
        ):
            self.assertIn(expected, label_texts)
        option_menu.assert_called_once()
        self.assertEqual(option_menu.call_args.kwargs["values"], ["CRC", "USD"])
        self.assertIs(option_menu.call_args.kwargs["variable"], app.import_currency_var)

    def test_load_refreshes_imports_overview_after_processing_pdfs(self):
        app = object.__new__(PurchaseTaggerUI)
        app.pdf_files = ["statement.pdf"]
        app.all_rows = []
        app.status_var = SimpleVar("")
        app.bank_var = SimpleVar("BAC")
        app.account_type_var = SimpleVar("Debito")
        app.apply_filter = Mock()
        app.update_idletasks = Mock()
        app.active_view = "Imports"
        app.show_view = Mock()

        with patch("purchase_tagger_app.process_purchases", return_value=[
            ("01-ENE-25", "CAFE", Decimal("-80.00"), "USD", "Dining", Decimal("0")),
        ]) as process_purchases:
            app.load()

        process_purchases.assert_called_once_with("statement.pdf", bank="BAC", account_type="Debito")
        self.assertEqual(app.all_rows, [["01-ENE-25", "CAFE", "-80.00", "USD", "Dining", "-"]])
        app.show_view.assert_called_once_with("Imports")

    def test_load_displays_error_message_when_pdf_processing_fails(self):
        app = object.__new__(PurchaseTaggerUI)
        app.pdf_files = [r"C:\tmp\broken.pdf"]
        app.all_rows = []
        app.status_var = SimpleVar("")
        app.bank_var = SimpleVar("BAC")
        app.account_type_var = SimpleVar("Debito")
        app.apply_filter = Mock()
        app.update_idletasks = Mock()

        with patch("purchase_tagger_app.process_purchases", side_effect=RuntimeError("Cannot read PDF")), \
                patch("purchase_tagger_app.messagebox.showerror") as showerror:
            app.load()

        showerror.assert_called_once_with("Error", "broken.pdf: Cannot read PDF")
        app.apply_filter.assert_called_once_with()


class PurchaseTaggerDisplayRowTest(unittest.TestCase):
    def test_display_purchase_row_moves_negative_to_sign_column(self):
        row = ["01-ENE-25", "CARD PAYMENT", "-96,711.06", "CRC", "N/A", "-"]

        self.assertEqual(
            display_purchase_row(row),
            ["01-ENE-25", "CARD PAYMENT", "-", "96,711.06", "CRC", "N/A"],
        )


class PurchaseTaggerRowMappingTest(unittest.TestCase):
    def make_app(self, rows, visible_order):
        app = object.__new__(PurchaseTaggerUI)
        app.tree = FakeTree(visible_order)
        app.filtered_rows = rows
        app.tree_item_rows = {
            "item-a": rows[0],
            "item-b": rows[1],
        }
        app.natag = "N/A"
        return app

    def test_assign_tag_uses_mapped_row_after_tree_sort(self):
        rows = [
            ["01-ENE-25", "APPLE STORE", "10.00", "USD", "N/A"],
            ["02-ENE-25", "BANANA MARKET", "20.00", "USD", "N/A"],
        ]
        app = self.make_app(rows, ["item-b", "item-a"])
        app.tags = {"Groceries": {"keywords": [], "limit": 0}}

        with patch("purchase_tagger_app.save_tags"):
            app.assign_tag("item-b", "Groceries")

        self.assertEqual(rows[0][4], "N/A")
        self.assertEqual(rows[1][4], "Groceries")
        self.assertEqual(app.tree.items["item-b"], ["02-ENE-25", "BANANA MARKET", "+", "20.00", "USD", "Groceries"])

    def test_assign_tag_adds_keyword_for_mapped_na_row(self):
        rows = [
            ["01-ENE-25", "APPLE STORE", "10.00", "USD", "Dining"],
            ["02-ENE-25", "BANANA MARKET", "20.00", "USD", "N/A"],
        ]
        app = self.make_app(rows, ["item-b", "item-a"])
        app.tags = {"Groceries": {"keywords": [], "limit": 0}}

        with patch("purchase_tagger_app.save_tags") as save_tags:
            app.assign_tag("item-b", "Groceries")

        self.assertEqual(app.tags["Groceries"]["keywords"], ["BANANA MARKET"])
        save_tags.assert_called_once_with(app.tags)

    def test_create_and_assign_uses_mapped_row_description_after_tree_sort(self):
        rows = [
            ["01-ENE-25", "APPLE STORE", "10.00", "USD", "N/A"],
            ["02-ENE-25", "BANANA MARKET", "20.00", "USD", "N/A"],
        ]
        app = self.make_app(rows, ["item-b", "item-a"])
        app.tags = {}

        with patch("purchase_tagger_app.simple_input", return_value="Groceries"), \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.create_and_assign("item-b")

        self.assertEqual(app.tags["Groceries"]["keywords"], ["BANANA MARKET"])
        self.assertEqual(rows[0][4], "N/A")
        self.assertEqual(rows[1][4], "Groceries")
        self.assertEqual(app.tree.items["item-b"], ["02-ENE-25", "BANANA MARKET", "+", "20.00", "USD", "Groceries"])
        save_tags.assert_called_once_with(app.tags)

    def test_row_mapping_helper_returns_original_row(self):
        rows = [
            ["01-ENE-25", "APPLE STORE", "10.00", "USD", "N/A"],
            ["02-ENE-25", "BANANA MARKET", "20.00", "USD", "N/A"],
        ]
        app = self.make_app(rows, ["item-b", "item-a"])

        assert app._row_for_item("item-b") is rows[1]

    def test_apply_filter_ignores_destroyed_tree_reference(self):
        rows = [
            ["01-ENE-25", "APPLE STORE", "10.00", "USD", "N/A"],
        ]
        app = object.__new__(PurchaseTaggerUI)
        app.all_rows = rows
        app.filtered_rows = []
        app.tree_item_rows = {"stale": rows[0]}
        app.tree = DeadTree()
        app.search_var = SimpleVar("")
        app.currency_var = SimpleVar("Todas las monedas")
        app.month_var = SimpleVar("Todos")
        app.tag_filter_var = SimpleVar("Todos")
        app.total_var = SimpleVar("")
        app.kpi_vars = {
            "total_rows": SimpleVar("0"),
            "visible_rows": SimpleVar("0"),
            "untagged_rows": SimpleVar("0"),
            "currency_count": SimpleVar("0"),
            "over_limit_tags": SimpleVar("0"),
        }
        app.tags = {}
        app.natag = "N/A"

        app.apply_filter()

        self.assertEqual(app.filtered_rows, rows)
        self.assertEqual(app.tree_item_rows, {})
        self.assertEqual(app.total_var.get(), "Totales: USD 10.00")

    def test_apply_filter_refreshes_live_tree_totals_kpis_and_filter_options(self):
        rows = [
            ["01-ENE-25", "APPLE STORE", "10.00", "USD", "Shopping"],
            ["02-FEB-25", "BANANA MARKET", "20.00", "CRC", "Groceries"],
        ]
        app = object.__new__(PurchaseTaggerUI)
        app.all_rows = rows
        app.filtered_rows = []
        app.tree_item_rows = {"old": rows[0]}
        app.tree = FakeTree(["old"])
        app.tree.items["old"] = rows[0]
        app.search_var = SimpleVar("banana")
        app.currency_var = SimpleVar("CRC")
        app.month_var = SimpleVar("2025-02")
        app.tag_filter_var = SimpleVar("Groceries")
        app.total_var = SimpleVar("")
        app.visible_count_var = SimpleVar("")
        app.kpi_vars = {
            "total_rows": SimpleVar("0"),
            "visible_rows": SimpleVar("0"),
            "untagged_rows": SimpleVar("0"),
            "currency_count": SimpleVar("0"),
            "over_limit_tags": SimpleVar("0"),
        }
        app.currency_menu = FakeMenu()
        app.month_menu = FakeMenu()
        app.tag_menu = FakeMenu()
        app.tags = {}
        app.natag = "N/A"

        app.apply_filter()

        self.assertEqual(app.filtered_rows, [rows[1]])
        self.assertEqual(app.tree.deleted, ["old"])
        self.assertEqual(list(app.tree_item_rows.values()), [rows[1]])
        self.assertEqual(app.total_var.get(), "Totales: CRC 20.00")
        self.assertEqual(app.visible_count_var.get(), "Mostrando 1 compras")
        self.assertEqual(app.tree.items["item-1"], ["02-FEB-25", "BANANA MARKET", "+", "20.00", "CRC", "Groceries"])
        self.assertEqual(app.tree.items["item-1"][5], "Groceries")
        self.assertEqual(app.kpi_vars["total_rows"].get(), "2")
        self.assertEqual(app.kpi_vars["visible_rows"].get(), "1")
        self.assertEqual(app.currency_menu.values, ["Todas las monedas", "CRC", "USD"])
        self.assertEqual(app.month_menu.values, ["Todos", "2025-01", "2025-02"])
        self.assertEqual(app.tag_menu.values, ["Todos", "Groceries", "Shopping"])

    def test_purchase_table_declares_visible_tag_column_order(self):
        app = object.__new__(PurchaseTaggerUI)
        app._panel = lambda parent, **kwargs: FakeFrame()
        app._style_treeview = lambda: None
        app.on_right_click = lambda event: None
        FakePurchaseTree.instances = []

        with patch("purchase_tagger_app.ttk.Treeview", side_effect=FakePurchaseTree), \
                patch("purchase_tagger_app.ttk.Scrollbar", side_effect=FakeWidget):
            app._build_purchase_table(FakeFrame(), row=0)

        tree = FakePurchaseTree.instances[0]
        expected_columns = ["date", "description", "sign", "amount", "currency", "tag"]
        self.assertEqual(tree.columns, expected_columns)
        self.assertEqual(tree.displaycolumns, expected_columns)
        self.assertEqual(tree.show, "headings")
        self.assertEqual(tree.headings["sign"]["text"], "Signo")
        self.assertEqual(tree.column_options["sign"]["anchor"], "center")
        self.assertEqual(tree.headings["tag"]["text"], "Etiqueta")
        self.assertGreaterEqual(tree.column_options["tag"]["width"], 100)
        self.assertEqual(tree.column_options["tag"]["anchor"], "w")
        self.assertIn("xscrollcommand", tree.configure_options)

    def test_apply_filter_resets_stale_filters_before_computing_rows(self):
        rows = [
            ["01-ENE-25", "APPLE STORE", "10.00", "USD", "Shopping"],
            ["02-FEB-25", "BANANA MARKET", "20.00", "CRC", "Groceries"],
        ]
        app = object.__new__(PurchaseTaggerUI)
        app.all_rows = rows
        app.filtered_rows = []
        app.tree_item_rows = {}
        app.search_var = SimpleVar("")
        app.currency_var = SimpleVar("EUR")
        app.month_var = SimpleVar("2024-12")
        app.tag_filter_var = SimpleVar("Travel")
        app.total_var = SimpleVar("")
        app.visible_count_var = SimpleVar("")
        app.kpi_vars = {
            "total_rows": SimpleVar("0"),
            "visible_rows": SimpleVar("0"),
            "untagged_rows": SimpleVar("0"),
            "currency_count": SimpleVar("0"),
            "over_limit_tags": SimpleVar("0"),
        }
        app.currency_menu = FakeMenu()
        app.month_menu = FakeMenu()
        app.tag_menu = FakeMenu()
        app.tags = {}
        app.natag = "N/A"

        app.apply_filter()

        self.assertEqual(app.currency_var.get(), "Todas las monedas")
        self.assertEqual(app.month_var.get(), "Todos")
        self.assertEqual(app.tag_filter_var.get(), "Todos")
        self.assertEqual(app.filtered_rows, rows)
        self.assertEqual(app.total_var.get(), "Totales: CRC 20.00; USD 10.00")
        self.assertEqual(app.visible_count_var.get(), "Mostrando 2 compras")

    def test_assign_tag_reapplies_active_tag_filter(self):
        rows = [
            ["01-ENE-25", "APPLE STORE", "10.00", "USD", "N/A"],
            ["02-ENE-25", "BANANA MARKET", "20.00", "USD", "N/A"],
        ]
        app = object.__new__(PurchaseTaggerUI)
        app.all_rows = rows
        app.filtered_rows = list(rows)
        app.tree_item_rows = {
            "item-a": rows[0],
            "item-b": rows[1],
        }
        app.tree = FakeTree(["item-a", "item-b"])
        app.tree.items["item-a"] = rows[0]
        app.tree.items["item-b"] = rows[1]
        app.search_var = SimpleVar("")
        app.currency_var = SimpleVar("Todas las monedas")
        app.month_var = SimpleVar("Todos")
        app.tag_filter_var = SimpleVar("N/A")
        app.total_var = SimpleVar("")
        app.visible_count_var = SimpleVar("")
        app.kpi_vars = {
            "total_rows": SimpleVar("0"),
            "visible_rows": SimpleVar("0"),
            "untagged_rows": SimpleVar("0"),
            "currency_count": SimpleVar("0"),
            "over_limit_tags": SimpleVar("0"),
        }
        app.currency_menu = FakeMenu()
        app.month_menu = FakeMenu()
        app.tag_menu = FakeMenu()
        app.tags = {"Groceries": {"keywords": [], "limit": 0}}
        app.natag = "N/A"

        with patch("purchase_tagger_app.save_tags"):
            app.assign_tag("item-a", "Groceries")

        self.assertEqual(app.filtered_rows, [rows[1]])
        self.assertEqual(list(app.tree_item_rows.values()), [rows[1]])
        self.assertEqual(app.visible_count_var.get(), "Mostrando 1 compras")
        self.assertEqual(app.total_var.get(), "Totales: USD 20.00")
        self.assertEqual(app.kpi_vars["untagged_rows"].get(), "1")

    def test_clear_workspace_widget_refs_preserves_app_state_vars(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tree = object()
        app.currency_menu = object()
        app.summary_frame = object()
        app.tag_listbox = object()
        app.limit_var = object()
        app.month_var = SimpleVar("Todos")
        app.search_var = SimpleVar("apple")
        app.tag_filter_var = SimpleVar("N/A")
        app.file_label_var = SimpleVar("No hay PDFs seleccionados")
        app.total_var = SimpleVar("Totales: 0.00")
        app.kpi_vars = {"total_rows": SimpleVar("0")}

        app._clear_workspace_widget_refs()

        for name in ("tree", "currency_menu", "summary_frame", "tag_listbox", "limit_var"):
            self.assertNotIn(name, app.__dict__)
        self.assertEqual(app.month_var.get(), "Todos")
        self.assertEqual(app.search_var.get(), "apple")
        self.assertEqual(app.tag_filter_var.get(), "N/A")
        self.assertEqual(app.file_label_var.get(), "No hay PDFs seleccionados")
        self.assertEqual(app.total_var.get(), "Totales: 0.00")
        self.assertIn("total_rows", app.kpi_vars)

    def test_open_summary_routes_to_workspace_summary_view(self):
        app = object.__new__(PurchaseTaggerUI)
        calls = []
        app.show_view = calls.append

        app.open_summary()

        self.assertEqual(calls, ["Summaries"])

    def test_open_tag_editor_routes_to_tags_workspace(self):
        app = object.__new__(PurchaseTaggerUI)
        calls = []
        app.show_view = calls.append

        app.open_tag_editor()

        self.assertEqual(calls, ["Tags"])

    def test_tag_workspace_methods_are_extracted_to_tags_view_module(self):
        self.assertIs(PurchaseTaggerUI._build_tags_view, tags_view._build_tags_view)
        self.assertIs(PurchaseTaggerUI.add_tag, tags_view.add_tag)
        self.assertIs(PurchaseTaggerUI.save_tags_from_view, tags_view.save_tags_from_view)
        self.assertIs(PurchaseTaggerUI.import_tags_json, tags_view.import_tags_json)
        self.assertIs(PurchaseTaggerUI.export_tags_json, tags_view.export_tags_json)
        self.assertIs(PurchaseTaggerUI.add_parent_category, tags_view.add_parent_category)
        self.assertIs(PurchaseTaggerUI.on_parent_category_selected, tags_view.on_parent_category_selected)
        self.assertIs(PurchaseTaggerUI.on_tags_tab_changed, tags_view.on_tags_tab_changed)
        self.assertIs(PurchaseTaggerUI.rename_parent_category, tags_view.rename_parent_category)
        self.assertIs(PurchaseTaggerUI.remove_parent_category, tags_view.remove_parent_category)

    def test_tags_view_renders_json_import_and_export_buttons(self):
        app = object.__new__(PurchaseTaggerUI)
        app.workspace = FakeFrame()
        app.tags = {}
        app._build_page_header = Mock()
        panels = []

        def make_panel(parent, **kwargs):
            panel = FakeCtkFrame(parent)
            panels.append(panel)
            return panel

        app._panel = make_panel
        app.refresh_tag_lists = Mock()
        FakeCtkFrame.instances = []
        FakeCtkTabview.instances = []

        with patch("purchase_tagger_app.ctk.CTkFont", return_value="font"), \
                patch("purchase_tagger_app.ctk.CTkLabel", side_effect=FakeWidget), \
                patch("purchase_tagger_app.tk.Listbox", side_effect=lambda *args, **kwargs: FakeListbox()) as listbox, \
                patch("purchase_tagger_app.tk.StringVar", side_effect=SimpleVar), \
                patch("purchase_tagger_app.ctk.CTkFrame", side_effect=FakeCtkFrame), \
                patch("purchase_tagger_app.ctk.CTkTabview", side_effect=FakeCtkTabview), \
                patch("purchase_tagger_app.ctk.CTkEntry", side_effect=FakeWidget) as entry, \
                patch("purchase_tagger_app.ctk.CTkOptionMenu", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkComboBox", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkButton", side_effect=FakeWidget) as button:
            app._build_tags_view()

        self.assertTrue(FakeCtkTabview.instances)
        tab_names = FakeCtkTabview.instances[0].tab_names
        self.assertEqual(tab_names, ["Etiquetas", "Categorías"])
        button_texts = [call.kwargs["text"] for call in button.call_args_list]
        self.assertIn("Importar JSON", button_texts)
        self.assertIn("Exportar JSON", button_texts)
        category_button_texts = [
            call.kwargs["text"]
            for call in button.call_args_list
            if fake_widget_descends_from(call.args[0], app.category_actions_section)
        ]
        self.assertEqual(category_button_texts, ["Agregar nuevo", "Editar", "Eliminar"])
        category_entry_calls = [
            call
            for call in entry.call_args_list
            if fake_widget_descends_from(call.args[0], app.category_actions_section)
        ]
        self.assertEqual(len(category_entry_calls), 1)
        self.assertIs(category_entry_calls[0].kwargs["textvariable"], app.selected_category_var)
        content = FakeCtkFrame.instances[0]
        self.assertEqual(content.grid_columns[0], {"weight": 0, "minsize": 330})
        self.assertEqual(content.grid_columns[1], {"weight": 1})
        tag_listbox_call, category_listbox_call = listbox.call_args_list[:2]
        self.assertEqual(tag_listbox_call.kwargs["width"], category_listbox_call.kwargs["width"])
        self.assertEqual(tag_listbox_call.kwargs["height"], category_listbox_call.kwargs["height"])
        self.assertEqual(app.tag_management_label.grid_options, app.category_management_label.grid_options)
        self.assertEqual(app.tag_actions_frame.grid_options, app.category_actions_section.grid_options)
        right_panel = panels[1]
        right_side_actions = {"Agregar nuevo", "Editar", "Eliminar"}
        for call in button.call_args_list:
            if call.kwargs["text"] in right_side_actions:
                self.assertTrue(fake_widget_descends_from(call.args[0], right_panel), call.kwargs["text"])

    def test_tags_view_switches_right_panel_sections_by_active_tab(self):
        app = object.__new__(PurchaseTaggerUI)
        app.workspace = FakeFrame()
        app.tags = {"Dining": {"keywords": [], "parent_category": "Comida"}}
        app._build_page_header = Mock()
        app._panel = lambda parent, **kwargs: FakeCtkFrame(parent)
        FakeCtkTabview.instances = []

        with patch("purchase_tagger_app.ctk.CTkFont", return_value="font"), \
                patch("purchase_tagger_app.ctk.CTkLabel", side_effect=FakeWidget), \
                patch("purchase_tagger_app.tk.Listbox", side_effect=lambda *args, **kwargs: FakeListbox()), \
                patch("purchase_tagger_app.tk.StringVar", side_effect=SimpleVar), \
                patch("purchase_tagger_app.ctk.CTkFrame", side_effect=FakeCtkFrame), \
                patch("purchase_tagger_app.ctk.CTkTabview", side_effect=FakeCtkTabview), \
                patch("purchase_tagger_app.ctk.CTkEntry", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkOptionMenu", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkComboBox", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkButton", side_effect=FakeWidget):
            app._build_tags_view()

        self.assertEqual(app.tag_detail_title.kwargs["text"], "Etiqueta seleccionada")
        self.assertTrue(app.tag_actions_frame.visible)
        self.assertTrue(app.tag_form.visible)
        self.assertTrue(app.keyword_listbox.visible)
        self.assertTrue(app.keyword_buttons_frame.visible)
        self.assertFalse(app.category_actions_section.visible)
        self.assertEqual(app.tag_name_entry.state, "disabled")

        app.tags_tabview.set("Categorías")

        self.assertEqual(app.tag_detail_title.kwargs["text"], "Categoría seleccionada")
        self.assertFalse(app.tag_actions_frame.visible)
        self.assertFalse(app.tag_form.visible)
        self.assertFalse(app.keyword_listbox.visible)
        self.assertFalse(app.keyword_buttons_frame.visible)
        self.assertTrue(app.category_actions_section.visible)
        self.assertEqual(app.selected_category_var.get(), "Selecciona una categoría")
        self.assertEqual(app.selected_category_label.state, "disabled")

        app.parent_category_listbox.items = ["Comida"]
        app.parent_category_listbox.selection_set(0)
        app.on_parent_category_selected()

        self.assertEqual(app.selected_category_var.get(), "Comida")
        self.assertEqual(app.selected_category_label.state, "normal")
        self.assertEqual(app.tag_detail_title.kwargs["text"], "Categoría seleccionada")

    def test_edit_tag_renames_selected_tag_from_inline_name_input(self):
        app = object.__new__(PurchaseTaggerUI)
        app.workspace = FakeFrame()
        app.tags = {"Dining": {"keywords": ["cafe"], "limit": 75, "parent_category": "Comida"}}
        app.status_var = SimpleVar("")
        app._build_page_header = Mock()
        app._panel = lambda parent, **kwargs: FakeCtkFrame(parent)
        FakeCtkTabview.instances = []

        with patch("purchase_tagger_app.ctk.CTkFont", return_value="font"), \
                patch("purchase_tagger_app.ctk.CTkLabel", side_effect=FakeWidget), \
                patch("purchase_tagger_app.tk.Listbox", side_effect=lambda *args, **kwargs: FakeListbox()), \
                patch("purchase_tagger_app.tk.StringVar", side_effect=SimpleVar), \
                patch("purchase_tagger_app.ctk.CTkFrame", side_effect=FakeCtkFrame), \
                patch("purchase_tagger_app.ctk.CTkTabview", side_effect=FakeCtkTabview), \
                patch("purchase_tagger_app.ctk.CTkEntry", side_effect=FakeWidget) as entry, \
                patch("purchase_tagger_app.ctk.CTkOptionMenu", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkComboBox", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkButton", side_effect=FakeWidget):
            app._build_tags_view()

        self.assertIn("tag_name_var", app.__dict__)
        tag_name_entries = [
            call
            for call in entry.call_args_list
            if call.kwargs.get("textvariable") is app.tag_name_var
        ]
        self.assertEqual(len(tag_name_entries), 1)

        app.tag_listbox.selection_set(0)
        self.assertTrue(app.load_tag_details())
        self.assertEqual(app.tag_name_var.get(), "Dining")
        self.assertEqual(app.tag_name_entry.state, "normal")

        app.tag_name_var.set("Food")
        with patch("purchase_tagger_app.simple_input") as simple_input, \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.edit_tag()

        self.assertNotIn("Dining", app.tags)
        self.assertEqual(app.tags["Food"]["keywords"], ["cafe"])
        simple_input.assert_not_called()
        save_tags.assert_called_once_with(app.tags)

    def test_rename_parent_category_uses_inline_category_input(self):
        app = object.__new__(PurchaseTaggerUI)
        app.workspace = FakeFrame()
        app.tags = {
            "Dining": {"keywords": [], "limit": 75, "parent_category": "Comida"},
            "Groceries": {"keywords": [], "limit": 50, "parent_category": "Comida"},
            "Bus": {"keywords": [], "limit": 10, "parent_category": "Transporte"},
        }
        app.status_var = SimpleVar("")
        app._build_page_header = Mock()
        app._panel = lambda parent, **kwargs: FakeCtkFrame(parent)
        app._refresh_tag_filter_options = Mock()
        FakeCtkTabview.instances = []

        with patch("purchase_tagger_app.ctk.CTkFont", return_value="font"), \
                patch("purchase_tagger_app.ctk.CTkLabel", side_effect=FakeWidget), \
                patch("purchase_tagger_app.tk.Listbox", side_effect=lambda *args, **kwargs: FakeListbox()), \
                patch("purchase_tagger_app.tk.StringVar", side_effect=SimpleVar), \
                patch("purchase_tagger_app.ctk.CTkFrame", side_effect=FakeCtkFrame), \
                patch("purchase_tagger_app.ctk.CTkTabview", side_effect=FakeCtkTabview), \
                patch("purchase_tagger_app.ctk.CTkEntry", side_effect=FakeWidget) as entry, \
                patch("purchase_tagger_app.ctk.CTkOptionMenu", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkComboBox", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkButton", side_effect=FakeWidget):
            app._build_tags_view()

        category_name_entries = [
            call
            for call in entry.call_args_list
            if fake_widget_descends_from(call.args[0], app.category_actions_section)
            and call.kwargs.get("textvariable") is app.selected_category_var
        ]
        self.assertEqual(len(category_name_entries), 1)

        app.tags_tabview.set("Categorías")
        app.parent_category_listbox.items = ["Comida", "Sin clasificar", "Transporte"]
        app.parent_category_listbox.selection_set(0)
        app.on_parent_category_selected()
        self.assertEqual(app.selected_category_var.get(), "Comida")

        app.selected_category_var.set("Alimentación")
        with patch("purchase_tagger_app.simple_input") as simple_input, \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.rename_parent_category()

        self.assertEqual(app.tags["Dining"]["parent_category"], "Alimentación")
        self.assertEqual(app.tags["Groceries"]["parent_category"], "Alimentación")
        self.assertEqual(app.tags["Bus"]["parent_category"], "Transporte")
        simple_input.assert_not_called()
        save_tags.assert_called_once_with(app.tags)

    def test_tags_view_uses_editable_category_dropdowns_from_existing_tags(self):
        app = object.__new__(PurchaseTaggerUI)
        app.workspace = FakeFrame()
        app.tags = {
            "Dining": {
                "keywords": [],
                "parent_category": "Alimentación",
            },
            "Groceries": {
                "keywords": [],
                "parent_category": "Alimentación",
            },
            "Car": {
                "keywords": [],
                "parent_category": "Transporte",
            },
        }
        app._build_page_header = Mock()
        app._panel = lambda parent, **kwargs: FakeFrame()
        FakeCtkTabview.instances = []

        with patch("purchase_tagger_app.ctk.CTkFont", return_value="font"), \
                patch("purchase_tagger_app.ctk.CTkLabel", side_effect=FakeWidget), \
                patch("purchase_tagger_app.tk.Listbox", side_effect=lambda *args, **kwargs: FakeListbox()), \
                patch("purchase_tagger_app.tk.StringVar", side_effect=SimpleVar), \
                patch("purchase_tagger_app.ctk.CTkFrame", side_effect=FakeCtkFrame), \
                patch("purchase_tagger_app.ctk.CTkTabview", side_effect=FakeCtkTabview), \
                patch("purchase_tagger_app.ctk.CTkEntry", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkOptionMenu", side_effect=FakeWidget), \
                patch("purchase_tagger_app.ctk.CTkComboBox", side_effect=FakeWidget) as combo_box, \
                patch("purchase_tagger_app.ctk.CTkButton", side_effect=FakeWidget):
            app._build_tags_view()

        combo_values = [call.kwargs["values"] for call in combo_box.call_args_list]
        self.assertIn(["Alimentación", "Transporte"], combo_values)

    def test_saving_new_category_values_refreshes_reusable_dropdowns(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": [], "limit": 75}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.limit_var = SimpleVar("100")
        app.parent_category_var = SimpleVar("Educación")
        app.parent_category_menu = FakeMenu()

        result = app.save_current_tag_limit()

        self.assertTrue(result)
        self.assertEqual(app.tags["Dining"]["parent_category"], "Educación")
        self.assertNotIn("subcategory", app.tags["Dining"])
        self.assertEqual(app.parent_category_menu.values, ["Educación"])

    def test_saving_parent_category_equal_to_tag_is_rejected(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": [], "limit": 75, "parent_category": "Alimentación"}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.limit_var = SimpleVar("100")
        app.parent_category_var = SimpleVar("Dining")
        app.parent_category_menu = FakeMenu()

        with patch("purchase_tagger_app.messagebox.showwarning") as warning:
            result = app.save_current_tag_limit()

        self.assertFalse(result)
        self.assertEqual(app.tags["Dining"]["parent_category"], "Alimentación")
        self.assertEqual(app.tags["Dining"]["limit"], 75)
        warning.assert_called_once()

    def test_parent_category_options_deduplicates_sorts_and_includes_default(self):
        tags = {
            "Dining": {"parent_category": "Alimentación"},
            "Groceries": {"parent_category": "Alimentación"},
            "Travel": {"parent_category": "Transporte"},
            "Other": {"parent_category": ""},
        }

        self.assertEqual(
            tags_view._parent_category_options(tags),
            ["Alimentación", "Sin clasificar", "Transporte"],
        )

    def test_add_parent_category_assigns_new_category_to_selected_tag(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": [], "limit": 75, "parent_category": "Alimentación"}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.parent_category_listbox = FakeListbox()
        app.parent_category_menu = FakeMenu()
        app.parent_category_var = SimpleVar("Alimentación")
        app.selected_category_var = SimpleVar("Selecciona una categoría")
        app.selected_category_label = FakeWidget(textvariable=app.selected_category_var, state="disabled")
        app.limit_var = SimpleVar("75")
        app.status_var = SimpleVar("")
        app._refresh_tag_filter_options = Mock()

        with patch("purchase_tagger_app.simple_input", return_value="Educación"), \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.add_parent_category()

        self.assertEqual(app.tags["Dining"]["parent_category"], "Educación")
        self.assertEqual(app.parent_category_var.get(), "Educación")
        self.assertEqual(app.parent_category_listbox.items, ["Educación", "Sin clasificar"])
        self.assertEqual(app.parent_category_listbox.curselection(), (0,))
        self.assertEqual(app.selected_category_var.get(), "Educación")
        self.assertEqual(app.selected_category_label.state, "normal")
        self.assertEqual(app.parent_category_menu.values, ["Educación"])
        save_tags.assert_called_once_with(app.tags)
        app._refresh_tag_filter_options.assert_called_once()
        self.assertEqual(app.status_var.get(), 'Se agregó la categoría "Educación"')

    def test_rename_parent_category_updates_all_associated_tags(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {
            "Dining": {"keywords": [], "limit": 75, "parent_category": "Comida"},
            "Groceries": {"keywords": [], "limit": 50, "parent_category": "Comida"},
            "Bus": {"keywords": [], "limit": 10, "parent_category": "Transporte"},
        }
        app.parent_category_listbox = FakeListbox()
        app.parent_category_listbox.items = ["Comida", "Sin clasificar", "Transporte"]
        app.parent_category_listbox.selection_set(0)
        app.parent_category_menu = FakeMenu()
        app.parent_category_var = SimpleVar("Comida")
        app.limit_var = SimpleVar("0")
        app.status_var = SimpleVar("")
        app._refresh_tag_filter_options = Mock()

        with patch("purchase_tagger_app.simple_input", return_value="Alimentación"), \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.rename_parent_category()

        self.assertEqual(app.tags["Dining"]["parent_category"], "Alimentación")
        self.assertEqual(app.tags["Groceries"]["parent_category"], "Alimentación")
        self.assertEqual(app.tags["Bus"]["parent_category"], "Transporte")
        self.assertEqual(app.parent_category_listbox.items, ["Alimentación", "Sin clasificar", "Transporte"])
        save_tags.assert_called_once_with(app.tags)
        app._refresh_tag_filter_options.assert_called_once()
        self.assertEqual(app.status_var.get(), 'Se renombró la categoría "Comida" a "Alimentación"')

    def test_rename_parent_category_rejects_default_and_duplicates(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {
            "Dining": {"keywords": [], "limit": 75, "parent_category": "Sin clasificar"},
            "Bus": {"keywords": [], "limit": 10, "parent_category": "Transporte"},
        }
        app.parent_category_listbox = FakeListbox()
        app.parent_category_listbox.items = ["Sin clasificar", "Transporte"]
        app.parent_category_listbox.selection_set(0)
        app.limit_var = SimpleVar("0")

        with patch("purchase_tagger_app.simple_input") as simple_input, \
                patch("purchase_tagger_app.messagebox.showwarning") as warning, \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.rename_parent_category()

        simple_input.assert_not_called()
        warning.assert_called_once()
        save_tags.assert_not_called()

        app.parent_category_listbox.selection_set(1)
        with patch("purchase_tagger_app.simple_input", return_value="Sin clasificar"), \
                patch("purchase_tagger_app.messagebox.showwarning") as warning, \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.rename_parent_category()

        warning.assert_called_once()
        save_tags.assert_not_called()

    def test_remove_parent_category_blocks_default(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": [], "limit": 75, "parent_category": "Sin clasificar"}}
        app.parent_category_listbox = FakeListbox()
        app.parent_category_listbox.items = ["Sin clasificar"]
        app.parent_category_listbox.selection_set(0)
        app.limit_var = SimpleVar("0")

        with patch("purchase_tagger_app.messagebox.showwarning") as warning, \
                patch("purchase_tagger_app.messagebox.askyesno") as askyesno, \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.remove_parent_category()

        warning.assert_called_once()
        askyesno.assert_not_called()
        save_tags.assert_not_called()

    def test_remove_parent_category_in_use_confirms_and_cancel_preserves_tags(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {
            "Dining": {"keywords": [], "limit": 75, "parent_category": "Comida"},
            "Groceries": {"keywords": [], "limit": 50, "parent_category": "Comida"},
        }
        app.parent_category_listbox = FakeListbox()
        app.parent_category_listbox.items = ["Comida", "Sin clasificar"]
        app.parent_category_listbox.selection_set(0)
        app.limit_var = SimpleVar("0")

        with patch("purchase_tagger_app.messagebox.askyesno", return_value=False) as askyesno, \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.remove_parent_category()

        askyesno.assert_called_once_with(
            "Confirmar",
            'La categoría "Comida" está en uso por 2 etiquetas. '
            "Si continúas, quedarán en Sin clasificar. ¿Deseas continuar?",
        )
        self.assertEqual(app.tags["Dining"]["parent_category"], "Comida")
        self.assertEqual(app.tags["Groceries"]["parent_category"], "Comida")
        save_tags.assert_not_called()

    def test_remove_parent_category_in_use_reassigns_tags_to_unclassified(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {
            "Dining": {"keywords": [], "limit": 75, "parent_category": "Comida"},
            "Groceries": {"keywords": [], "limit": 50, "parent_category": "Comida"},
            "Bus": {"keywords": [], "limit": 10, "parent_category": "Transporte"},
        }
        app.parent_category_listbox = FakeListbox()
        app.parent_category_listbox.items = ["Comida", "Sin clasificar", "Transporte"]
        app.parent_category_listbox.selection_set(0)
        app.parent_category_menu = FakeMenu()
        app.parent_category_var = SimpleVar("Comida")
        app.limit_var = SimpleVar("0")
        app.status_var = SimpleVar("")
        app._refresh_tag_filter_options = Mock()

        with patch("purchase_tagger_app.messagebox.askyesno", return_value=True) as askyesno, \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.remove_parent_category()

        askyesno.assert_called_once()
        self.assertEqual(app.tags["Dining"]["parent_category"], "Sin clasificar")
        self.assertEqual(app.tags["Groceries"]["parent_category"], "Sin clasificar")
        self.assertEqual(app.tags["Bus"]["parent_category"], "Transporte")
        self.assertEqual(app.parent_category_var.get(), "Sin clasificar")
        self.assertEqual(app.parent_category_listbox.items, ["Sin clasificar", "Transporte"])
        save_tags.assert_called_once_with(app.tags)
        app._refresh_tag_filter_options.assert_called_once()
        self.assertEqual(app.status_var.get(), 'Se eliminó la categoría "Comida"')

    def test_parent_category_actions_stop_when_current_tag_limit_is_invalid(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": [], "limit": 75, "parent_category": "Comida"}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.parent_category_listbox = FakeListbox()
        app.parent_category_listbox.items = ["Comida", "Sin clasificar"]
        app.parent_category_listbox.selection_set(0)
        app.limit_var = SimpleVar("bad limit")

        with patch("purchase_tagger_app.simple_input") as simple_input, \
                patch("purchase_tagger_app.messagebox.showwarning") as warning, \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.add_parent_category()
            app.rename_parent_category()
            app.remove_parent_category()

        simple_input.assert_not_called()
        self.assertEqual(warning.call_count, 3)
        save_tags.assert_not_called()

    def test_refresh_tag_lists_sorts_tags_and_clears_details(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {
            "Travel": {"keywords": ["uber"], "limit": 100},
            "Dining": {"keywords": ["cafe"], "limit": 50},
        }
        app.tag_listbox = FakeListbox()
        app.keyword_listbox = FakeListbox()
        app.keyword_listbox.items = ["old"]
        app.limit_var = SimpleVar("123")

        app.refresh_tag_lists()

        self.assertEqual(app.tag_listbox.items, ["Dining", "Travel"])
        self.assertEqual(app.keyword_listbox.items, [])
        self.assertEqual(app.limit_var.get(), "")

    def test_refresh_tag_lists_disables_tag_details_until_a_tag_is_selected(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": ["cafe"], "limit": 50}}
        app.tag_listbox = FakeListbox()
        app.keyword_listbox = FakeListbox()
        app.keyword_listbox.items = ["old"]
        app.limit_var = SimpleVar("123")
        app.current_tag_name = "Dining"
        widgets = attach_tag_detail_widgets(app)

        app.refresh_tag_lists()

        self.assertIsNone(app.current_tag_name)
        self.assertEqual(app.keyword_listbox.items, [])
        self.assertEqual(app.limit_var.get(), "")
        self.assertTrue(all(widget.state == "disabled" for widget in widgets))

    def test_load_tag_details_populates_keywords_and_limit(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": ["cafe", "lunch"], "limit": 75}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.keyword_listbox = FakeListbox()
        app.limit_var = SimpleVar("")

        app.load_tag_details()

        self.assertEqual(app.keyword_listbox.items, ["cafe", "lunch"])
        self.assertEqual(app.limit_var.get(), "75")

    def test_load_tag_details_enables_details_and_clears_parent_category_selection(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": ["cafe"], "limit": 75, "parent_category": "Comida"}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.parent_category_listbox = FakeListbox()
        app.parent_category_listbox.items = ["Comida", "Sin clasificar"]
        app.parent_category_listbox.selection_set(0)
        app.keyword_listbox = FakeListbox()
        app.limit_var = SimpleVar("")
        widgets = attach_tag_detail_widgets(app)
        for widget in widgets:
            widget.configure(state="disabled")

        app.load_tag_details()

        self.assertEqual(app.current_tag_name, "Dining")
        self.assertEqual(app.parent_category_listbox.curselection(), ())
        self.assertTrue(all(widget.state == "normal" for widget in widgets))

    def test_selecting_parent_category_deselects_tag_and_disables_details(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": ["cafe"], "limit": 75, "parent_category": "Comida"}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.parent_category_listbox = FakeListbox()
        app.parent_category_listbox.items = ["Comida", "Sin clasificar"]
        app.parent_category_listbox.selection_set(0)
        app.keyword_listbox = FakeListbox()
        app.keyword_listbox.items = ["cafe"]
        app.limit_var = SimpleVar("91.5")
        app.current_tag_name = "Dining"
        widgets = attach_tag_detail_widgets(app)

        app.on_parent_category_selected()

        self.assertEqual(app.tags["Dining"]["limit"], Decimal("91.5"))
        self.assertEqual(app.tag_listbox.curselection(), ())
        self.assertIsNone(app.current_tag_name)
        self.assertEqual(app.keyword_listbox.items, [])
        self.assertEqual(app.limit_var.get(), "")
        self.assertTrue(all(widget.state == "disabled" for widget in widgets))

    def test_selecting_parent_category_keeps_tag_selected_when_current_edit_is_invalid(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": ["cafe"], "limit": 75, "parent_category": "Comida"}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.parent_category_listbox = FakeListbox()
        app.parent_category_listbox.items = ["Comida", "Sin clasificar"]
        app.parent_category_listbox.selection_set(0)
        app.keyword_listbox = FakeListbox()
        app.keyword_listbox.items = ["cafe"]
        app.limit_var = SimpleVar("bad limit")
        app.current_tag_name = "Dining"
        widgets = attach_tag_detail_widgets(app)

        with patch("purchase_tagger_app.messagebox.showwarning") as warning:
            app.on_parent_category_selected()

        self.assertEqual(app.tags["Dining"]["limit"], 75)
        self.assertEqual(app.tag_listbox.curselection(), (0,))
        self.assertEqual(app.current_tag_name, "Dining")
        self.assertEqual(app.keyword_listbox.items, ["cafe"])
        self.assertEqual(app.limit_var.get(), "bad limit")
        self.assertTrue(all(widget.state == "normal" for widget in widgets))
        warning.assert_called_once()

    def test_switching_tags_saves_previous_valid_decimal_limit(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {
            "Dining": {"keywords": ["cafe"], "limit": 75},
            "Travel": {"keywords": ["uber"], "limit": 125},
        }
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining", "Travel"]
        app.tag_listbox.selection_set(1)
        app.keyword_listbox = FakeListbox()
        app.limit_var = SimpleVar("42987.5")
        app.current_tag_name = "Dining"

        app.load_tag_details()

        self.assertEqual(app.tags["Dining"]["limit"], Decimal("42987.5"))
        self.assertEqual(app.current_tag_name, "Travel")
        self.assertEqual(app.keyword_listbox.items, ["uber"])
        self.assertEqual(app.limit_var.get(), "125")

    def test_switching_tags_with_invalid_limit_reselects_previous_tag(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {
            "Dining": {"keywords": ["cafe"], "limit": 75},
            "Travel": {"keywords": ["uber"], "limit": 125},
        }
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining", "Travel"]
        app.tag_listbox.selection_set(1)
        app.keyword_listbox = FakeListbox()
        app.keyword_listbox.items = ["cafe"]
        app.limit_var = SimpleVar("not a number")
        app.current_tag_name = "Dining"

        with patch("purchase_tagger_app.messagebox.showwarning") as warning:
            app.load_tag_details()

        self.assertEqual(app.tags["Dining"]["limit"], 75)
        self.assertEqual(app.current_tag_name, "Dining")
        self.assertEqual(app.tag_listbox.curselection(), (0,))
        self.assertEqual(app.keyword_listbox.items, ["cafe"])
        self.assertEqual(app.limit_var.get(), "not a number")
        warning.assert_called_once()

    def test_save_current_tag_limit_rejects_invalid_number(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": [], "limit": 75}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.limit_var = SimpleVar("oops")

        with patch("purchase_tagger_app.messagebox.showwarning") as warning:
            result = app.save_current_tag_limit()

        self.assertFalse(result)
        self.assertEqual(app.tags["Dining"]["limit"], 75)
        warning.assert_called_once()

    def test_save_current_tag_limit_accepts_decimal_limit(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": [], "limit": 75}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.limit_var = SimpleVar("42987.5")

        with patch("purchase_tagger_app.messagebox.showwarning") as warning:
            result = app.save_current_tag_limit()

        self.assertTrue(result)
        self.assertEqual(app.tags["Dining"]["limit"], Decimal("42987.5"))
        warning.assert_not_called()

    def test_export_tags_json_writes_current_tags_to_selected_path(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"tag_name": {"keywords": ["KEYWORD"], "limit": Decimal("10.5")}}
        app.status_var = SimpleVar("")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_file:
            path = temp_file.name

        try:
            with patch("purchase_tagger_app.filedialog.asksaveasfilename", return_value=path) as save_dialog, \
                    patch("purchase_tagger_app.messagebox.showinfo") as showinfo:
                app.export_tags_json()

            self.assertEqual(save_dialog.call_args.kwargs["initialfile"], "etiquetas.json")
            with open(path, encoding="utf-8") as exported:
                self.assertEqual(
                    json.load(exported),
                    {
                        "tag_name": {
                            "keywords": ["KEYWORD"],
                        "limit": 10.5,
                        "budget_type": "Expense",
                        "parent_category": "Sin clasificar",
                        "budget_period": "monthly",
                        "planned_amount": 10.5,
                        "expense_nature": None,
                            "financial_purpose": None,
                        }
                    },
                )
            showinfo.assert_called_once()
            self.assertEqual(app.status_var.get(), f"Etiquetas exportadas a {path}")
        finally:
            os.remove(path)

    def test_import_tags_json_merges_saves_refreshes_and_reports_counts(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": ["CAFE"], "limit": 1000}}
        app.tag_listbox = FakeListbox()
        app.keyword_listbox = FakeListbox()
        app.limit_var = SimpleVar("")
        app.status_var = SimpleVar("")
        app._refresh_tag_filter_options = Mock()

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as temp_file:
            path = temp_file.name
            json.dump(
                {
                    "Dining": {"keywords": ["CAFE", "LUNCH"], "limit": 2500},
                    "tag_name": {"keywords": ["KEYWORD"], "limit": 0},
                },
                temp_file,
            )

        try:
            with patch("purchase_tagger_app.filedialog.askopenfilename", return_value=path), \
                    patch("purchase_tagger_app.save_tags") as save_tags, \
                    patch("purchase_tagger_app.messagebox.showinfo") as showinfo:
                app.import_tags_json()

            self.assertEqual(app.tags["Dining"]["keywords"], ["CAFE", "LUNCH"])
            self.assertEqual(app.tags["Dining"]["planned_amount"], 2500)
            self.assertEqual(app.tags["tag_name"]["keywords"], ["KEYWORD"])
            self.assertEqual(app.tags["tag_name"]["parent_category"], "Sin clasificar")
            self.assertNotIn("subcategory", app.tags["tag_name"])
            self.assertEqual(app.tag_listbox.items, ["Dining", "tag_name"])
            save_tags.assert_called_once_with(app.tags)
            app._refresh_tag_filter_options.assert_called_once()
            showinfo.assert_called_once_with(
                "Importado",
                "Etiquetas importadas desde JSON.\n"
                "Etiquetas agregadas: 1\n"
                "Palabras clave agregadas: 2\n"
                "Montos actualizados: 1\n"
                "Datos actualizados: 0",
            )
            self.assertEqual(
                app.status_var.get(),
                "Se importaron 1 etiqueta, 2 palabras clave, se actualizaron 1 monto y 0 datos",
            )
        finally:
            os.remove(path)

    def test_import_tags_json_cancel_does_not_save(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": ["CAFE"], "limit": 1000}}

        with patch("purchase_tagger_app.filedialog.askopenfilename", return_value=""), \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.import_tags_json()

        self.assertEqual(app.tags, {"Dining": {"keywords": ["CAFE"], "limit": 1000}})
        save_tags.assert_not_called()

    def test_import_tags_json_invalid_json_shows_error_without_saving(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": ["CAFE"], "limit": 1000}}
        app.status_var = SimpleVar("")

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as temp_file:
            path = temp_file.name
            json.dump([], temp_file)

        try:
            with patch("purchase_tagger_app.filedialog.askopenfilename", return_value=path), \
                    patch("purchase_tagger_app.save_tags") as save_tags, \
                    patch("purchase_tagger_app.messagebox.showerror") as showerror:
                app.import_tags_json()

            self.assertEqual(app.tags, {"Dining": {"keywords": ["CAFE"], "limit": 1000}})
            save_tags.assert_not_called()
            showerror.assert_called_once()
            self.assertEqual(app.status_var.get(), "No se pudo importar")
        finally:
            os.remove(path)

    def test_import_tags_json_save_failure_preserves_current_tags(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": ["CAFE"], "limit": 1000}}
        app.tag_listbox = FakeListbox()
        app.keyword_listbox = FakeListbox()
        app.limit_var = SimpleVar("")
        app.status_var = SimpleVar("")
        app.refresh_tag_lists = Mock()
        app._refresh_tag_filter_options = Mock()

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as temp_file:
            path = temp_file.name
            json.dump({"Travel": {"keywords": ["UBER"], "limit": 2500}}, temp_file)

        try:
            with patch("purchase_tagger_app.filedialog.askopenfilename", return_value=path), \
                    patch("purchase_tagger_app.save_tags", side_effect=OSError("disk full")), \
                    patch("purchase_tagger_app.messagebox.showerror") as showerror:
                app.import_tags_json()

            self.assertEqual(app.tags, {"Dining": {"keywords": ["CAFE"], "limit": 1000}})
            app.refresh_tag_lists.assert_not_called()
            app._refresh_tag_filter_options.assert_not_called()
            showerror.assert_called_once()
            self.assertEqual(app.status_var.get(), "No se pudo importar")
        finally:
            os.remove(path)

    def test_tag_workspace_add_edit_remove_tag(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {}
        app.tag_listbox = FakeListbox()
        app.keyword_listbox = FakeListbox()
        app.limit_var = SimpleVar("")
        app.status_var = SimpleVar("")

        with patch("purchase_tagger_app.simple_input", return_value="Dining"), \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.add_tag()

        self.assertEqual(app.tags["Dining"]["keywords"], [])
        self.assertEqual(app.tags["Dining"]["planned_amount"], 0)
        self.assertEqual(app.tags["Dining"]["parent_category"], "Sin clasificar")
        self.assertEqual(app.tags["Dining"]["budget_period"], "monthly")
        self.assertEqual(app.tag_listbox.items, ["Dining"])
        save_tags.assert_called_once_with(app.tags)

        app.tag_listbox.selection_set(0)
        with patch("purchase_tagger_app.simple_input", return_value="Food"), \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.edit_tag()

        self.assertEqual(list(app.tags), ["Food"])
        self.assertEqual(app.tags["Food"]["keywords"], [])
        self.assertEqual(app.tags["Food"]["planned_amount"], 0)
        self.assertEqual(app.tag_listbox.items, ["Food"])
        save_tags.assert_called_once_with(app.tags)

        app.tag_listbox.selection_set(0)
        with patch("purchase_tagger_app.messagebox.askyesno", return_value=True), \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.remove_tag()

        self.assertEqual(app.tags, {})
        self.assertEqual(app.tag_listbox.items, [])
        save_tags.assert_called_once_with(app.tags)

    def test_add_tag_preserves_current_limit_edit(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": [], "limit": 75}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.keyword_listbox = FakeListbox()
        app.limit_var = SimpleVar("91.5")
        app.tag_name_var = SimpleVar("Dining")
        app.tag_name_entry = FakeWidget(textvariable=app.tag_name_var, state="disabled")
        app.tag_detail_widgets = [app.tag_name_entry]
        app.status_var = SimpleVar("")
        app.current_tag_name = "Dining"

        with patch("purchase_tagger_app.simple_input", return_value="Travel"), \
                patch("purchase_tagger_app.save_tags"):
            app.add_tag()

        self.assertEqual(app.tags["Dining"]["limit"], Decimal("91.5"))
        self.assertEqual(app.tags["Dining"]["planned_amount"], Decimal("91.5"))
        self.assertEqual(app.tags["Travel"]["keywords"], [])
        self.assertEqual(app.tags["Travel"]["planned_amount"], 0)
        self.assertEqual(app.tags["Travel"]["parent_category"], "Sin clasificar")
        self.assertEqual(app.tag_listbox.curselection(), (1,))
        self.assertEqual(app.tag_name_var.get(), "Travel")
        self.assertEqual(app.tag_name_entry.state, "normal")

    def test_edit_tag_carries_current_limit_edit_to_renamed_tag(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": [], "limit": 75}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.keyword_listbox = FakeListbox()
        app.limit_var = SimpleVar("91.5")
        app.status_var = SimpleVar("")
        app.current_tag_name = "Dining"

        with patch("purchase_tagger_app.simple_input", return_value="Food"), \
                patch("purchase_tagger_app.save_tags"):
            app.edit_tag()

        self.assertNotIn("Dining", app.tags)
        self.assertEqual(app.tags["Food"]["limit"], Decimal("91.5"))

    def test_invalid_current_limit_blocks_add_and_edit_tag_actions(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": [], "limit": 75}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.keyword_listbox = FakeListbox()
        app.limit_var = SimpleVar("bad limit")
        app.status_var = SimpleVar("")
        app.current_tag_name = "Dining"

        with patch("purchase_tagger_app.simple_input") as simple_input, \
                patch("purchase_tagger_app.messagebox.showwarning") as warning, \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.add_tag()
            app.edit_tag()

        self.assertEqual(app.tags, {"Dining": {"keywords": [], "limit": 75}})
        self.assertEqual(app.tag_listbox.items, ["Dining"])
        self.assertEqual(app.limit_var.get(), "bad limit")
        simple_input.assert_not_called()
        self.assertEqual(warning.call_count, 2)
        save_tags.assert_not_called()

    def test_remove_tag_resets_loaded_rows_and_reapplies_filter(self):
        rows = [
            ["01-ENE-25", "CAFE", "10.00", "USD", "Dining"],
            ["02-ENE-25", "HOTEL", "20.00", "USD", "Travel"],
        ]
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": [], "limit": 0}, "Travel": {"keywords": [], "limit": 0}}
        app.natag = "N/A"
        app.all_rows = rows
        app.filtered_rows = list(rows)
        app.tree_item_rows = {"item-a": rows[0], "item-b": rows[1]}
        app.tree = FakeTree(["item-a", "item-b"])
        app.tree.items["item-a"] = rows[0]
        app.tree.items["item-b"] = rows[1]
        app.search_var = SimpleVar("")
        app.currency_var = SimpleVar("Todas las monedas")
        app.month_var = SimpleVar("Todos")
        app.tag_filter_var = SimpleVar("Dining")
        app.total_var = SimpleVar("")
        app.visible_count_var = SimpleVar("")
        app.kpi_vars = {
            "total_rows": SimpleVar("0"),
            "visible_rows": SimpleVar("0"),
            "untagged_rows": SimpleVar("0"),
            "currency_count": SimpleVar("0"),
            "over_limit_tags": SimpleVar("0"),
        }
        app.currency_menu = FakeMenu()
        app.month_menu = FakeMenu()
        app.tag_menu = FakeMenu()
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining", "Travel"]
        app.tag_listbox.selection_set(0)
        app.keyword_listbox = FakeListbox()
        app.limit_var = SimpleVar("0")
        app.status_var = SimpleVar("")

        with patch("purchase_tagger_app.messagebox.askyesno", return_value=True), \
                patch("purchase_tagger_app.save_tags"):
            app.remove_tag()

        self.assertEqual(rows[0][4], "N/A")
        self.assertEqual(rows[1][4], "Travel")
        self.assertEqual(app.tag_filter_var.get(), "Todos")
        self.assertEqual(app.filtered_rows, rows)
        self.assertEqual(app.kpi_vars["untagged_rows"].get(), "1")
        self.assertEqual(app.status_var.get(), 'Se eliminó la etiqueta "Dining"')

    def test_tag_workspace_add_edit_remove_keyword(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"keywords": [], "limit": 0}}
        app.tag_listbox = FakeListbox()
        app.tag_listbox.items = ["Dining"]
        app.tag_listbox.selection_set(0)
        app.keyword_listbox = FakeListbox()
        app.limit_var = SimpleVar("0")
        app.status_var = SimpleVar("")

        with patch("purchase_tagger_app.simple_input", return_value="cafe"), \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.add_keyword()

        self.assertEqual(app.tags["Dining"]["keywords"], ["cafe"])
        self.assertEqual(app.keyword_listbox.items, ["cafe"])
        save_tags.assert_called_once_with(app.tags)

        app.keyword_listbox.selection_set(0)
        with patch("purchase_tagger_app.simple_input", return_value="lunch"), \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.edit_keyword()

        self.assertEqual(app.tags["Dining"]["keywords"], ["lunch"])
        self.assertEqual(app.keyword_listbox.items, ["lunch"])
        save_tags.assert_called_once_with(app.tags)

        app.keyword_listbox.selection_set(0)
        with patch("purchase_tagger_app.messagebox.askyesno", return_value=True), \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.remove_keyword()

        self.assertEqual(app.tags["Dining"]["keywords"], [])
        self.assertEqual(app.keyword_listbox.items, [])
        save_tags.assert_called_once_with(app.tags)

    def test_draw_summary_shows_empty_state_before_currency_state(self):
        app = object.__new__(PurchaseTaggerUI)
        app.all_rows = []
        app.filtered_rows = []
        app.summary_frame = FakeFrame([FakeWidget()])
        app.summary_currency_vars = {}
        app.summary_month_var = SimpleVar("Todos")
        app.summary_choice_var = SimpleVar("Gasto por etiqueta")

        with patch("purchase_tagger_app.ctk.CTkFont", return_value="font"), \
                patch("purchase_tagger_app.ctk.CTkLabel", side_effect=FakeWidget) as label:
            app.draw_summary()

        self.assertTrue(app.summary_frame.winfo_children()[0].destroyed)
        self.assertEqual(label.call_args.kwargs["text"], "Carga compras para ver resúmenes.")

    def test_draw_summary_uses_all_rows_independent_of_purchase_filter(self):
        all_rows = [
            ["01-ENE-25", "CAFE", "-80.00", "USD", "Dining"],
            ["02-FEB-25", "MARKET", "-90.00", "CRC", "Groceries"],
        ]
        app = object.__new__(PurchaseTaggerUI)
        app.all_rows = all_rows
        app.filtered_rows = [all_rows[0]]
        app.summary_frame = FakeFrame()
        app.summary_currency_vars = {
            "USD": SimpleVar(True),
            "CRC": SimpleVar(False),
        }
        app.summary_month_var = SimpleVar("Todos")
        app.summary_choice_var = SimpleVar("Gasto por etiqueta")
        app.tags = {}
        with patch("purchase_tagger_app.filter_rows_by_month", side_effect=lambda rows, month: list(rows)) as month_filter, \
                patch("purchase_tagger_app.summary_aggregates", return_value={
                    "tag_totals": {"Dining": Decimal("80.00")},
                    "monthly_totals": {},
                    "cumulative_points": [],
                }) as aggregates, \
                patch("purchase_tagger_app.plt.subplots", return_value=(FakeFigure(), FakeAxes())), \
                patch("purchase_tagger_app.FigureCanvasTkAgg", return_value=FakeCanvas()):
            app.draw_summary()

        self.assertEqual(month_filter.call_args.args[0], all_rows)
        self.assertEqual(aggregates.call_args.args[0], all_rows)

    def test_draw_summary_updates_insights_with_selected_currency_and_month(self):
        all_rows = [
            ["01-ENE-25", "CAFE", "-80.00", "USD", "Dining"],
            ["02-FEB-25", "MARKET", "-90.00", "CRC", "Groceries"],
        ]
        app = object.__new__(PurchaseTaggerUI)
        app.all_rows = all_rows
        app.summary_frame = FakeFrame()
        app.summary_currency_vars = {
            "USD": SimpleVar(True),
            "CRC": SimpleVar(False),
        }
        app.summary_month_var = SimpleVar("2025-01")
        app.summary_choice_var = SimpleVar("Gasto por etiqueta")
        app.tags = {"Dining": {"limit": 100}}
        calls = []
        app._render_summary_insights = lambda rows, selected, month: calls.append((rows, selected, month))

        with patch("purchase_tagger_app.filter_rows_by_month", side_effect=lambda rows, month: list(rows)), \
                patch("purchase_tagger_app.summary_aggregates", return_value={
                    "tag_totals": {"Dining": Decimal("80.00")},
                    "monthly_totals": {},
                    "cumulative_points": [],
                }), \
                patch("purchase_tagger_app.plt.subplots", return_value=(FakeFigure(), FakeAxes())), \
                patch("purchase_tagger_app.FigureCanvasTkAgg", return_value=FakeCanvas()):
            app.draw_summary()

        self.assertEqual(calls, [(all_rows, {"USD"}, "2025-01")])

    def test_style_summary_axes_applies_analytical_presentation(self):
        app = object.__new__(PurchaseTaggerUI)
        ax = FakeAxes()

        app._style_summary_axes(ax, "Gasto mensual", ylabel="Total")

        self.assertEqual(ax.title, "Gasto mensual")
        self.assertEqual(ax.title_kwargs["loc"], "left")
        self.assertEqual(ax.ylabel, "Total")
        self.assertEqual(ax.ylabel_kwargs["color"], "#4b5563")
        self.assertEqual(ax.facecolor, "#ffffff")
        self.assertTrue(ax.grid_calls)
        self.assertEqual(ax.grid_calls[0][1]["axis"], "y")
        self.assertFalse(ax.spines["top"].visible)
        self.assertFalse(ax.spines["right"].visible)

    def test_summary_status_color_marks_over_limit_spend(self):
        app = object.__new__(PurchaseTaggerUI)

        self.assertEqual(app._summary_status_color(80.0, 50.0), "#dc2626")
        self.assertEqual(app._summary_status_color(40.0, 50.0), "#2563eb")
        self.assertEqual(app._summary_status_color(40.0, 0.0), "#2563eb")

    def test_render_summary_insights_sets_headline_and_detail(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tags = {"Dining": {"limit": Decimal("50.00")}}
        app.natag = "N/A"
        app.summary_insight_vars = {
            "total_spend": SimpleVar(),
            "purchase_count": SimpleVar(),
            "top_tag": SimpleVar(),
            "over_limit": SimpleVar(),
            "largest_purchase": SimpleVar(),
        }
        app.summary_headline_var = SimpleVar()
        app.summary_messages_var = SimpleVar()

        with patch("purchase_tagger_app.summary_insights", return_value={
            "total_spend": Decimal("80.00"),
            "purchase_count": 1,
            "top_tags": [("Dining", Decimal("80.00"))],
            "over_limit_tags": [("Dining", Decimal("80.00"), Decimal("50.00"))],
            "largest_purchases": [["01-ENE-25", "CAFE", "-80.00", "USD", "Dining"]],
            "headline": "Dining supera su presupuesto por USD 30.00.",
            "detail": "- Dining representa el 100.0% del gasto.\n- El gasto total es USD 80.00 en 1 compra.",
            "messages": [],
        }):
            app._render_summary_insights([["01-ENE-25", "CAFE", "-80.00", "USD", "Dining"]], {"USD"}, "Todos")

        self.assertEqual(app.summary_headline_var.get(), "Dining supera su presupuesto por USD 30.00.")
        self.assertEqual(
            app.summary_messages_var.get(),
            "- Dining representa el 100.0% del gasto.\n- El gasto total es USD 80.00 en 1 compra.",
        )

    def test_summary_insights_panel_uses_highlighted_left_aligned_callout(self):
        app = object.__new__(PurchaseTaggerUI)
        app._panel = lambda parent, **kwargs: FakeFrame()
        FakeCtkFrame.instances = []

        with patch("purchase_tagger_app.tk.StringVar", side_effect=SimpleVar), \
                patch("purchase_tagger_app.ctk.CTkFont", return_value="font"), \
                patch("purchase_tagger_app.ctk.CTkFrame", side_effect=FakeCtkFrame), \
                patch("purchase_tagger_app.ctk.CTkLabel", side_effect=FakeWidget) as label:
            app._build_summary_insights_panel(FakeFrame(), row=1)

        callout = next(frame for frame in FakeCtkFrame.instances if frame.kwargs.get("fg_color") == "#fff7ed")
        self.assertEqual(callout.kwargs["border_color"], "#fed7aa")
        self.assertEqual(callout.grid_options["sticky"], "ew")
        self.assertEqual(callout.grid_options["columnspan"], 5)

        headline_label = next(
            call.kwargs
            for call in label.call_args_list
            if call.kwargs.get("textvariable") is app.summary_headline_var
        )
        detail_label = next(
            call.kwargs
            for call in label.call_args_list
            if call.kwargs.get("textvariable") is app.summary_messages_var
        )
        self.assertEqual(headline_label["anchor"], "w")
        self.assertEqual(detail_label["anchor"], "w")
        self.assertEqual(headline_label["justify"], "left")
        self.assertEqual(detail_label["justify"], "left")

    def test_draw_summary_shows_message_when_multiple_currencies_are_selected(self):
        app = object.__new__(PurchaseTaggerUI)
        app.all_rows = [
            ["01-ENE-25", "CAFE", "-80.00", "USD", "Dining"],
            ["02-FEB-25", "MARKET", "-90.00", "CRC", "Groceries"],
        ]
        app.summary_frame = FakeFrame()
        app.summary_currency_vars = {
            "USD": SimpleVar(True),
            "CRC": SimpleVar(True),
        }
        app.summary_month_var = SimpleVar("Todos")
        app.summary_choice_var = SimpleVar("Gasto por etiqueta")
        calls = []
        app._render_summary_insights = lambda rows, selected, month: calls.append((rows, selected, month))

        with patch("purchase_tagger_app.ctk.CTkFont", return_value="font"), \
                patch("purchase_tagger_app.ctk.CTkLabel", side_effect=FakeWidget) as label, \
                patch("purchase_tagger_app.summary_aggregates") as aggregates:
            app.draw_summary()

        self.assertEqual(label.call_args.kwargs["text"], "Selecciona una sola moneda para no mezclar monedas.")
        self.assertEqual(calls, [(app.all_rows, {"CRC", "USD"}, "Todos")])
        aggregates.assert_not_called()

    def test_draw_summary_limit_chart_uses_alert_color_for_over_limit_tags(self):
        app = object.__new__(PurchaseTaggerUI)
        app.all_rows = [["01-ENE-25", "CAFE", "-80.00", "USD", "Dining"]]
        app.summary_frame = FakeFrame()
        app.summary_currency_vars = {"USD": SimpleVar(True)}
        app.summary_month_var = SimpleVar("Todos")
        app.summary_choice_var = SimpleVar("Presupuesto vs gasto por etiqueta")
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

    def test_draw_summary_uses_pie_chart_for_negative_purchase_spend(self):
        app = object.__new__(PurchaseTaggerUI)
        app.all_rows = [
            ["01-ENE-25", "CARD PAYMENT", "-80.00", "USD", "Payments", "-"],
            ["02-ENE-25", "CAFE", "30.00", "USD", "Dining", "+"],
        ]
        app.summary_frame = FakeFrame()
        app.summary_currency_vars = {"USD": SimpleVar(True)}
        app.summary_month_var = SimpleVar("Todos")
        app.summary_choice_var = SimpleVar("Gasto por etiqueta")
        app.tags = {}
        app._render_summary_insights = lambda rows, selected, month: None
        ax = FakeAxes()

        with patch("purchase_tagger_app.filter_rows_by_month", side_effect=lambda rows, month: list(rows)), \
                patch("purchase_tagger_app.plt.subplots", return_value=(FakeFigure(), ax)), \
                patch("purchase_tagger_app.FigureCanvasTkAgg", return_value=FakeCanvas()):
            app.draw_summary()

        self.assertEqual(len(ax.pie_calls), 1)
        self.assertEqual(len(ax.bar_calls), 0)

    def test_sort_column_uses_decimal_for_amounts(self):
        app = object.__new__(PurchaseTaggerUI)
        app.tree = FakeTree(["row-a", "row-b", "row-c"])
        app.tree.items = {
            "row-a": ["01-ENE-25", "A", "10.00", "USD", "Misc"],
            "row-b": ["02-ENE-25", "B", "2.00", "USD", "Misc"],
            "row-c": ["03-ENE-25", "C", "1,000.00", "USD", "Misc"],
        }

        app.sort_column("amount", False)

        self.assertEqual(app.tree.visible_order, ["row-b", "row-a", "row-c"])

    def test_export_csv_writes_visible_sign_column_order(self):
        app = object.__new__(PurchaseTaggerUI)
        app.filtered_rows = [["01-ENE-25", "CAFE", "-10.00", "USD", "Dining", "-"]]

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
            path = temp_file.name

        try:
            with patch("purchase_tagger_app.filedialog.asksaveasfilename", return_value=path), \
                    patch("purchase_tagger_app.messagebox.showinfo") as showinfo:
                app.export_csv()

            with open(path, newline="", encoding="utf-8") as exported:
                rows = [line.strip() for line in exported.readlines()]

            self.assertEqual(rows[0], "fecha,descripcion,signo,monto,moneda,etiqueta")
            self.assertEqual(rows[1], "01-ENE-25,CAFE,-,10.00,USD,Dining")
            showinfo.assert_called_once()
        finally:
            os.remove(path)

    def test_clear_summary_frame_destroys_canvas_widget_and_clears_refs(self):
        app = object.__new__(PurchaseTaggerUI)
        app.summary_frame = FakeFrame([FakeWidget()])
        app.summary_canvas = FakeCanvas()
        app.summary_figure = object()

        with patch("purchase_tagger_app.plt.close") as close:
            app._clear_summary_frame()

        self.assertTrue(app.summary_canvas is None)
        self.assertTrue(app.summary_figure is None)
        self.assertTrue(app.summary_frame.winfo_children()[0].destroyed)
        self.assertTrue(close.called)

    def test_average_spend_table_marks_rows_over_limit(self):
        app = object.__new__(PurchaseTaggerUI)
        app.summary_frame = FakeFrame()
        app.tags = {
            "Dining": {"limit": 50, "parent_category": "Comida"},
            "Groceries": {"limit": 200, "parent_category": "Comida"},
        }
        rows = [
            ["01-ENE-25", "CAFE", "-80.00", "USD", "Dining"],
            ["02-ENE-25", "MARKET", "-90.00", "USD", "Groceries"],
        ]
        FakeSummaryTree.instances = []

        with patch("purchase_tagger_app.ttk.Treeview", side_effect=FakeSummaryTree), \
                patch("purchase_tagger_app.ttk.Scrollbar", side_effect=FakeWidget):
            app._draw_average_spend_table(rows, {"USD"})

        tree = FakeSummaryTree.instances[0]
        self.assertIn("over_limit", tree.tag_options)
        dining_row = next(row for row in tree.rows if row["values"][0] == "  Dining")
        self.assertEqual(dining_row["tags"], ["over_limit"])
        self.assertEqual(tree.rows[-1]["values"][0], "Total")

    def test_average_spend_table_groups_tags_under_parent_category_rows(self):
        app = object.__new__(PurchaseTaggerUI)
        app.summary_frame = FakeFrame()
        app.tags = {
            "Dining": {"limit": 80, "parent_category": "Alimentación"},
            "Groceries": {"limit": 120, "parent_category": "Alimentación"},
            "Bus": {"limit": 50, "parent_category": "Transporte"},
        }
        rows = [
            ["01-ENE-25", "CAFE", "-90.00", "USD", "Dining"],
            ["02-ENE-25", "MARKET", "-60.00", "USD", "Groceries"],
            ["03-ENE-25", "BUS", "-20.00", "USD", "Bus"],
        ]
        FakeSummaryTree.instances = []

        with patch("purchase_tagger_app.ttk.Treeview", side_effect=FakeSummaryTree), \
                patch("purchase_tagger_app.ttk.Scrollbar", side_effect=FakeWidget):
            app._draw_average_spend_table(rows, {"USD"})

        tree = FakeSummaryTree.instances[0]
        self.assertEqual(
            [row["values"][0] for row in tree.rows],
            ["Alimentación", "  Dining", "  Groceries", "Transporte", "  Bus", "Total"],
        )
        self.assertEqual(tree.rows[0]["values"], ["Alimentación", "200.00", "150.00", "150.00", "150.00"])
        self.assertEqual(tree.rows[0]["tags"], ["category"])

    def test_average_spend_table_marks_parent_category_over_budget_red(self):
        app = object.__new__(PurchaseTaggerUI)
        app.summary_frame = FakeFrame()
        app.tags = {
            "Dining": {"limit": 50, "parent_category": "Comida"},
            "Groceries": {"limit": 100, "parent_category": "Comida"},
        }
        rows = [
            ["01-ENE-25", "CAFE", "-80.00", "USD", "Dining"],
            ["02-ENE-25", "MARKET", "-90.00", "USD", "Groceries"],
        ]
        FakeSummaryTree.instances = []

        with patch("purchase_tagger_app.ttk.Treeview", side_effect=FakeSummaryTree), \
                patch("purchase_tagger_app.ttk.Scrollbar", side_effect=FakeWidget):
            app._draw_average_spend_table(rows, {"USD"})

        tree = FakeSummaryTree.instances[0]
        self.assertEqual(tree.rows[0]["values"][0], "Comida")
        self.assertEqual(tree.rows[0]["values"][1], "150.00")
        self.assertEqual(tree.rows[0]["values"][-1], "170.00")
        self.assertEqual(tree.rows[0]["tags"], ["over_limit"])

    def test_average_spend_table_keeps_report_month_columns_without_tag_spend(self):
        app = object.__new__(PurchaseTaggerUI)
        app.summary_frame = FakeFrame()
        app.tags = {"Dining": {"limit": 40, "parent_category": "Comida"}}
        rows = [
            ["01-ENE-25", "CAFE", "-90.00", "USD", "Dining"],
            ["02-FEB-25", "MARKET", "-120.00", "CRC", "Groceries"],
            ["03-MAR-25", "DINNER", "-60.00", "USD", "Dining"],
        ]
        FakeSummaryTree.instances = []

        with patch("purchase_tagger_app.ttk.Treeview", side_effect=FakeSummaryTree), \
                patch("purchase_tagger_app.ttk.Scrollbar", side_effect=FakeWidget):
            app._draw_average_spend_table(rows, {"USD"}, report_months=["2025-01", "2025-02", "2025-03"])

        tree = FakeSummaryTree.instances[0]
        self.assertEqual(
            tree.columns,
            ["Etiqueta", "Presupuesto", "2025-01_USD", "2025-02_USD", "2025-03_USD", "Total", "Promedio"],
        )
        self.assertEqual(tree.rows[0]["values"], ["Comida", "40.00", "90.00", "", "60.00", "150.00", "50.00"])
        self.assertEqual(tree.rows[1]["values"], ["  Dining", "40.00", "90.00", "", "60.00", "150.00", "50.00"])


if __name__ == "__main__":
    unittest.main()
