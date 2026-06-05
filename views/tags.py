import sys
import tkinter as tk

import customtkinter as ctk

from money import parse_amount


def _app_dependencies():
    app_module = sys.modules.get("purchase_tagger_app") or sys.modules.get("__main__")
    if app_module is None:
        import purchase_tagger_app

        app_module = purchase_tagger_app
    return app_module


def _build_tags_view(self):
    self.workspace.grid_rowconfigure(1, weight=1)
    self._build_page_header(
        self.workspace,
        "Tags",
        "Manage tag names, keyword matching, and monthly limits.",
    )

    content = ctk.CTkFrame(self.workspace, fg_color="transparent")
    content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
    content.grid_columnconfigure(0, weight=1)
    content.grid_columnconfigure(1, weight=2)
    content.grid_rowconfigure(0, weight=1)

    left_panel = self._panel(content, row=0, column=0, sticky="nsew", padx=(0, 12))
    left_panel.grid_columnconfigure(0, weight=1)
    left_panel.grid_rowconfigure(1, weight=1)
    ctk.CTkLabel(
        left_panel,
        text="Tag List",
        text_color="#171a20",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 8))
    self.tag_listbox = tk.Listbox(left_panel, exportselection=False, bg="white", bd=0, relief="flat")
    self.tag_listbox.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 10))
    self.tag_listbox.bind("<<ListboxSelect>>", self.load_tag_details)

    tag_buttons = ctk.CTkFrame(left_panel, fg_color="transparent")
    tag_buttons.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
    for index in range(3):
        tag_buttons.grid_columnconfigure(index, weight=1)
    ctk.CTkButton(tag_buttons, text="Add", command=self.add_tag).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(tag_buttons, text="Edit", command=self.edit_tag).grid(row=0, column=1, sticky="ew", padx=(0, 6))
    ctk.CTkButton(tag_buttons, text="Remove", command=self.remove_tag, fg_color="#dc2626").grid(
        row=0, column=2, sticky="ew"
    )

    json_buttons = ctk.CTkFrame(left_panel, fg_color="transparent")
    json_buttons.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 14))
    for index in range(2):
        json_buttons.grid_columnconfigure(index, weight=1)
    ctk.CTkButton(json_buttons, text="Import JSON", command=self.import_tags_json).grid(
        row=0, column=0, sticky="ew", padx=(0, 6)
    )
    ctk.CTkButton(json_buttons, text="Export JSON", command=self.export_tags_json).grid(
        row=0, column=1, sticky="ew"
    )

    right_panel = self._panel(content, row=0, column=1, sticky="nsew")
    right_panel.grid_columnconfigure(0, weight=1)
    right_panel.grid_rowconfigure(3, weight=1)
    ctk.CTkLabel(
        right_panel,
        text="Selected Tag",
        text_color="#171a20",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 8))
    ctk.CTkLabel(right_panel, text="Monthly Limit", text_color="#6b7280", font=ctk.CTkFont(size=11)).grid(
        row=1, column=0, sticky="w", padx=14
    )
    self.limit_var = tk.StringVar(value="")
    ctk.CTkEntry(right_panel, textvariable=self.limit_var).grid(
        row=2, column=0, sticky="ew", padx=14, pady=(2, 10)
    )
    self.keyword_listbox = tk.Listbox(right_panel, exportselection=False, bg="white", bd=0, relief="flat")
    self.keyword_listbox.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 10))

    keyword_buttons = ctk.CTkFrame(right_panel, fg_color="transparent")
    keyword_buttons.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 14))
    for index in range(4):
        keyword_buttons.grid_columnconfigure(index, weight=1)
    ctk.CTkButton(keyword_buttons, text="Add Keyword", command=self.add_keyword).grid(
        row=0, column=0, sticky="ew", padx=(0, 6)
    )
    ctk.CTkButton(keyword_buttons, text="Edit", command=self.edit_keyword).grid(
        row=0, column=1, sticky="ew", padx=(0, 6)
    )
    ctk.CTkButton(keyword_buttons, text="Remove", command=self.remove_keyword, fg_color="#dc2626").grid(
        row=0, column=2, sticky="ew", padx=(0, 6)
    )
    ctk.CTkButton(keyword_buttons, text="Save", command=self.save_tags_from_view, fg_color="#16a34a").grid(
        row=0, column=3, sticky="ew"
    )

    self.refresh_tag_lists()


