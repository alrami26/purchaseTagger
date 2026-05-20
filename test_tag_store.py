import json
import tempfile
from pathlib import Path
import unittest

from tag_store import load_tags, save_tags, tag_purchase


class TagStoreTest(unittest.TestCase):
    def test_load_tags_creates_empty_file_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.json"

            self.assertEqual(load_tags(path), {})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {})

    def test_load_tags_migrates_old_keyword_list_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.json"
            path.write_text(json.dumps({"Groceries": ["MARKET", "STORE"]}), encoding="utf-8")

            self.assertEqual(
                load_tags(path),
                {"Groceries": {"keywords": ["MARKET", "STORE"], "limit": 0}},
            )

    def test_load_tags_preserves_new_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.json"
            original = {"Dining": {"keywords": ["CAFE"], "limit": 12000}}
            path.write_text(json.dumps(original), encoding="utf-8")

            self.assertEqual(load_tags(path), original)

    def test_save_tags_writes_current_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.json"
            tags = {"Travel": {"keywords": ["UBER"], "limit": 5000}}

            save_tags(tags, path)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), tags)

    def test_tag_purchase_matches_case_insensitive_keyword(self):
        tags = {
            "Groceries": {"keywords": ["market"], "limit": 0},
            "Dining": {"keywords": ["cafe"], "limit": 0},
        }

        self.assertEqual(tag_purchase("CITY MARKET CENTRAL", tags), "Groceries")
        self.assertEqual(tag_purchase("Unknown merchant", tags), "N/A")


if __name__ == "__main__":
    unittest.main()
