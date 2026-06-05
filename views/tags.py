import sys
import tkinter as tk

import customtkinter as ctk

from money import parse_amount
from tag_store import (
    BUDGET_PERIODS,
    BUDGET_TYPES,
    DEFAULT_PARENT_CATEGORY,
    EXPENSE_NATURES,
    FINANCIAL_PURPOSES,
    default_tag_info,
)


BUDGET_TYPE_LABELS = {
    "Expense": "Gasto",
    "Savings": "Ahorro",
    "Debt": "Deuda",
    "Donation": "Donación",
    "Investment": "Inversión",
    "Income": "Ingreso",
}
BUDGET_TYPE_VALUES = {label: value for value, label in BUDGET_TYPE_LABELS.items()}
BUDGET_PERIOD_LABELS = {
    "monthly": "Mensual",
    "annual": "Anual",
    "weekly": "Semanal",
    "one-time": "Único",
}
BUDGET_PERIOD_VALUES = {label: value for value, label in BUDGET_PERIOD_LABELS.items()}
EXPENSE_NATURE_LABELS = {
    "fixed": "Fijo",
    "variable": "Variable",
}
EXPENSE_NATURE_VALUES = {label: value for value, label in EXPENSE_NATURE_LABELS.items()}
UNCLASSIFIED_LABEL = "Sin clasificar"
TAG_COLLECTION_PANEL_WIDTH = 330
TAG_COLLECTION_LISTBOX_WIDTH = 32
TAG_COLLECTION_LISTBOX_HEIGHT = 18


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
        "Etiquetas",
        "Administra nombres, palabras clave y datos de presupuesto.",
    )

    content = ctk.CTkFrame(self.workspace, fg_color="transparent")
    content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
    content.grid_columnconfigure(0, weight=0, minsize=TAG_COLLECTION_PANEL_WIDTH)
    content.grid_columnconfigure(1, weight=1)
    content.grid_rowconfigure(0, weight=1)

    left_panel = self._panel(content, row=0, column=0, sticky="nsew", padx=(0, 12))
    left_panel.grid_columnconfigure(0, weight=1)
    left_panel.grid_rowconfigure(0, weight=1)

    self.tags_tabview = ctk.CTkTabview(left_panel, command=self.on_tags_tab_changed)
    self.tags_tabview.grid(row=0, column=0, sticky="nsew", padx=14, pady=(12, 10))
    tags_tab = self.tags_tabview.add("Etiquetas")
    categories_tab = self.tags_tabview.add("Categorías")

    tags_tab.grid_columnconfigure(0, weight=1)
    tags_tab.grid_rowconfigure(1, weight=1)
    ctk.CTkLabel(
        tags_tab,
        text="Lista de etiquetas",
        text_color="#171a20",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 8))
    self.tag_listbox = tk.Listbox(
        tags_tab,
        exportselection=False,
        bg="white",
        bd=0,
        relief="flat",
        width=TAG_COLLECTION_LISTBOX_WIDTH,
        height=TAG_COLLECTION_LISTBOX_HEIGHT,
    )
    self.tag_listbox.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 10))
    self.tag_listbox.bind("<<ListboxSelect>>", self.load_tag_details)

    categories_tab.grid_columnconfigure(0, weight=1)
    categories_tab.grid_rowconfigure(1, weight=1)
    ctk.CTkLabel(
        categories_tab,
        text="Categorías padre",
        text_color="#171a20",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 8))
    self.parent_category_listbox = tk.Listbox(
        categories_tab,
        exportselection=False,
        bg="white",
        bd=0,
        relief="flat",
        width=TAG_COLLECTION_LISTBOX_WIDTH,
        height=TAG_COLLECTION_LISTBOX_HEIGHT,
    )
    self.parent_category_listbox.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 10))
    self.parent_category_listbox.bind("<<ListboxSelect>>", self.on_parent_category_selected)

    json_buttons = ctk.CTkFrame(left_panel, fg_color="transparent")
    json_buttons.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
    for index in range(2):
        json_buttons.grid_columnconfigure(index, weight=1)
    ctk.CTkButton(json_buttons, text="Importar JSON", command=self.import_tags_json).grid(
        row=0, column=0, sticky="ew", padx=(0, 6)
    )
    ctk.CTkButton(json_buttons, text="Exportar JSON", command=self.export_tags_json).grid(
        row=0, column=1, sticky="ew"
    )

    right_panel = self._panel(content, row=0, column=1, sticky="nsew")
    right_panel.grid_columnconfigure(0, weight=1)
    right_panel.grid_rowconfigure(5, weight=1)
    self.tag_detail_title = ctk.CTkLabel(
        right_panel,
        text="Etiqueta seleccionada",
        text_color="#171a20",
        font=ctk.CTkFont(size=14, weight="bold"),
    )
    self.tag_detail_title.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 8))

    self.tag_name_var = tk.StringVar(value="")
    self.selected_category_var = tk.StringVar(value="Selecciona una categoría")
    self.tag_management_label = ctk.CTkLabel(
        right_panel,
        text="Gestionar etiqueta",
        text_color="#6b7280",
        font=ctk.CTkFont(size=11),
    )
    self.tag_management_label.grid(row=1, column=0, sticky="w", padx=14)
    self.tag_actions_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
    self.tag_actions_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 10))
    self.tag_actions_frame.grid_columnconfigure(0, weight=1)
    self.tag_name_entry = ctk.CTkEntry(self.tag_actions_frame, textvariable=self.tag_name_var)
    self.tag_name_entry.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
    for index in range(3):
        self.tag_actions_frame.grid_columnconfigure(index, weight=1)
    ctk.CTkButton(self.tag_actions_frame, text="Agregar nuevo", command=self.add_tag).grid(
        row=1, column=0, sticky="ew", padx=(0, 6)
    )
    ctk.CTkButton(self.tag_actions_frame, text="Editar", command=self.edit_tag).grid(
        row=1, column=1, sticky="ew", padx=(0, 6)
    )
    ctk.CTkButton(self.tag_actions_frame, text="Eliminar", command=self.remove_tag, fg_color="#dc2626").grid(
        row=1, column=2, sticky="ew"
    )

    self.category_management_label = ctk.CTkLabel(
        right_panel,
        text="Gestionar categoría",
        text_color="#6b7280",
        font=ctk.CTkFont(size=11),
    )
    self.category_management_label.grid(row=1, column=0, sticky="w", padx=14)
    self.category_actions_section = ctk.CTkFrame(right_panel, fg_color="transparent")
    self.category_actions_section.grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 10))
    self.category_actions_section.grid_columnconfigure(0, weight=1)
    self.selected_category_label = ctk.CTkEntry(
        self.category_actions_section,
        textvariable=self.selected_category_var,
    )
    self.selected_category_label.grid(row=0, column=0, sticky="ew", pady=(0, 6))
    category_buttons = ctk.CTkFrame(self.category_actions_section, fg_color="transparent")
    category_buttons.grid(row=1, column=0, sticky="ew")
    for index in range(3):
        category_buttons.grid_columnconfigure(index, weight=1)
    ctk.CTkButton(category_buttons, text="Agregar nuevo", command=self.add_parent_category).grid(
        row=0, column=0, sticky="ew", padx=(0, 6)
    )
    ctk.CTkButton(category_buttons, text="Editar", command=self.rename_parent_category).grid(
        row=0, column=1, sticky="ew", padx=(0, 6)
    )
    ctk.CTkButton(
        category_buttons,
        text="Eliminar",
        command=self.remove_parent_category,
        fg_color="#dc2626",
    ).grid(row=0, column=2, sticky="ew")

    self.tag_form = ctk.CTkFrame(right_panel, fg_color="transparent")
    self.tag_form.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 10))
    self.tag_form.grid_columnconfigure(0, weight=1)
    self.tag_form.grid_columnconfigure(1, weight=1)

    self.limit_var = tk.StringVar(value="")
    self.budget_type_var = tk.StringVar(value=BUDGET_TYPE_LABELS["Expense"])
    self.parent_category_var = tk.StringVar(value="")
    self.budget_period_var = tk.StringVar(value=BUDGET_PERIOD_LABELS["monthly"])
    self.expense_nature_var = tk.StringVar(value=UNCLASSIFIED_LABEL)
    self.financial_purpose_var = tk.StringVar(value=UNCLASSIFIED_LABEL)

    _form_label(self.tag_form, "Tipo de presupuesto", 0, 0)
    self.budget_type_menu = ctk.CTkOptionMenu(
        self.tag_form,
        variable=self.budget_type_var,
        values=[BUDGET_TYPE_LABELS[value] for value in BUDGET_TYPES],
    )
    self.budget_type_menu.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(2, 8))

    _form_label(self.tag_form, "Periodo", 0, 1)
    self.budget_period_menu = ctk.CTkOptionMenu(
        self.tag_form,
        variable=self.budget_period_var,
        values=[BUDGET_PERIOD_LABELS[value] for value in BUDGET_PERIODS],
    )
    self.budget_period_menu.grid(row=1, column=1, sticky="ew", pady=(2, 8))

    _form_label(self.tag_form, "Categoría padre", 2, 0)
    self.parent_category_menu = ctk.CTkComboBox(
        self.tag_form,
        variable=self.parent_category_var,
        values=_metadata_options(self.tags, "parent_category"),
    )
    self.parent_category_menu.grid(
        row=3, column=0, columnspan=2, sticky="ew", pady=(2, 8)
    )
    _form_label(self.tag_form, "Monto planificado", 4, 0)
    self.planned_amount_entry = ctk.CTkEntry(self.tag_form, textvariable=self.limit_var)
    self.planned_amount_entry.grid(
        row=5, column=0, sticky="ew", padx=(0, 8), pady=(2, 8)
    )
    _form_label(self.tag_form, "Naturaleza del gasto", 4, 1)
    self.expense_nature_menu = ctk.CTkOptionMenu(
        self.tag_form,
        variable=self.expense_nature_var,
        values=[UNCLASSIFIED_LABEL] + [EXPENSE_NATURE_LABELS[value] for value in EXPENSE_NATURES],
    )
    self.expense_nature_menu.grid(row=5, column=1, sticky="ew", pady=(2, 8))

    _form_label(self.tag_form, "Propósito financiero", 6, 0)
    self.financial_purpose_menu = ctk.CTkOptionMenu(
        self.tag_form,
        variable=self.financial_purpose_var,
        values=[UNCLASSIFIED_LABEL] + list(FINANCIAL_PURPOSES),
    )
    self.financial_purpose_menu.grid(row=7, column=0, sticky="ew", padx=(0, 8), pady=(2, 0))

    self.keyword_label = ctk.CTkLabel(
        right_panel,
        text="Palabras clave",
        text_color="#6b7280",
        font=ctk.CTkFont(size=11),
    )
    self.keyword_label.grid(row=4, column=0, sticky="w", padx=14)
    self.keyword_listbox = tk.Listbox(right_panel, exportselection=False, bg="white", bd=0, relief="flat")
    self.keyword_listbox.grid(row=5, column=0, sticky="nsew", padx=14, pady=(2, 10))

    self.keyword_buttons_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
    self.keyword_buttons_frame.grid(row=6, column=0, sticky="ew", padx=14, pady=(0, 14))
    for index in range(4):
        self.keyword_buttons_frame.grid_columnconfigure(index, weight=1)
    self.add_keyword_button = ctk.CTkButton(self.keyword_buttons_frame, text="Agregar palabra", command=self.add_keyword)
    self.add_keyword_button.grid(
        row=0, column=0, sticky="ew", padx=(0, 6)
    )
    self.edit_keyword_button = ctk.CTkButton(self.keyword_buttons_frame, text="Editar", command=self.edit_keyword)
    self.edit_keyword_button.grid(
        row=0, column=1, sticky="ew", padx=(0, 6)
    )
    self.remove_keyword_button = ctk.CTkButton(
        self.keyword_buttons_frame, text="Eliminar", command=self.remove_keyword, fg_color="#dc2626"
    )
    self.remove_keyword_button.grid(
        row=0, column=2, sticky="ew", padx=(0, 6)
    )
    self.save_tag_details_button = ctk.CTkButton(
        self.keyword_buttons_frame, text="Guardar", command=self.save_tags_from_view, fg_color="#16a34a"
    )
    self.save_tag_details_button.grid(
        row=0, column=3, sticky="ew"
    )
    self.tag_detail_widgets = [
        self.tag_name_entry,
        self.budget_type_menu,
        self.budget_period_menu,
        self.parent_category_menu,
        self.planned_amount_entry,
        self.expense_nature_menu,
        self.financial_purpose_menu,
        self.keyword_listbox,
        self.add_keyword_button,
        self.edit_keyword_button,
        self.remove_keyword_button,
        self.save_tag_details_button,
    ]

    self.refresh_tag_lists()
    _refresh_tags_workspace_mode(self)