def open_tag_editor(self):
    self.show_view("Tags")


def refresh_tag_lists(self):
    if "tag_listbox" not in self.__dict__:
        return
    self.tag_listbox.delete(0, "end")
    for tag in sorted(self.tags):
        self.tag_listbox.insert("end", tag)
    if "keyword_listbox" in self.__dict__:
        self.keyword_listbox.delete(0, "end")
    if "limit_var" in self.__dict__:
        self.limit_var.set("")
    self.current_tag_name = None


def selected_tag_name(self):
    if "tag_listbox" not in self.__dict__:
        return None
    selection = self.tag_listbox.curselection()
    if not selection:
        return None
    return self.tag_listbox.get(selection[0])


def load_tag_details(self, event=None):
    tag = self.selected_tag_name()
    if not tag or tag not in self.tags:
        return False
    previous_tag = self.__dict__.get("current_tag_name")
    if previous_tag and previous_tag != tag and not self.save_current_tag_limit(previous_tag):
        self._set_tag_selection(previous_tag)
        return False
    if "keyword_listbox" in self.__dict__:
        self.keyword_listbox.delete(0, "end")
        for keyword in self.tags[tag].get("keywords", []):
            self.keyword_listbox.insert("end", keyword)
    if "limit_var" in self.__dict__:
        self.limit_var.set(str(self.tags[tag].get("limit", 0)))
    self.current_tag_name = tag
    return True


def _parse_limit_value(self, value):
    return parse_amount(value)


def save_current_tag_limit(self, tag_name=None):
    tag = tag_name or self.selected_tag_name()
    if not tag or tag not in self.tags or "limit_var" not in self.__dict__:
        return True
    try:
        limit = self._parse_limit_value(self.limit_var.get())
    except ValueError:
        _app_dependencies().messagebox.showwarning("Invalid Limit", "Monthly limit must be a number.")
        return False
    self.tags[tag]["limit"] = limit
    return True


def _set_status(self, message):
    if "status_var" in self.__dict__:
        self.status_var.set(message)


def _refresh_tag_filter_options(self):
    if all(name in self.__dict__ for name in ("all_rows", "tag_menu", "tag_filter_var")):
        self._refresh_filter_options()


def _set_tag_selection(self, tag):
    if "tag_listbox" not in self.__dict__ or tag not in self.tags:
        return
    index = sorted(self.tags).index(tag)
    if hasattr(self.tag_listbox, "selection_clear"):
        self.tag_listbox.selection_clear(0, "end")
    self.tag_listbox.selection_set(index)


def _select_tag_in_list(self, tag):
    self._set_tag_selection(tag)
    self.load_tag_details()


def _count_phrase(count, singular, plural=None):
    word = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {word}"


def _import_status_message(counts):
    return (
        f"Imported {_count_phrase(counts['tags_added'], 'tag')}, "
        f"{_count_phrase(counts['keywords_added'], 'keyword')}, "
        f"and updated {_count_phrase(counts['limits_updated'], 'limit')}"
    )


def import_tags_json(self):
    if not self.save_current_tag_limit():
        return
    app = _app_dependencies()
    path = app.filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All files", "*.*")])
    if not path:
        return
    try:
        imported_tags = app.load_tags(path)
        merged_tags, counts = app.merge_tags(self.tags, imported_tags)
        app.save_tags(merged_tags)
        self.tags = merged_tags
        self.refresh_tag_lists()
        self._refresh_tag_filter_options()
        app.messagebox.showinfo(
            "Imported",
            "Imported tags from JSON.\n"
            f"Tags added: {counts['tags_added']}\n"
            f"Keywords added: {counts['keywords_added']}\n"
            f"Limits updated: {counts['limits_updated']}",
        )
        self._set_status(_import_status_message(counts))
    except Exception as exc:
        app.messagebox.showerror("Import Error", str(exc))
        self._set_status("Import failed")


