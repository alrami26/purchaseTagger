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


if __name__ == "__main__":
    unittest.main()