def open_tag_editor(self):
    self.show_view("Tags")


def on_tags_tab_changed(self):
    _refresh_tags_workspace_mode(self)


def _active_tags_tab(self):
    tabview = self.__dict__.get("tags_tabview")
    if tabview is None or not hasattr(tabview, "get"):
        return "Etiquetas"
    return tabview.get()


def _refresh_tags_workspace_mode(self):
    if "tag_detail_title" not in self.__dict__:
        return
    if _active_tags_tab(self) == "Categorías":
        self.tag_detail_title.configure(text="Categoría seleccionada")
        selected_category = _selected_parent_category(self)
        if "selected_category_var" in self.__dict__:
            self.selected_category_var.set(selected_category or "Selecciona una categoría")
        _set_category_details_enabled(self, bool(selected_category))
        _hide_widgets(
            self.__dict__.get(name)
            for name in (
                "tag_management_label",
                "tag_actions_frame",
                "tag_form",
                "keyword_label",
                "keyword_listbox",
                "keyword_buttons_frame",
            )
        )
        _show_widgets(
            self.__dict__.get(name)
            for name in (
                "selected_category_label",
                "category_management_label",
                "category_actions_section",
            )
        )
        return
    self.tag_detail_title.configure(text="Etiqueta seleccionada")
    _set_category_details_enabled(self, False)
    _hide_widgets(
        self.__dict__.get(name)
        for name in (
            "selected_category_label",
            "category_management_label",
            "category_actions_section",
        )
    )
    _show_widgets(
        self.__dict__.get(name)
        for name in (
            "tag_management_label",
            "tag_actions_frame",
            "tag_form",
            "keyword_label",
            "keyword_listbox",
            "keyword_buttons_frame",
        )
    )


