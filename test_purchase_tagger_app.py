import unittest
from unittest.mock import patch

from purchase_tagger_app import PurchaseTaggerUI


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

    def winfo_exists(self):
        return 1


class FakeMenu:
    def __init__(self):
        self.values = []

    def configure(self, **kwargs):
        if "values" in kwargs:
            self.values = list(kwargs["values"])


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

    def grid_rowconfigure(self, row, weight=0):
        self.grid_rows[row] = weight

    def grid_columnconfigure(self, column, weight=0):
        self.grid_columns[column] = weight

    def update_idletasks(self):
        pass


class FakeWidget:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.grid_options = None
        self.packed = False
        self.destroyed = False

    def grid(self, **kwargs):
        self.grid_options = kwargs

    def pack(self, **kwargs):
        self.packed = True

    def destroy(self):
        self.destroyed = True

    def set(self, *args):
        pass


class FakeCanvas:
    def __init__(self):
        self.widget = FakeWidget()

    def get_tk_widget(self):
        return self.widget

    def draw(self):
        pass


class FakeAxes:
    def pie(self, *args, **kwargs):
        pass

    def bar(self, *args, **kwargs):
        pass

    def plot(self, *args, **kwargs):
        pass

    def set_title(self, *args, **kwargs):
        pass

    def set_ylabel(self, *args, **kwargs):
        pass

    def tick_params(self, *args, **kwargs):
        pass

    def set_xticks(self, *args, **kwargs):
        pass

    def set_xticklabels(self, *args, **kwargs):
        pass

    def legend(self, *args, **kwargs):
        pass


