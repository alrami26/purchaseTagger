import unittest
from unittest.mock import patch

from purchase_tagger_app import PurchaseTaggerUI


class FakeTree:
    def __init__(self, visible_order):
        self.visible_order = list(visible_order)
        self.items = {}

    def index(self, item_iid):
        return self.visible_order.index(item_iid)

    def item(self, item_iid, values=None):
        if values is not None:
            self.items[item_iid] = list(values)
        return {"values": self.items.get(item_iid)}


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
