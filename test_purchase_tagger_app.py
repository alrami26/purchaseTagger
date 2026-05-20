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


if __name__ == "__main__":
    unittest.main()