def _show_widgets(widgets):
    for widget in widgets:
        if widget is not None and hasattr(widget, "grid"):
            widget.grid()


def _hide_widgets(widgets):
    for widget in widgets:
        if widget is not None and hasattr(widget, "grid_remove"):
            widget.grid_remove()


def _form_label(parent, text, row, column):
    ctk.CTkLabel(parent, text=text, text_color="#6b7280", font=ctk.CTkFont(size=11)).grid(
        row=row, column=column, sticky="w", padx=(0, 8) if column == 0 else 0
    )


def refresh_tag_lists(self):
    if "tag_listbox" not in self.__dict__:
        return
    self.tag_listbox.delete(0, "end")
    for tag in sorted(self.tags):
        self.tag_listbox.insert("end", tag)
    _refresh_parent_category_list(self)
    if "selected_category_var" in self.__dict__:
        self.selected_category_var.set("Selecciona una categoría")
    _set_category_details_enabled(self, False)
    _clear_tag_details(self)
    _set_tag_details_enabled(self, False)


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
        _clear_tag_details(self)
        _set_tag_details_enabled(self, False)
        return False
    previous_tag = self.__dict__.get("current_tag_name")
    if previous_tag and previous_tag != tag and not self.save_current_tag_limit(previous_tag):
        self._set_tag_selection(previous_tag)
        return False
    _clear_parent_category_selection(self)
    if "keyword_listbox" in self.__dict__:
        _configure_widget_state(self.keyword_listbox, "normal")
        self.keyword_listbox.delete(0, "end")
        for keyword in self.tags[tag].get("keywords", []):
            self.keyword_listbox.insert("end", keyword)
    if "limit_var" in self.__dict__:
        self.limit_var.set(str(self.tags[tag].get("planned_amount", self.tags[tag].get("limit", 0))))
    if "tag_name_var" in self.__dict__:
        self.tag_name_var.set(tag)
    _load_tag_metadata_vars(self, tag)
    _refresh_metadata_option_values(self)
    self.current_tag_name = tag
    _set_tag_details_enabled(self, True)
    return True


