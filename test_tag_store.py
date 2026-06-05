import json
import os
import sys
from unittest import mock
import tempfile
from decimal import Decimal
from pathlib import Path
import unittest

import tag_store
from tag_store import default_tag_file_path, load_tags, save_tags, tag_purchase


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

    def test_load_tags_rejects_invalid_json_shape(self):
        invalid_cases = [
            [],
            {"Dining": "CAFE"},
            {"Dining": {"keywords": "CAFE", "limit": 12000}},
            {"Dining": {"keywords": ["CAFE"], "limit": "12000"}},
            {"Dining": {"keywords": [123], "limit": 12000}},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.json"
            for value in invalid_cases:
                with self.subTest(value=value):
                    path.write_text(json.dumps(value), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "Invalid tags.json"):
                        load_tags(path)

    def test_save_tags_writes_current_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.json"
            tags = {"Travel": {"keywords": ["UBER"], "limit": 5000}}

            save_tags(tags, path)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), tags)

    def test_save_tags_serializes_decimal_limits_as_json_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.json"
            tags = {"Travel": {"keywords": ["UBER"], "limit": Decimal("5000.50")}}

            save_tags(tags, path)

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"Travel": {"keywords": ["UBER"], "limit": 5000.5}},
            )

    def test_save_tags_writes_atomically_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.json"
            original = {"Dining": {"keywords": ["CAFE"], "limit": 1000}}
            updated = {"Travel": {"keywords": ["UBER"], "limit": 5000}}
            path.write_text(json.dumps(original), encoding="utf-8")

            save_tags(updated, path)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), updated)
            self.assertEqual(json.loads(path.with_suffix(".json.bak").read_text(encoding="utf-8")), original)
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_save_tags_preserves_existing_file_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.json"
            original = {"Dining": {"keywords": ["CAFE"], "limit": 1000}}
            updated = {"Travel": {"keywords": ["UBER"], "limit": 5000}}
            path.write_text(json.dumps(original), encoding="utf-8")

            with mock.patch("tag_store.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    save_tags(updated, path)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), original)

    def test_merge_tags_adds_new_tag_from_import(self):
        current = {"Dining": {"keywords": ["CAFE"], "limit": 1000}}
        imported = {"tag_name": {"keywords": ["STORE"], "limit": 2000}}

        merged, counts = tag_store.merge_tags(current, imported)

        self.assertEqual(
            merged,
            {
                "Dining": {"keywords": ["CAFE"], "limit": 1000},
                "tag_name": {"keywords": ["STORE"], "limit": 2000},
            },
        )
        self.assertEqual(counts, {"tags_added": 1, "keywords_added": 1, "limits_updated": 0})

    def test_merge_tags_adds_keywords_and_replaces_existing_limit(self):
        current = {"Dining": {"keywords": ["CAFE"], "limit": 1000}}
        imported = {"Dining": {"keywords": ["CAFE", "LUNCH"], "limit": 2500}}

        merged, counts = tag_store.merge_tags(current, imported)

        self.assertEqual(merged["Dining"], {"keywords": ["CAFE", "LUNCH"], "limit": 2500})
        self.assertEqual(counts, {"tags_added": 0, "keywords_added": 1, "limits_updated": 1})

    def test_merge_tags_does_not_duplicate_existing_keywords(self):
        current = {"Dining": {"keywords": ["CAFE"], "limit": 1000}}
        imported = {"Dining": {"keywords": ["CAFE"], "limit": 1000}}

        merged, counts = tag_store.merge_tags(current, imported)

        self.assertEqual(merged["Dining"]["keywords"], ["CAFE"])
        self.assertEqual(counts, {"tags_added": 0, "keywords_added": 0, "limits_updated": 0})

    def test_default_tag_file_path_keeps_source_tags_json_in_dev_mode(self):
        expected = Path(tag_store.__file__).resolve().parent / "tags.json"

        with mock.patch.object(sys, "frozen", False, create=True):
            self.assertEqual(default_tag_file_path(), expected)

    def test_default_tag_file_path_uses_windows_appdata_when_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdata = Path(tmp) / "Roaming"

            with mock.patch.object(sys, "frozen", True, create=True), \
                    mock.patch.object(sys, "platform", "win32"), \
                    mock.patch.dict(os.environ, {"APPDATA": str(appdata)}, clear=False):
                self.assertEqual(
                    default_tag_file_path(),
                    appdata / "PurchaseTagger" / "tags.json",
                )

    def test_load_tags_copies_bundled_tags_to_appdata_on_first_frozen_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            appdata = root / "Roaming"
            bundle = root / "bundle"
            exe_dir = root / "exe"
            bundle.mkdir()
            exe_dir.mkdir()
            source_tags = {"Dining": {"keywords": ["CAFE"], "limit": 12000}}
            (bundle / "tags.json").write_text(json.dumps(source_tags), encoding="utf-8")

            with mock.patch.object(sys, "frozen", True, create=True), \
                    mock.patch.object(sys, "_MEIPASS", str(bundle), create=True), \
                    mock.patch.object(sys, "executable", str(exe_dir / "app.exe")), \
                    mock.patch.object(sys, "platform", "win32"), \
                    mock.patch.dict(os.environ, {"APPDATA": str(appdata)}, clear=False):
                tags = load_tags()

            target = appdata / "PurchaseTagger" / "tags.json"
            self.assertEqual(tags, source_tags)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), source_tags)

    def test_load_tags_does_not_copy_bundle_over_existing_appdata_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            appdata = root / "Roaming"
            bundle = root / "bundle"
            exe_dir = root / "exe"
            bundle.mkdir()
            exe_dir.mkdir()
            target = appdata / "PurchaseTagger" / "tags.json"
            target.parent.mkdir(parents=True)
            existing = {"Existing": {"keywords": ["KEEP"], "limit": 1}}
            bundled = {"Bundled": {"keywords": ["COPY"], "limit": 2}}
            target.write_text(json.dumps(existing), encoding="utf-8")
            (bundle / "tags.json").write_text(json.dumps(bundled), encoding="utf-8")

            with mock.patch.object(sys, "frozen", True, create=True), \
                    mock.patch.object(sys, "_MEIPASS", str(bundle), create=True), \
                    mock.patch.object(sys, "executable", str(exe_dir / "app.exe")), \
                    mock.patch.object(sys, "platform", "win32"), \
                    mock.patch.dict(os.environ, {"APPDATA": str(appdata)}, clear=False):
                tags = load_tags()

            self.assertEqual(tags, existing)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), existing)

    def test_explicit_custom_path_still_creates_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom_path = Path(tmp) / "custom-tags.json"

            with mock.patch.object(sys, "frozen", True, create=True):
                self.assertEqual(load_tags(path=custom_path), {})

            self.assertEqual(json.loads(custom_path.read_text(encoding="utf-8")), {})

    def test_tag_purchase_matches_case_insensitive_keyword(self):
        tags = {
            "Groceries": {"keywords": ["market"], "limit": 0},
            "Dining": {"keywords": ["cafe"], "limit": 0},
        }

        self.assertEqual(tag_purchase("CITY MARKET CENTRAL", tags), "Groceries")
        self.assertEqual(tag_purchase("Unknown merchant", tags), "N/A")


if __name__ == "__main__":
    unittest.main()