class FakeFigure:
    def tight_layout(self):
        pass


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
        self.assertEqual(app.tree.items["item-b"], rows[1])

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
        self.assertEqual(app.tree.items["item-b"], rows[1])
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
        app.currency_var = SimpleVar("All currencies")
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
        self.assertEqual(app.total_var.get(), "Totals: USD 10.00")

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
        self.assertEqual(app.total_var.get(), "Totals: CRC 20.00")
        self.assertEqual(app.visible_count_var.get(), "Showing 1 purchases")
        self.assertEqual(app.kpi_vars["total_rows"].get(), "2")
        self.assertEqual(app.kpi_vars["visible_rows"].get(), "1")
        self.assertEqual(app.currency_menu.values, ["All currencies", "CRC", "USD"])
        self.assertEqual(app.month_menu.values, ["Todos", "2025-01", "2025-02"])
        self.assertEqual(app.tag_menu.values, ["Todos", "Groceries", "Shopping"])

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

        self.assertEqual(app.currency_var.get(), "All currencies")
        self.assertEqual(app.month_var.get(), "Todos")
        self.assertEqual(app.tag_filter_var.get(), "Todos")
        self.assertEqual(app.filtered_rows, rows)
        self.assertEqual(app.total_var.get(), "Totals: CRC 20.00; USD 10.00")
        self.assertEqual(app.visible_count_var.get(), "Showing 2 purchases")

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
        app.currency_var = SimpleVar("All currencies")
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
        self.assertEqual(app.visible_count_var.get(), "Showing 1 purchases")
        self.assertEqual(app.total_var.get(), "Totals: USD 20.00")
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
        app.file_label_var = SimpleVar("No PDFs selected")
        app.total_var = SimpleVar("Totals: 0.00")
        app.kpi_vars = {"total_rows": SimpleVar("0")}

        app._clear_workspace_widget_refs()

        for name in ("tree", "currency_menu", "summary_frame", "tag_listbox", "limit_var"):
            self.assertNotIn(name, app.__dict__)
        self.assertEqual(app.month_var.get(), "Todos")
        self.assertEqual(app.search_var.get(), "apple")
        self.assertEqual(app.tag_filter_var.get(), "N/A")
        self.assertEqual(app.file_label_var.get(), "No PDFs selected")
        self.assertEqual(app.total_var.get(), "Totals: 0.00")
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

        self.assertEqual(app.tags["Dining"]["limit"], 42987.5)
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
        self.assertEqual(app.tags["Dining"]["limit"], 42987.5)
        warning.assert_not_called()

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

        self.assertEqual(app.tags, {"Dining": {"keywords": [], "limit": 0}})
        self.assertEqual(app.tag_listbox.items, ["Dining"])
        save_tags.assert_called_once_with(app.tags)

        app.tag_listbox.selection_set(0)
        with patch("purchase_tagger_app.simple_input", return_value="Food"), \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.edit_tag()

        self.assertEqual(app.tags, {"Food": {"keywords": [], "limit": 0}})
        self.assertEqual(app.tag_listbox.items, ["Food"])
        save_tags.assert_called_once_with(app.tags)

        app.tag_listbox.selection_set(0)
        with patch("purchase_tagger_app.messagebox.askyesno", return_value=True), \
                patch("purchase_tagger_app.save_tags") as save_tags:
            app.remove_tag()

        self.assertEqual(app.tags, {})
        self.assertEqual(app.tag_listbox.items, [])
        save_tags.assert_called_once_with(app.tags)

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
        app.currency_var = SimpleVar("All currencies")
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
        self.assertEqual(app.status_var.get(), 'Removed tag "Dining"')

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
        app.summary_choice_var = SimpleVar("Spend by Tag")

        with patch("purchase_tagger_app.ctk.CTkFont", return_value="font"), \
                patch("purchase_tagger_app.ctk.CTkLabel", side_effect=FakeWidget) as label:
            app.draw_summary()

        self.assertTrue(app.summary_frame.winfo_children()[0].destroyed)
        self.assertEqual(label.call_args.kwargs["text"], "Load purchases to see summaries.")

    def test_draw_summary_uses_all_rows_independent_of_purchase_filter(self):
        all_rows = [
            ["01-ENE-25", "CAFE", "80.00", "USD", "Dining"],
            ["02-FEB-25", "MARKET", "90.00", "CRC", "Groceries"],
        ]
        app = object.__new__(PurchaseTaggerUI)
        app.all_rows = all_rows
        app.filtered_rows = [all_rows[0]]
        app.summary_frame = FakeFrame()
        app.summary_currency_vars = {
            "USD": SimpleVar(True),
            "CRC": SimpleVar(True),
        }
        app.summary_month_var = SimpleVar("Todos")
        app.summary_choice_var = SimpleVar("Spend by Tag")
        app.tags = {}
        with patch("purchase_tagger_app.filter_rows_by_month", side_effect=lambda rows, month: list(rows)) as month_filter, \
                patch("purchase_tagger_app.summary_aggregates", return_value={
                    "tag_totals": {"Dining": 80, "Groceries": 90},
                    "monthly_totals": {},
                    "cumulative_points": [],
                }) as aggregates, \
                patch("purchase_tagger_app.plt.subplots", return_value=(FakeFigure(), FakeAxes())), \
                patch("purchase_tagger_app.FigureCanvasTkAgg", return_value=FakeCanvas()):
            app.draw_summary()

        self.assertEqual(month_filter.call_args.args[0], all_rows)
        self.assertEqual(aggregates.call_args.args[0], all_rows)

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
            "Dining": {"limit": 50},
            "Groceries": {"limit": 200},
        }
        rows = [
            ["01-ENE-25", "CAFE", "80.00", "USD", "Dining"],
            ["02-ENE-25", "MARKET", "90.00", "USD", "Groceries"],
        ]
        FakeSummaryTree.instances = []

        with patch("purchase_tagger_app.ttk.Treeview", side_effect=FakeSummaryTree), \
                patch("purchase_tagger_app.ttk.Scrollbar", side_effect=FakeWidget):
            app._draw_average_spend_table(rows, {"USD"})

        tree = FakeSummaryTree.instances[0]
        self.assertIn("over_limit", tree.tag_options)
        self.assertEqual(tree.rows[0]["values"][0], "Dining")
        self.assertEqual(tree.rows[0]["tags"], ["over_limit"])
        self.assertEqual(tree.rows[-1]["values"][0], "Total")


if __name__ == "__main__":
    unittest.main()