def on_parent_category_selected(self, event=None):
    category = _selected_parent_category(self)
    if "selected_category_var" in self.__dict__:
        self.selected_category_var.set(category or "Selecciona una categoría")
    _set_category_details_enabled(self, bool(category))
    _refresh_tags_workspace_mode(self)
    tag = self.__dict__.get("current_tag_name") or self.selected_tag_name()
    if _active_tags_tab(self) == "Categorías":
        if "tag_listbox" in self.__dict__ and hasattr(self.tag_listbox, "selection_clear"):
            self.tag_listbox.selection_clear(0, "end")
        _clear_tag_details(self)
        _set_tag_details_enabled(self, False)
        return True
    if not category or not tag:
        return True
    if not self.save_current_tag_limit(tag):
        self._set_tag_selection(tag)
        _set_tag_details_enabled(self, True)
        return False
    _set_parent_category_selection(self, category)
    if "tag_listbox" in self.__dict__ and hasattr(self.tag_listbox, "selection_clear"):
        self.tag_listbox.selection_clear(0, "end")
    _clear_tag_details(self)
    _set_tag_details_enabled(self, False)
    return True


def _parse_limit_value(self, value):
    return parse_amount(value)


def save_current_tag_limit(self, tag_name=None):
    tag = tag_name or self.selected_tag_name()
    if not tag or tag not in self.tags or "limit_var" not in self.__dict__:
        return True
    try:
        planned_amount = self._parse_limit_value(self.limit_var.get())
    except ValueError:
        _app_dependencies().messagebox.showwarning("Monto inválido", "El monto planificado debe ser un número.")
        return False
    if not _valid_parent_category_from_view(self, tag):
        _app_dependencies().messagebox.showwarning(
            "Categoría inválida",
            "La categoría padre debe ser diferente del tag.",
        )
        return False
    self.tags[tag]["limit"] = planned_amount
    self.tags[tag]["planned_amount"] = planned_amount
    _save_tag_metadata_vars(self, tag)
    _refresh_metadata_option_values(self)
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
        f"Se importaron {_count_phrase(counts['tags_added'], 'etiqueta')}, "
        f"{_count_phrase(counts['keywords_added'], 'palabra clave', 'palabras clave')}, "
        f"se actualizaron {_count_phrase(counts['limits_updated'], 'monto')} "
        f"y {_count_phrase(counts.get('metadata_updated', 0), 'dato')}"
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
        _refresh_metadata_option_values(self)
        self._refresh_tag_filter_options()
        app.messagebox.showinfo(
            "Importado",
            "Etiquetas importadas desde JSON.\n"
            f"Etiquetas agregadas: {counts['tags_added']}\n"
            f"Palabras clave agregadas: {counts['keywords_added']}\n"
            f"Montos actualizados: {counts['limits_updated']}\n"
            f"Datos actualizados: {counts.get('metadata_updated', 0)}",
        )
        self._set_status(_import_status_message(counts))
    except Exception as exc:
        app.messagebox.showerror("Error de importación", str(exc))
        self._set_status("No se pudo importar")