def export_tags_json(self):
    if not self.save_current_tag_limit():
        return
    app = _app_dependencies()
    path = app.filedialog.asksaveasfilename(
        defaultextension=".json",
        initialfile="tag_list.json",
        filetypes=[("JSON", "*.json"), ("All files", "*.*")],
    )
    if not path:
        return
    try:
        app.save_tags(self.tags, path)
        app.messagebox.showinfo("Exported", f"Exported tags to {path}")
        self._set_status(f"Exported tags to {path}")
    except Exception as exc:
        app.messagebox.showerror("Export Error", str(exc))
        self._set_status("Export failed")


def add_tag(self):
    if not self.save_current_tag_limit():
        return
    app = _app_dependencies()
    name = app.simple_input(self, "New Tag", "Tag name:")
    if not name or name in self.tags:
        return
    self.tags[name] = {"keywords": [], "limit": 0}
    app.save_tags(self.tags)
    self.refresh_tag_lists()
    self._select_tag_in_list(name)
    self._refresh_tag_filter_options()
    self._set_status(f'Added tag "{name}"')


def edit_tag(self):
    old = self.selected_tag_name()
    if not old:
        return
    if not self.save_current_tag_limit(old):
        return
    app = _app_dependencies()
    new = app.simple_input(self, "Edit Tag", f'New name for tag "{old}":', default=old)
    if not new or new == old or new in self.tags:
        return
    self.tags[new] = self.tags.pop(old)
    for row in self.__dict__.get("all_rows", []):
        if row[4] == old:
            row[4] = new
    app.save_tags(self.tags)
    self.refresh_tag_lists()
    self._select_tag_in_list(new)
    self._refresh_tag_filter_options()
    self._set_status(f'Renamed tag "{old}" to "{new}"')


def remove_tag(self):
    tag = self.selected_tag_name()
    if not tag:
        return
    if not self.save_current_tag_limit(tag):
        return
    app = _app_dependencies()
    if not app.messagebox.askyesno("Confirm", f'Remove tag "{tag}"?'):
        return
    del self.tags[tag]
    for row in self.__dict__.get("all_rows", []):
        if row[4] == tag:
            row[4] = self.natag
    app.save_tags(self.tags)
    self.refresh_tag_lists()
    if "all_rows" in self.__dict__:
        self.apply_filter()
    else:
        self._refresh_tag_filter_options()
    self._set_status(f'Removed tag "{tag}"')


def add_keyword(self):
    tag = self.selected_tag_name()
    if not tag:
        return
    app = _app_dependencies()
    keyword = app.simple_input(self, "New Keyword", "Keyword:")
    if not keyword:
        return
    self.tags[tag].setdefault("keywords", []).append(keyword)
    app.save_tags(self.tags)
    self.load_tag_details()
    self._set_status(f'Added keyword to "{tag}"')


def edit_keyword(self):
    tag = self.selected_tag_name()
    if not tag or "keyword_listbox" not in self.__dict__:
        return
    selection = self.keyword_listbox.curselection()
    if not selection:
        return
    index = selection[0]
    old = self.keyword_listbox.get(index)
    app = _app_dependencies()
    new = app.simple_input(self, "Edit Keyword", f'New value for keyword "{old}":', default=old)
    if not new or new == old:
        return
    self.tags[tag]["keywords"][index] = new
    app.save_tags(self.tags)
    self.load_tag_details()
    self.keyword_listbox.selection_set(index)
    self._set_status(f'Updated keyword for "{tag}"')


def remove_keyword(self):
    tag = self.selected_tag_name()
    if not tag or "keyword_listbox" not in self.__dict__:
        return
    selection = self.keyword_listbox.curselection()
    if not selection:
        return
    index = selection[0]
    keyword = self.keyword_listbox.get(index)
    app = _app_dependencies()
    if not app.messagebox.askyesno("Confirm", f'Remove keyword "{keyword}"?'):
        return
    del self.tags[tag]["keywords"][index]
    app.save_tags(self.tags)
    self.load_tag_details()
    self._set_status(f'Removed keyword from "{tag}"')


def save_tags_from_view(self):
    if not self.save_current_tag_limit():
        return
    app = _app_dependencies()
    app.save_tags(self.tags)
    self._refresh_tag_filter_options()
    self._set_status("Saved tags")