def export_tags_json(self):
    if not self.save_current_tag_limit():
        return
    app = _app_dependencies()
    path = app.filedialog.asksaveasfilename(
        defaultextension=".json",
        initialfile="etiquetas.json",
        filetypes=[("JSON", "*.json"), ("All files", "*.*")],
    )
    if not path:
        return
    try:
        app.save_tags(self.tags, path)
        app.messagebox.showinfo("Exportado", f"Etiquetas exportadas a {path}")
        self._set_status(f"Etiquetas exportadas a {path}")
    except Exception as exc:
        app.messagebox.showerror("Error de exportación", str(exc))
        self._set_status("No se pudo exportar")


def add_tag(self):
    if not self.save_current_tag_limit():
        return
    app = _app_dependencies()
    name = app.simple_input(self, "Nueva etiqueta", "Nombre de la etiqueta:")
    if not name or name in self.tags:
        return
    self.tags[name] = default_tag_info(name)
    app.save_tags(self.tags)
    self.refresh_tag_lists()
    _refresh_metadata_option_values(self)
    self._select_tag_in_list(name)
    self._refresh_tag_filter_options()
    self._set_status(f'Se agregó la etiqueta "{name}"')


def edit_tag(self):
    old = self.selected_tag_name()
    if not old:
        return
    if not self.save_current_tag_limit(old):
        return
    app = _app_dependencies()
    if "tag_name_var" in self.__dict__:
        new = self.tag_name_var.get().strip()
    else:
        new = app.simple_input(self, "Editar etiqueta", f'Nuevo nombre para "{old}":', default=old)
    if not new or new == old or new in self.tags:
        return
    self.tags[new] = self.tags.pop(old)
    for row in self.__dict__.get("all_rows", []):
        if row[4] == old:
            row[4] = new
    app.save_tags(self.tags)
    self.refresh_tag_lists()
    _refresh_metadata_option_values(self)
    self._select_tag_in_list(new)
    self._refresh_tag_filter_options()
    self._set_status(f'Se renombró "{old}" a "{new}"')


def remove_tag(self):
    tag = self.selected_tag_name()
    if not tag:
        return
    if not self.save_current_tag_limit(tag):
        return
    app = _app_dependencies()
    if not app.messagebox.askyesno("Confirmar", f'¿Eliminar la etiqueta "{tag}"?'):
        return
    del self.tags[tag]
    for row in self.__dict__.get("all_rows", []):
        if row[4] == tag:
            row[4] = self.natag
    app.save_tags(self.tags)
    self.refresh_tag_lists()
    _refresh_metadata_option_values(self)
    if "all_rows" in self.__dict__:
        self.apply_filter()
    else:
        self._refresh_tag_filter_options()
    self._set_status(f'Se eliminó la etiqueta "{tag}"')


def add_parent_category(self):
    if not self.save_current_tag_limit():
        return
    tag = self.selected_tag_name()
    app = _app_dependencies()
    if not tag:
        app.messagebox.showwarning("Etiqueta requerida", "Selecciona una etiqueta para asignar la categoría.")
        return
    category = app.simple_input(self, "Nueva categoría padre", "Nombre de la categoría padre:")
    category = str(category or "").strip()
    if not category:
        return
    if category.casefold() == DEFAULT_PARENT_CATEGORY.casefold():
        app.messagebox.showwarning("Categoría inválida", "La categoría ya existe.")
        return
    if any(category.casefold() == option.casefold() for option in _parent_category_options(self.tags)):
        app.messagebox.showwarning("Categoría inválida", "La categoría ya existe.")
        return
    if category.casefold() == tag.casefold():
        app.messagebox.showwarning("Categoría inválida", "La categoría padre debe ser diferente del tag.")
        return
    self.tags[tag]["parent_category"] = category
    app.save_tags(self.tags)
    _load_tag_metadata_vars(self, tag)
    _refresh_metadata_option_values(self)
    _set_parent_category_selection(self, category)
    if "selected_category_var" in self.__dict__:
        self.selected_category_var.set(category)
    _set_category_details_enabled(self, True)
    self._refresh_tag_filter_options()
    self._set_status(f'Se agregó la categoría "{category}"')


def rename_parent_category(self):
    if not self.save_current_tag_limit():
        return
    old = _selected_parent_category(self)
    if not old:
        return
    app = _app_dependencies()
    if old.casefold() == DEFAULT_PARENT_CATEGORY.casefold():
        app.messagebox.showwarning("Categoría protegida", f'No se puede renombrar "{DEFAULT_PARENT_CATEGORY}".')
        return
    if "selected_category_label" in self.__dict__:
        new = self.selected_category_var.get()
    else:
        new = app.simple_input(self, "Renombrar categoría padre", f'Nuevo nombre para "{old}":', default=old)
    new = str(new or "").strip()
    if not new or new.casefold() == old.casefold():
        return
    existing = _parent_category_options(self.tags)
    if any(new.casefold() == option.casefold() for option in existing):
        app.messagebox.showwarning("Categoría inválida", "La categoría ya existe.")
        return
    for tag, info in self.tags.items():
        if _parent_category_matches(info, old) and new.casefold() == tag.casefold():
            app.messagebox.showwarning("Categoría inválida", "La categoría padre debe ser diferente del tag.")
            return
    _rename_parent_category(self, old, new)
    app.save_tags(self.tags)
    if "parent_category_var" in self.__dict__ and self.parent_category_var.get().casefold() == old.casefold():
        self.parent_category_var.set(new)
    _refresh_metadata_option_values(self)
    _set_parent_category_selection(self, new)
    if "selected_category_var" in self.__dict__:
        self.selected_category_var.set(new)
    _set_category_details_enabled(self, True)
    self._refresh_tag_filter_options()
    self._set_status(f'Se renombró la categoría "{old}" a "{new}"')


def remove_parent_category(self):
    if not self.save_current_tag_limit():
        return
    category = _selected_parent_category(self)
    if not category:
        return
    app = _app_dependencies()
    if category.casefold() == DEFAULT_PARENT_CATEGORY.casefold():
        app.messagebox.showwarning("Categoría protegida", f'No se puede eliminar "{DEFAULT_PARENT_CATEGORY}".')
        return
    affected = _tags_for_parent_category(self.tags, category)
    if affected:
        count = len(affected)
        word = "etiqueta" if count == 1 else "etiquetas"
        if not app.messagebox.askyesno(
            "Confirmar",
            f'La categoría "{category}" está en uso por {count} {word}. '
            f"Si continúas, quedarán en {DEFAULT_PARENT_CATEGORY}. ¿Deseas continuar?",
        ):
            return
    _delete_parent_category(self, category)
    app.save_tags(self.tags)
    if "parent_category_var" in self.__dict__ and self.parent_category_var.get().casefold() == category.casefold():
        self.parent_category_var.set(DEFAULT_PARENT_CATEGORY)
    _refresh_metadata_option_values(self)
    if "selected_category_var" in self.__dict__:
        self.selected_category_var.set("Selecciona una categoría")
    _set_category_details_enabled(self, False)
    self._refresh_tag_filter_options()
    self._set_status(f'Se eliminó la categoría "{category}"')


def add_keyword(self):
    tag = self.selected_tag_name()
    if not tag:
        return
    app = _app_dependencies()
    keyword = app.simple_input(self, "Nueva palabra clave", "Palabra clave:")
    if not keyword:
        return
    self.tags[tag].setdefault("keywords", []).append(keyword)
    app.save_tags(self.tags)
    self.load_tag_details()
    self._set_status(f'Se agregó una palabra clave a "{tag}"')


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
    new = app.simple_input(self, "Editar palabra clave", f'Nuevo valor para "{old}":', default=old)
    if not new or new == old:
        return
    self.tags[tag]["keywords"][index] = new
    app.save_tags(self.tags)
    self.load_tag_details()
    self.keyword_listbox.selection_set(index)
    self._set_status(f'Se actualizó una palabra clave de "{tag}"')


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
    if not app.messagebox.askyesno("Confirmar", f'¿Eliminar la palabra clave "{keyword}"?'):
        return
    del self.tags[tag]["keywords"][index]
    app.save_tags(self.tags)
    self.load_tag_details()
    self._set_status(f'Se eliminó una palabra clave de "{tag}"')


def save_tags_from_view(self):
    if not self.save_current_tag_limit():
        return
    app = _app_dependencies()
    app.save_tags(self.tags)
    _refresh_metadata_option_values(self)
    self._refresh_tag_filter_options()
    self._set_status("Etiquetas guardadas")


def _clear_tag_details(self):
    if "keyword_listbox" in self.__dict__:
        _configure_widget_state(self.keyword_listbox, "normal")
        self.keyword_listbox.delete(0, "end")
    if "limit_var" in self.__dict__:
        self.limit_var.set("")
    if "tag_name_var" in self.__dict__:
        self.tag_name_var.set("")
    for name in (
        "budget_type_var",
        "parent_category_var",
        "budget_period_var",
        "expense_nature_var",
        "financial_purpose_var",
    ):
        if name in self.__dict__:
            getattr(self, name).set(_empty_metadata_value(name))
    self.current_tag_name = None


def _set_tag_details_enabled(self, enabled):
    state = "normal" if enabled else "disabled"
    for widget in self.__dict__.get("tag_detail_widgets", ()):
        _configure_widget_state(widget, state)


def _set_category_details_enabled(self, enabled):
    state = "normal" if enabled else "disabled"
    _configure_widget_state(self.__dict__.get("selected_category_label"), state)


def _configure_widget_state(widget, state):
    if widget is not None and hasattr(widget, "configure"):
        widget.configure(state=state)


def _clear_parent_category_selection(self):
    listbox = self.__dict__.get("parent_category_listbox")
    if listbox is not None and hasattr(listbox, "selection_clear"):
        listbox.selection_clear(0, "end")


def _set_parent_category_selection(self, category):
    listbox = self.__dict__.get("parent_category_listbox")
    if listbox is None or not hasattr(listbox, "selection_set"):
        return
    for index, option in enumerate(_parent_category_options(self.tags)):
        if option.casefold() == category.casefold():
            if hasattr(listbox, "selection_clear"):
                listbox.selection_clear(0, "end")
            listbox.selection_set(index)
            return


def _empty_metadata_value(var_name):
    defaults = {
        "budget_type_var": BUDGET_TYPE_LABELS["Expense"],
        "parent_category_var": DEFAULT_PARENT_CATEGORY,
        "budget_period_var": BUDGET_PERIOD_LABELS["monthly"],
        "expense_nature_var": UNCLASSIFIED_LABEL,
        "financial_purpose_var": UNCLASSIFIED_LABEL,
    }
    return defaults[var_name]


def _metadata_options(tags, field):
    return sorted({
        str(info.get(field, "")).strip()
        for info in tags.values()
        if isinstance(info, dict) and str(info.get(field, "")).strip()
    })


def _parent_category_options(tags, include_default=True):
    categories = set()
    if include_default:
        categories.add(DEFAULT_PARENT_CATEGORY)
    for tag, info in tags.items():
        if not isinstance(info, dict):
            continue
        categories.add(_normalized_parent_category_value(info.get("parent_category"), tag))
    return sorted(categories)


def _refresh_parent_category_list(self):
    if "parent_category_listbox" not in self.__dict__:
        return
    self.parent_category_listbox.delete(0, "end")
    for category in _parent_category_options(self.tags):
        self.parent_category_listbox.insert("end", category)


def _selected_parent_category(self):
    if "parent_category_listbox" not in self.__dict__:
        return None
    selection = self.parent_category_listbox.curselection()
    if not selection:
        return None
    return self.parent_category_listbox.get(selection[0])


def _parent_category_matches(info, category):
    return str(info.get("parent_category", DEFAULT_PARENT_CATEGORY)).strip().casefold() == category.casefold()


def _tags_for_parent_category(tags, category):
    return [tag for tag, info in tags.items() if isinstance(info, dict) and _parent_category_matches(info, category)]


def _rename_parent_category(self, old, new):
    for info in self.tags.values():
        if isinstance(info, dict) and _parent_category_matches(info, old):
            info["parent_category"] = new


def _delete_parent_category(self, category):
    for info in self.tags.values():
        if isinstance(info, dict) and _parent_category_matches(info, category):
            info["parent_category"] = DEFAULT_PARENT_CATEGORY


def _refresh_metadata_option_values(self):
    menu_fields = (
        ("parent_category_menu", "parent_category"),
    )
    for menu_name, field in menu_fields:
        menu = self.__dict__.get(menu_name)
        if menu is not None and hasattr(menu, "configure"):
            menu.configure(values=_metadata_options(self.tags, field))
    _refresh_parent_category_list(self)


def _load_tag_metadata_vars(self, tag):
    info = self.tags[tag]
    if "budget_type_var" in self.__dict__:
        self.budget_type_var.set(BUDGET_TYPE_LABELS.get(info.get("budget_type", "Expense"), BUDGET_TYPE_LABELS["Expense"]))
    if "parent_category_var" in self.__dict__:
        self.parent_category_var.set(_normalized_parent_category_value(info.get("parent_category"), tag))
    if "budget_period_var" in self.__dict__:
        self.budget_period_var.set(BUDGET_PERIOD_LABELS.get(info.get("budget_period", "monthly"), BUDGET_PERIOD_LABELS["monthly"]))
    if "expense_nature_var" in self.__dict__:
        nature = info.get("expense_nature")
        self.expense_nature_var.set(EXPENSE_NATURE_LABELS.get(nature, UNCLASSIFIED_LABEL))
    if "financial_purpose_var" in self.__dict__:
        self.financial_purpose_var.set(info.get("financial_purpose") or UNCLASSIFIED_LABEL)


def _save_tag_metadata_vars(self, tag):
    info = self.tags[tag]
    if "budget_type_var" in self.__dict__:
        info["budget_type"] = BUDGET_TYPE_VALUES.get(self.budget_type_var.get(), "Expense")
    if "parent_category_var" in self.__dict__:
        info["parent_category"] = _normalized_parent_category_value(self.parent_category_var.get(), tag)
    if "budget_period_var" in self.__dict__:
        info["budget_period"] = BUDGET_PERIOD_VALUES.get(self.budget_period_var.get(), "monthly")
    if "expense_nature_var" in self.__dict__:
        info["expense_nature"] = EXPENSE_NATURE_VALUES.get(self.expense_nature_var.get())
    if "financial_purpose_var" in self.__dict__:
        value = self.financial_purpose_var.get()
        info["financial_purpose"] = None if value == UNCLASSIFIED_LABEL else value


def _normalized_parent_category_value(value, tag):
    parent_category = str(value or "").strip()
    if not parent_category:
        return DEFAULT_PARENT_CATEGORY
    if parent_category.casefold() == tag.casefold():
        return DEFAULT_PARENT_CATEGORY
    return parent_category


def _valid_parent_category_from_view(self, tag):
    if "parent_category_var" not in self.__dict__:
        return True
    parent_category = self.parent_category_var.get().strip()
    return not parent_category or parent_category.casefold() != tag.casefold()
