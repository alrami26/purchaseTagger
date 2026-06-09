#!/usr/bin/env python3
import ctypes
import csv
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk
from purchase_extractor import (
    ACCOUNT_TYPE_CREDIT,
    ACCOUNT_TYPE_DEBIT,
    BANK_BAC,
    BANK_BCR,
    BANK_PROMERICA,
    SUPPORTED_ACCOUNT_TYPES_BY_BANK,
    process_purchases,
)
from tag_store import DEFAULT_PARENT_CATEGORY, default_tag_info, load_tags, merge_tags, save_tags
from money import ZERO, format_amount, parse_amount
from summary import (
    available_months,
    average_spend_by_tag_month,
    budget_metadata_aggregates,
    currency_totals,
    filter_rows_by_month,
    filter_rows_by_text,
    purchase_rows,
    summary_insights,
    summary_aggregates,
)
from ui_state import (
    ALL_MONTHS,
    ALL_TAGS,
    available_currencies,
    available_tags,
    build_file_label,
    filter_purchase_rows,
    format_totals,
    kpi_stats,
)
from version import APP_TITLE
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.normpath(os.path.join(base_path, relative_path))


APP_ICON_PATH = resource_path(os.path.join("assets", "app_icon.ico"))
APP_ICON_PNG_PATH = resource_path(os.path.join("assets", "app_icon.png"))
WINDOWS_APP_ID = "PurchaseTagger.PDFPurchaseTagger.App"
BANK_OPTIONS = [BANK_BAC, BANK_PROMERICA, BANK_BCR]
ACCOUNT_TYPE_OPTIONS = [ACCOUNT_TYPE_CREDIT, ACCOUNT_TYPE_DEBIT]
STATEMENT_FILETYPES = [
    ("Estados de cuenta", "*.pdf *.html *.htm *.xls"),
    ("PDF", "*.pdf"),
    ("HTML", "*.html *.htm"),
    ("Excel HTML", "*.xls"),
]
ALL_CURRENCIES = "Todas las monedas"
DEFAULT_WINDOW_WIDTH = 1020
DEFAULT_WINDOW_HEIGHT = 680
DEFAULT_WINDOW_GEOMETRY = f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}"


def amount_sign(amount):
    return "-" if parse_amount(amount) < ZERO else "+"


def display_purchase_row(row):
    date, description, amount, currency, tag = row[:5]
    sign = row[5] if len(row) > 5 else amount_sign(amount)
    display_amount = format_amount(abs(parse_amount(amount)))
    return [date, description, sign, display_amount, currency, tag]


def set_windows_app_user_model_id(app_id=WINDOWS_APP_ID):
    if sys.platform != "win32":
        return False
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError):
        return False
    return True


def simple_input(parent, title, prompt, default=None):
    """
    Muestra un diálogo con un Label y un Entry.
    Si se proporciona `default`, lo precarga y selecciona en el Entry.
    """
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.geometry('300x100')
    dlg.configure(bg='#FAFAFA')
    ttk.Label(dlg, text=prompt).pack(pady=5)
    entry = ttk.Entry(dlg)
    entry.pack(padx=10)
    if default is not None:
        entry.insert(0, default)
        entry.select_range(0, tk.END)
    res = {'value': None}
    def on_ok():
        res['value'] = entry.get().strip()
        dlg.destroy()
    ttk.Button(dlg, text='Aceptar', command=on_ok).pack(pady=5)
    dlg.grab_set()
    parent.wait_window(dlg)
    return res['value']

class PurchaseTaggerUI(ctk.CTk):
    from views.tags import (
        _build_tags_view,
        _parse_limit_value,
        _refresh_tag_filter_options,
        _select_tag_in_list,
        _set_status,
        _set_tag_selection,
        add_parent_category,
        add_keyword,
        add_tag,
        edit_keyword,
        edit_tag,
        export_tags_json,
        import_tags_json,
        load_tag_details,
        on_parent_category_selected,
        on_tags_tab_changed,
        open_tag_editor,
        refresh_tag_lists,
        remove_parent_category,
        remove_keyword,
        remove_tag,
        rename_parent_category,
        save_current_tag_limit,
        save_tags_from_view,
        selected_tag_name,
    )

    def __init__(self):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(DEFAULT_WINDOW_GEOMETRY)
        self._apply_app_icon()

        self.pdf_files = []
        self.tags = load_tags()
        self.natag = 'N/A'

        self.all_rows = []
        self.filtered_rows = []
        self.tree_item_rows = {}

        self.active_view = "Imports"
        self.search_var = tk.StringVar()
        self.currency_var = tk.StringVar(value=ALL_CURRENCIES)
        self.import_currency_var = tk.StringVar(value="")
        self.bank_var = tk.StringVar(value=BANK_BAC)
        self.account_type_var = tk.StringVar(value=ACCOUNT_TYPE_CREDIT)
        self.month_var = tk.StringVar(value=ALL_MONTHS)
        self.tag_filter_var = tk.StringVar(value=ALL_TAGS)
        self.status_var = tk.StringVar(value="Listo")
        self.file_label_var = tk.StringVar(value=build_file_label(self.pdf_files))
        self.total_var = tk.StringVar(value="Totales: 0.00")
        self.kpi_vars = {
            "total_rows": tk.StringVar(value="0"),
            "visible_rows": tk.StringVar(value="0"),
            "untagged_rows": tk.StringVar(value="0"),
            "currency_count": tk.StringVar(value="0"),
            "over_limit_tags": tk.StringVar(value="0"),
        }

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=190, corner_radius=0, fg_color="#1f2633")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self.workspace = ctk.CTkFrame(self, corner_radius=0, fg_color="#f4f6f8")
        self.workspace.grid(row=0, column=1, sticky="nsew")
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(1, weight=1)

        self._build_sidebar()
        self.show_view("Imports")

    def _apply_app_icon(self):
        if not os.path.exists(APP_ICON_PATH):
            return
        try:
            self.iconbitmap(APP_ICON_PATH)
        except tk.TclError:
            pass
        if os.path.exists(APP_ICON_PNG_PATH):
            try:
                self._app_icon_photo = tk.PhotoImage(file=APP_ICON_PNG_PATH)
                self.iconphoto(True, self._app_icon_photo)
            except tk.TclError:
                pass

    def _build_sidebar(self):
        title = ctk.CTkLabel(
            self.sidebar,
            text="Etiquetador",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#f8fafc",
        )
        title.pack(anchor="w", padx=16, pady=(20, 2))

        subtitle = ctk.CTkLabel(
            self.sidebar,
            text="Espacio financiero",
            font=ctk.CTkFont(size=12),
            text_color="#aeb8c7",
        )
        subtitle.pack(anchor="w", padx=16, pady=(0, 22))

        self.nav_buttons = {}
        nav_labels = {
            "Imports": "Importar",
            "Purchases": "Compras",
            "Summaries": "Resúmenes",
            "Tags": "Etiquetas",
        }
        for view in ("Imports", "Purchases", "Summaries", "Tags"):
            button = ctk.CTkButton(
                self.sidebar,
                text=nav_labels[view],
                anchor="w",
                fg_color="transparent",
                hover_color="#334155",
                text_color="#cbd5e1",
                command=lambda name=view: self.show_view(name),
            )
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[view] = button

        ctk.CTkLabel(
            self.sidebar,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=11),
            text_color="#aeb8c7",
            wraplength=150,
            justify="left",
        ).pack(side="bottom", anchor="w", padx=16, pady=18)

    def show_view(self, view_name):
        self.active_view = view_name
        for name, button in self.nav_buttons.items():
            if name == view_name:
                button.configure(fg_color="#334155", text_color="#f8fafc")
            else:
                button.configure(fg_color="transparent", text_color="#cbd5e1")

        self._clear_workspace_widget_refs()
        for child in self.workspace.winfo_children():
            child.destroy()
        self._clear_workspace_widget_refs()

        if view_name == "Imports":
            self._build_imports_view()
        elif view_name == "Purchases":
            self._build_purchases_view()
        elif view_name == "Summaries":
            self._build_summary_view()
        elif view_name == "Tags":
            self._build_tags_view()

    def _clear_workspace_widget_refs(self):
        for name in (
            "tree",
            "import_currency_menu",
            "bank_menu",
            "account_type_menu",
            "currency_menu",
            "month_menu",
            "tag_menu",
            "visible_count_var",
            "summary_frame",
            "summary_insights_frame",
            "summary_insight_vars",
            "summary_headline_var",
            "summary_messages_var",
            "summary_choice_var",
            "summary_chart_menu",
            "summary_month_menu",
            "summary_month_var",
            "summary_currency_vars",
            "summary_canvas",
            "summary_figure",
            "tag_listbox",
            "tags_tabview",
            "tag_detail_title",
            "tag_name_var",
            "tag_name_entry",
            "selected_category_var",
            "selected_category_label",
            "tag_management_label",
            "category_management_label",
            "tag_actions_frame",
            "category_actions_section",
            "tag_form",
            "keyword_label",
            "keyword_buttons_frame",
            "keyword_listbox",
            "tag_detail_widgets",
            "budget_type_menu",
            "budget_period_menu",
            "planned_amount_entry",
            "limit_var",
            "budget_type_var",
            "parent_category_listbox",
            "parent_category_menu",
            "parent_category_var",
            "expense_nature_menu",
            "financial_purpose_menu",
            "budget_period_var",
            "expense_nature_var",
            "financial_purpose_var",
            "add_keyword_button",
            "edit_keyword_button",
            "remove_keyword_button",
            "save_tag_details_button",
        ):
            if name in self.__dict__:
                if name == "summary_canvas" and self.summary_canvas is not None:
                    self.summary_canvas.get_tk_widget().destroy()
                if name == "summary_figure" and self.summary_figure is not None:
                    plt.close(self.summary_figure)
                delattr(self, name)

    def _has_live_tree(self):
        tree = self.__dict__.get("tree")
        if tree is None:
            return False
        if not hasattr(tree, "winfo_exists"):
            return True
        try:
            return bool(tree.winfo_exists())
        except tk.TclError:
            return False

    def _var_value(self, name, default):
        var = self.__dict__.get(name)
        if var is None:
            return default
        return var.get()

    def _build_placeholder_view(self, title):
        ctk.CTkLabel(
            self.workspace,
            text=title,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#171a20",
        ).grid(row=0, column=0, sticky="w", padx=24, pady=24)

    def _panel(self, parent, **grid_options):
        frame = ctk.CTkFrame(parent, fg_color="#ffffff", border_width=1, border_color="#e0e5ec", corner_radius=8)
        frame.grid(**grid_options)
        return frame

    def _build_page_header(self, parent, title, subtitle, action_text=None, action_command=None):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#171a20",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text=subtitle,
            font=ctk.CTkFont(size=12),
            text_color="#6b7280",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        if action_text and action_command:
            ctk.CTkButton(header, text=action_text, command=action_command, fg_color="#2563eb").grid(
                row=0, column=1, rowspan=2, sticky="e"
            )

    def _format_import_month_range(self, rows):
        months = available_months(rows)
        if not months:
            return "Sin filas con fecha"
        if len(months) == 1:
            return months[0]
        return f"{months[0]} a {months[-1]}"

    def _import_overview_data(self):
        rows = purchase_rows(self.__dict__.get("all_rows", []))
        pdf_files = list(self.__dict__.get("pdf_files", []))
        natag = self.__dict__.get("natag", "N/A")
        currencies = sorted({row[3] for row in rows if len(row) > 3 and row[3]})
        import_currency_var = self.__dict__.get("import_currency_var")
        selected_currency = import_currency_var.get() if import_currency_var is not None else ""
        if selected_currency not in currencies:
            selected_currency = currencies[0] if currencies else ""
            if import_currency_var is not None:
                import_currency_var.set(selected_currency)
        data = {
            "file_count": len(pdf_files),
            "purchase_count": len(rows),
            "currencies": ", ".join(currencies) if currencies else "Ninguna",
            "currency_options": currencies,
            "selected_currency": selected_currency,
            "untagged_count": sum(1 for row in rows if len(row) > 4 and row[4] == natag),
            "over_limit_count": 0,
            "month_range": self._format_import_month_range(rows),
            "top_tag": "Ninguna",
            "largest_purchase": "Ninguna",
            "headline": "Carga compras para ver hallazgos.",
            "detail": "Selecciona archivos para completar este resumen.",
        }

        if not rows:
            return data
        if not selected_currency:
            data.update({
                "top_tag": "Selecciona una moneda",
                "largest_purchase": "Selecciona una moneda",
                "headline": "Selecciona una moneda para ver hallazgos.",
                "detail": "Los hallazgos por moneda necesitan una sola moneda seleccionada.",
            })
            return data

        currency = selected_currency
        limits = {
            tag: info.get("planned_amount", info.get("limit", ZERO))
            for tag, info in self.__dict__.get("tags", {}).items()
        }
        insight_data = summary_insights(rows, {currency}, limits, natag=natag)
        top_tags = insight_data["top_tags"]
        largest_purchases = insight_data["largest_purchases"]
        data.update({
            "over_limit_count": len(insight_data["over_limit_tags"]),
            "top_tag": f"{top_tags[0][0]} {format_amount(top_tags[0][1])}" if top_tags else "Ninguna",
            "headline": insight_data.get("headline", data["headline"]),
            "detail": insight_data.get("detail") or "\n".join(insight_data["messages"]),
        })
        if largest_purchases:
            largest = largest_purchases[0]
            amount = largest[2]
            try:
                amount = format_amount(abs(parse_amount(amount)))
            except (TypeError, ValueError):
                pass
            data["largest_purchase"] = f"{largest[1]} {currency} {amount}"
        return data

    def _build_import_overview(self, parent, row):
        data = self._import_overview_data()
        panel = self._panel(parent, row=row, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_columnconfigure(1, weight=0)
        panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            panel,
            text="Resumen de importación",
            text_color="#171a20",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 2))
        if data["currency_options"]:
            selector_frame = ctk.CTkFrame(panel, fg_color="transparent")
            selector_frame.grid(row=0, column=1, sticky="e", padx=14, pady=(10, 0))
            ctk.CTkLabel(
                selector_frame,
                text="Moneda",
                text_color="#6b7280",
                font=ctk.CTkFont(size=11),
            ).grid(row=0, column=0, sticky="e", padx=(0, 8))
            self.import_currency_menu = ctk.CTkOptionMenu(
                selector_frame,
                variable=self.import_currency_var,
                values=data["currency_options"],
                command=lambda _currency: self.show_view("Imports"),
                width=96,
            )
            self.import_currency_menu.grid(row=0, column=1, sticky="e")

        metrics_frame = ctk.CTkFrame(panel, fg_color="transparent")
        metrics_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=(4, 8))
        for index in range(4):
            metrics_frame.grid_columnconfigure(index, weight=1)

        metrics = [
            ("Archivos", data["file_count"]),
            ("Compras cargadas", data["purchase_count"]),
            ("Monedas", data["currencies"]),
            ("Rango de meses", data["month_range"]),
            ("Sin etiqueta", data["untagged_count"]),
            ("Sobre presupuesto", data["over_limit_count"]),
            ("Etiqueta principal", data["top_tag"]),
            ("Compra mayor", data["largest_purchase"]),
        ]
        for index, (label, value) in enumerate(metrics):
            stat_row = index // 4
            stat_column = index % 4
            ctk.CTkLabel(
                metrics_frame,
                text=label,
                text_color="#6b7280",
                font=ctk.CTkFont(size=11),
            ).grid(row=stat_row * 2, column=stat_column, sticky="w", padx=6, pady=(6, 0))
            ctk.CTkLabel(
                metrics_frame,
                text=str(value),
                text_color="#171a20",
                font=ctk.CTkFont(size=14, weight="bold"),
                wraplength=170,
                justify="left",
            ).grid(row=(stat_row * 2) + 1, column=stat_column, sticky="nw", padx=6, pady=(2, 8))

        ctk.CTkLabel(
            panel,
            text="Hallazgos",
            text_color="#6b7280",
            font=ctk.CTkFont(size=11),
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 0))

        insight_callout = ctk.CTkFrame(
            panel,
            fg_color="#eef6ff",
            border_width=1,
            border_color="#bfdbfe",
            corner_radius=6,
        )
        insight_callout.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 14))
        insight_callout.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            insight_callout,
            text=data["headline"],
            text_color="#1d4ed8",
            font=ctk.CTkFont(size=13, weight="bold"),
            wraplength=820,
            justify="left",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            insight_callout,
            text=data["detail"],
            text_color="#374151",
            font=ctk.CTkFont(size=12),
            wraplength=820,
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

    def _build_imports_view(self):
        self.workspace.grid_rowconfigure(1, weight=1)
        self._build_page_header(
            self.workspace,
            "Importar",
            "Carga estados de cuenta, etiqueta compras y revisa resultados.",
        )

        content = ctk.CTkFrame(self.workspace, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)

        self._build_file_panel(content, row=0)
        self._build_kpi_row(content, row=1)
        self._build_import_overview(content, row=2)
        self.apply_filter()

    def _build_purchases_view(self):
        self.workspace.grid_rowconfigure(1, weight=1)
        self._build_page_header(
            self.workspace,
            "Compras",
            "Revisa, busca y corrige compras etiquetadas.",
        )

        content = ctk.CTkFrame(self.workspace, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)

        self._build_kpi_row(content, row=0)
        self._build_filter_toolbar(content, row=1)
        self._build_purchase_table(content, row=2)
        self._build_totals_footer(content, row=3)
        self.apply_filter()

    def _build_file_panel(self, parent, row):
        panel = self._panel(parent, row=row, column=0, sticky="ew", pady=(0, 12))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_columnconfigure(1, weight=0)
        panel.grid_columnconfigure(2, weight=0)
        ctk.CTkLabel(panel, text="Archivos seleccionados", text_color="#6b7280", font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 0)
        )
        ctk.CTkLabel(
            panel,
            textvariable=self.file_label_var,
            text_color="#171a20",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(2, 12))
        ctk.CTkLabel(panel, text="Banco", text_color="#6b7280", font=ctk.CTkFont(size=11)).grid(
            row=0, column=1, sticky="w", padx=(0, 8), pady=(12, 0)
        )
        self.bank_menu = ctk.CTkOptionMenu(
            panel,
            variable=self.bank_var,
            values=BANK_OPTIONS,
            command=self._refresh_account_type_options,
            width=92,
        )
        self.bank_menu.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=(2, 12))
        ctk.CTkLabel(panel, text="Tipo", text_color="#6b7280", font=ctk.CTkFont(size=11)).grid(
            row=0, column=2, sticky="w", padx=(0, 8), pady=(12, 0)
        )
        self.account_type_menu = ctk.CTkOptionMenu(
            panel,
            variable=self.account_type_var,
            values=ACCOUNT_TYPE_OPTIONS,
            width=104,
        )
        self.account_type_menu.grid(row=1, column=2, sticky="w", padx=(0, 8), pady=(2, 12))
        ctk.CTkButton(panel, text="Buscar y etiquetar", command=self.browse_pdf, width=130).grid(
            row=1, column=3, sticky="w", padx=(0, 8), pady=(2, 12)
        )
        ctk.CTkButton(panel, text="Limpiar", command=self.clear_pdfs, width=80, fg_color="#64748b").grid(
            row=1, column=4, sticky="w", padx=(0, 14), pady=(2, 12)
        )

    def _refresh_account_type_options(self, selected_bank=None):
        bank = selected_bank or self._var_value("bank_var", BANK_BAC)
        values = list(SUPPORTED_ACCOUNT_TYPES_BY_BANK.get(bank, ACCOUNT_TYPE_OPTIONS))
        if hasattr(self, "account_type_menu"):
            self.account_type_menu.configure(values=values)
        if self._var_value("account_type_var", ACCOUNT_TYPE_CREDIT) not in values:
            self.account_type_var.set(values[0])

    def _build_kpi_row(self, parent, row):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        for index in range(5):
            frame.grid_columnconfigure(index, weight=1)
        cards = [
            ("Compras", "total_rows"),
            ("Visibles", "visible_rows"),
            ("Sin etiqueta", "untagged_rows"),
            ("Monedas", "currency_count"),
            ("Sobre presupuesto", "over_limit_tags"),
        ]
        for index, (label, key) in enumerate(cards):
            card = ctk.CTkFrame(frame, fg_color="#ffffff", border_width=1, border_color="#e0e5ec", corner_radius=8)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            ctk.CTkLabel(card, text=label, text_color="#6b7280", font=ctk.CTkFont(size=11)).pack(
                anchor="w", padx=12, pady=(10, 0)
            )
            ctk.CTkLabel(
                card,
                textvariable=self.kpi_vars[key],
                text_color="#171a20",
                font=ctk.CTkFont(size=22, weight="bold"),
            ).pack(anchor="w", padx=12, pady=(2, 10))

    def _build_filter_toolbar(self, parent, row):
        panel = self._panel(parent, row=row, column=0, sticky="ew", pady=(0, 12))
        panel.grid_columnconfigure(0, weight=1)
        if not getattr(self, "_search_trace_registered", False):
            self.search_var.trace_add("write", lambda *args: self.apply_filter())
            self._search_trace_registered = True
        search = ctk.CTkEntry(panel, textvariable=self.search_var, placeholder_text="Buscar compras, descripciones o etiquetas")
        search.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.currency_menu = ctk.CTkOptionMenu(
            panel,
            variable=self.currency_var,
            values=[ALL_CURRENCIES],
            command=lambda _: self.apply_filter(),
        )
        self.currency_menu.grid(row=0, column=1, padx=(0, 8))
        self.month_menu = ctk.CTkOptionMenu(
            panel,
            variable=self.month_var,
            values=[ALL_MONTHS],
            command=lambda _: self.apply_filter(),
        )
        self.month_menu.grid(row=0, column=2, padx=(0, 8))
        self.tag_menu = ctk.CTkOptionMenu(
            panel,
            variable=self.tag_filter_var,
            values=[ALL_TAGS],
            command=lambda _: self.apply_filter(),
        )
        self.tag_menu.grid(row=0, column=3, padx=(0, 8))
        ctk.CTkButton(panel, text="Restablecer", command=self.reset_filters, width=96, fg_color="#64748b").grid(
            row=0, column=4, padx=(0, 8)
        )
        ctk.CTkButton(panel, text="Exportar", command=self.export_csv, width=82).grid(row=0, column=5, padx=(0, 10))

    def _build_purchase_table(self, parent, row):
        table_frame = self._panel(parent, row=row, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        cols = ("date", "description", "sign", "amount", "currency", "tag")
        headings = {
            "date": "Fecha",
            "description": "Descripción",
            "sign": "Signo",
            "amount": "Monto",
            "currency": "Moneda",
            "tag": "Etiqueta",
        }
        self.tree = ttk.Treeview(table_frame, columns=cols, displaycolumns=cols, show="headings")
        for col in cols:
            self.tree.heading(
                col,
                text=headings[col],
                command=lambda selected_col=col: self.sort_column(selected_col, False),
            )
        self.tree.column("date", width=95, minwidth=85, anchor="w", stretch=False)
        self.tree.column("description", width=250, minwidth=220, anchor="w", stretch=True)
        self.tree.column("sign", width=55, minwidth=45, anchor="center", stretch=False)
        self.tree.column("amount", width=90, minwidth=80, anchor="e", stretch=False)
        self.tree.column("currency", width=75, minwidth=70, anchor="center", stretch=False)
        self.tree.column("tag", width=125, minwidth=100, anchor="w", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(1, 0), pady=1)
        self.tree.bind("<Button-3>", self.on_right_click)

        vertical_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        vertical_scrollbar.grid(row=0, column=1, sticky="ns")
        horizontal_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical_scrollbar.set, xscrollcommand=horizontal_scrollbar.set)
        self._style_treeview()

    def _build_totals_footer(self, parent, row):
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.grid(row=row, column=0, sticky="ew", pady=(8, 0))
        footer.grid_columnconfigure(0, weight=1)
        self.visible_count_var = tk.StringVar(value="Mostrando 0 compras")
        ctk.CTkLabel(
            footer,
            textvariable=self.visible_count_var,
            text_color="#6b7280",
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            footer,
            textvariable=self.total_var,
            text_color="#171a20",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=1, sticky="e")

    def _style_treeview(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#171a20",
            rowheight=30,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#eef2f7",
            foreground="#475569",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#171a20")])

    def _refresh_filter_options(self):
        if "currency_menu" in self.__dict__:
            currency_values = [ALL_CURRENCIES] + available_currencies(self.all_rows)
            self.currency_menu.configure(values=currency_values)
            if self.currency_var.get() not in currency_values:
                self.currency_var.set(ALL_CURRENCIES)
        if "month_menu" in self.__dict__:
            month_values = [ALL_MONTHS] + available_months(self.all_rows)
            self.month_menu.configure(values=month_values)
            if self.month_var.get() not in month_values:
                self.month_var.set(ALL_MONTHS)
        if "tag_menu" in self.__dict__:
            tag_values = [ALL_TAGS] + available_tags(self.all_rows)
            self.tag_menu.configure(values=tag_values)
            if self.tag_filter_var.get() not in tag_values:
                self.tag_filter_var.set(ALL_TAGS)

    def _update_kpis(self):
        stats = kpi_stats(self.all_rows, self.filtered_rows, self.tags, self.natag)
        for key, value in stats.items():
            if "kpi_vars" in self.__dict__ and key in self.kpi_vars:
                self.kpi_vars[key].set(str(value))

    def _build_summary_insights_panel(self, parent, row):
        self.summary_insights_frame = self._panel(parent, row=row, column=0, sticky="ew", pady=(0, 12))
        for index in range(5):
            self.summary_insights_frame.grid_columnconfigure(index, weight=1)

        self.summary_insight_vars = {
            "total_spend": tk.StringVar(value="0.00"),
            "purchase_count": tk.StringVar(value="0"),
            "top_tag": tk.StringVar(value="Ninguna"),
            "over_limit": tk.StringVar(value="0"),
            "largest_purchase": tk.StringVar(value="Ninguna"),
        }
        metrics = [
            ("Gasto total", "total_spend"),
            ("Compras", "purchase_count"),
            ("Etiqueta principal", "top_tag"),
            ("Sobre presupuesto", "over_limit"),
            ("Compra mayor", "largest_purchase"),
        ]
        for index, (label, key) in enumerate(metrics):
            ctk.CTkLabel(
                self.summary_insights_frame,
                text=label,
                text_color="#6b7280",
                font=ctk.CTkFont(size=11),
            ).grid(row=0, column=index, sticky="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(
                self.summary_insights_frame,
                textvariable=self.summary_insight_vars[key],
                text_color="#171a20",
                font=ctk.CTkFont(size=14, weight="bold"),
                wraplength=150,
                justify="left",
            ).grid(row=1, column=index, sticky="nw", padx=12, pady=(2, 8))

        ctk.CTkLabel(
            self.summary_insights_frame,
            text="Hallazgos",
            text_color="#6b7280",
            font=ctk.CTkFont(size=11),
        ).grid(row=2, column=0, sticky="w", padx=12, pady=(0, 0))

        insight_callout = ctk.CTkFrame(
            self.summary_insights_frame,
            fg_color="#fff7ed",
            border_width=1,
            border_color="#fed7aa",
            corner_radius=6,
        )
        insight_callout.grid(row=3, column=0, columnspan=5, sticky="ew", padx=12, pady=(4, 12))
        insight_callout.grid_columnconfigure(0, weight=1)

        self.summary_headline_var = tk.StringVar(value="Carga compras para ver hallazgos.")
        ctk.CTkLabel(
            insight_callout,
            textvariable=self.summary_headline_var,
            text_color="#9a3412",
            font=ctk.CTkFont(size=13, weight="bold"),
            wraplength=820,
            justify="left",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        self.summary_messages_var = tk.StringVar(value="Carga compras para ver hallazgos.")
        ctk.CTkLabel(
            insight_callout,
            textvariable=self.summary_messages_var,
            text_color="#374151",
            font=ctk.CTkFont(size=12),
            wraplength=820,
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

    def _render_summary_insights(self, rows, selected_currencies, month_key):
        if (
            "summary_insight_vars" not in self.__dict__
            or "summary_headline_var" not in self.__dict__
            or "summary_messages_var" not in self.__dict__
        ):
            return

        if len(selected_currencies) != 1:
            self.summary_insight_vars["total_spend"].set("0.00")
            self.summary_insight_vars["purchase_count"].set("0")
            self.summary_insight_vars["top_tag"].set("Ninguna")
            self.summary_insight_vars["over_limit"].set("0")
            self.summary_insight_vars["largest_purchase"].set("Ninguna")
            self.summary_headline_var.set("Selecciona una moneda para ver hallazgos.")
            self.summary_messages_var.set("Los hallazgos se muestran solo con una moneda seleccionada.")
            return

        limits = {tag: info.get("planned_amount", info.get("limit", ZERO)) for tag, info in self.tags.items()}
        insight_data = summary_insights(
            rows,
            selected_currencies,
            limits,
            month_key=month_key,
            natag=self.natag,
        )
        currency = next(iter(selected_currencies))
        top_tags = insight_data["top_tags"]
        over_limit_tags = insight_data["over_limit_tags"]
        largest_purchases = insight_data["largest_purchases"]

        self.summary_insight_vars["total_spend"].set(f"{currency} {format_amount(insight_data['total_spend'])}")
        self.summary_insight_vars["purchase_count"].set(str(insight_data["purchase_count"]))
        self.summary_insight_vars["top_tag"].set(
            f"{top_tags[0][0]} {format_amount(top_tags[0][1])}" if top_tags else "Ninguna"
        )
        self.summary_insight_vars["over_limit"].set(str(len(over_limit_tags)))
        if largest_purchases:
            largest = largest_purchases[0]
            self.summary_insight_vars["largest_purchase"].set(
                f"{largest[1]} {currency} {format_amount(abs(parse_amount(largest[2])))}"
            )
        else:
            self.summary_insight_vars["largest_purchase"].set("Ninguna")
        self.summary_headline_var.set(insight_data.get("headline", "No hay hallazgos principales para esta selección."))
        self.summary_messages_var.set(
            insight_data.get("detail") or "\n".join(insight_data["messages"]) or "No hay hallazgos para esta selección."
        )

    def _build_summary_view(self):
        self.workspace.grid_rowconfigure(1, weight=1)
        self._build_page_header(
            self.workspace,
            "Resúmenes",
            "Analiza gasto por etiqueta, categoría, propósito y presupuesto.",
        )

        content = ctk.CTkFrame(self.workspace, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)

        controls = self._panel(content, row=0, column=0, sticky="ew", pady=(0, 12))
        controls.grid_columnconfigure(3, weight=1)

        chart_options = [
            "Gasto por etiqueta",
            "Gasto mensual",
            "Gasto acumulado",
            "Presupuesto vs gasto por etiqueta",
            "Gasto promedio por etiqueta/mes",
            "Gasto por tipo de presupuesto",
            "Gasto por categoría padre",
            "Gasto por propósito financiero",
        ]
        self.summary_choice_var = tk.StringVar(value=chart_options[0])
        self.summary_chart_menu = ctk.CTkOptionMenu(
            controls,
            variable=self.summary_choice_var,
            values=chart_options,
            command=lambda _choice: self.draw_summary(),
            width=210,
        )
        self.summary_chart_menu.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        rows = purchase_rows(self.all_rows)
        month_values = [ALL_MONTHS] + available_months(rows)
        self.summary_month_var = tk.StringVar(value=ALL_MONTHS)
        self.summary_month_menu = ctk.CTkOptionMenu(
            controls,
            variable=self.summary_month_var,
            values=month_values,
            command=lambda _month: self.draw_summary(),
            width=110,
        )
        self.summary_month_menu.grid(row=0, column=1, padx=(0, 8), pady=10, sticky="w")

        currency_frame = ctk.CTkFrame(controls, fg_color="transparent")
        currency_frame.grid(row=0, column=2, columnspan=2, sticky="w", padx=(0, 10), pady=8)
        self.summary_currency_vars = {}
        for index, currency in enumerate(available_currencies(rows)):
            var = tk.BooleanVar(value=index == 0)
            self.summary_currency_vars[currency] = var
            ctk.CTkCheckBox(
                currency_frame,
                text=currency,
                variable=var,
                command=self.draw_summary,
                width=80,
            ).grid(row=0, column=index, padx=(0, 8), pady=2, sticky="w")

        self._build_summary_insights_panel(content, row=1)

        self.summary_frame = self._panel(content, row=2, column=0, sticky="nsew")
        self.summary_frame.grid_rowconfigure(0, weight=1)
        self.summary_frame.grid_columnconfigure(0, weight=1)
        self.draw_summary()

    def _clear_summary_frame(self):
        if "summary_canvas" in self.__dict__ and self.summary_canvas is not None:
            self.summary_canvas.get_tk_widget().destroy()
            self.summary_canvas = None
        if "summary_figure" in self.__dict__ and self.summary_figure is not None:
            plt.close(self.summary_figure)
            self.summary_figure = None
        for child in self.summary_frame.winfo_children():
            child.destroy()

    def _show_summary_message(self, message):
        ctk.CTkLabel(
            self.summary_frame,
            text=message,
            text_color="#6b7280",
            font=ctk.CTkFont(size=14),
        ).grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

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

    def draw_summary(self):
        self._clear_summary_frame()

        rows = purchase_rows(self.all_rows)
        if not rows:
            self._show_summary_message("Carga compras para ver resúmenes.")
            return

        selected = {cur for cur, var in self.summary_currency_vars.items() if var.get()}
        self._render_summary_insights(rows, selected, self.summary_month_var.get())
        if not selected:
            self._show_summary_message("Selecciona al menos una moneda.")
            return
        if len(selected) > 1:
            self._show_summary_message("Selecciona una sola moneda para no mezclar monedas.")
            return

        data_rows = filter_rows_by_month(rows, self.summary_month_var.get())
        choice = self.summary_choice_var.get()
        if choice == "Gasto promedio por etiqueta/mes":
            self._draw_average_spend_table(data_rows, selected, report_months=available_months(data_rows))
            return

        aggregates = summary_aggregates(data_rows, selected)
        tag_totals = aggregates["tag_totals"]
        monthly = aggregates["monthly_totals"]
        cumulative_points = aggregates["cumulative_points"]

        fig, ax = plt.subplots(figsize=(7, 4.5))
        if choice == "Gasto por etiqueta":
            if tag_totals:
                if any(value < ZERO for value in tag_totals.values()):
                    labels = list(tag_totals.keys())
                    values = [float(tag_totals[label]) for label in labels]
                    x_values = list(range(len(labels)))
                    colors = ["#dc2626" if value < 0 else "#2563eb" for value in values]
                    ax.bar(x_values, values, color=colors, width=0.6)
                    ax.set_xticks(x_values)
                    ax.set_xticklabels(labels, rotation=45, ha="right")
                else:
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
            self._style_summary_axes(ax, "Gasto por etiqueta")
        elif choice == "Gasto mensual":
            months = sorted(monthly.keys())
            ax.bar(months, [float(monthly[month]) for month in months], color="#2563eb", width=0.6)
            self._style_summary_axes(ax, "Gasto mensual", ylabel="Total")
            ax.tick_params(axis="x", rotation=45)
        elif choice == "Gasto acumulado":
            xs = [date_label for date_label, _running in cumulative_points]
            ys = [float(running) for _date_label, running in cumulative_points]
            ax.plot(xs, ys, marker="o", color="#2563eb", linewidth=2.2, markerfacecolor="#ffffff")
            self._style_summary_axes(ax, "Gasto acumulado en el tiempo", ylabel="Total")
            ax.tick_params(axis="x", rotation=45)
        elif choice == "Presupuesto vs gasto por etiqueta":
            labels = list(tag_totals.keys())
            spend = [float(tag_totals[tag]) for tag in labels]
            limits = [
                float(parse_amount(self.tags.get(tag, {}).get("planned_amount", self.tags.get(tag, {}).get("limit", ZERO))))
                for tag in labels
            ]
            x_values = list(range(len(labels)))
            spend_colors = [
                self._summary_status_color(spend_value, limit_value)
                for spend_value, limit_value in zip(spend, limits)
            ]
            ax.bar([x - 0.2 for x in x_values], spend, width=0.4, label="Gasto", color=spend_colors)
            ax.bar([x + 0.2 for x in x_values], limits, width=0.4, label="Presupuesto", color="#9ca3af")
            ax.set_xticks(x_values)
            ax.set_xticklabels(labels, rotation=45, ha="right")
            self._style_summary_axes(ax, "Comparación: presupuesto vs gasto", ylabel="Total")
            ax.legend(frameon=False)
        elif choice in {
            "Gasto por tipo de presupuesto",
            "Gasto por categoría padre",
            "Gasto por propósito financiero",
        }:
            metadata = budget_metadata_aggregates(data_rows, selected, self.tags)
            group_key = {
                "Gasto por tipo de presupuesto": "by_budget_type",
                "Gasto por categoría padre": "by_parent_category",
                "Gasto por propósito financiero": "by_financial_purpose",
            }[choice]
            values_by_label = metadata[group_key]
            labels = list(values_by_label.keys())
            values = [float(values_by_label[label]) for label in labels]
            ax.bar(labels, values, color="#2563eb", width=0.6)
            self._style_summary_axes(ax, choice, ylabel="Total")
            ax.tick_params(axis="x", rotation=45)
        else:
            plt.close(fig)
            self._show_summary_message("Elige un resumen.")
            return

        self._finalize_summary_figure(fig)
        self.summary_figure = fig
        self.summary_canvas = FigureCanvasTkAgg(fig, master=self.summary_frame)
        self.summary_canvas.draw()
        self.summary_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def _draw_average_spend_table(self, data_rows, selected, report_months=None):
        limits = {tag: parse_amount(info.get("planned_amount", info.get("limit", ZERO))) for tag, info in self.tags.items()}
        summary_data = average_spend_by_tag_month(data_rows, selected, limits, month_keys=report_months)
        tag_totals = summary_data["tag_month_totals"]
        tag_global_totals = summary_data["tag_global_totals"]
        average_by_tag = summary_data["tag_average_by_month"]
        totals = summary_data["totals"]
        months = summary_data["months"]
        currencies_by_month = summary_data["currencies_by_month"]

        self.summary_frame.grid_rowconfigure(0, weight=1)
        self.summary_frame.grid_columnconfigure(0, weight=1)

        month_columns = [
            f"{month_key}_{currency}"
            for month_key in months
            for currency in currencies_by_month[month_key]
        ]
        columns = ["Etiqueta", "Presupuesto"] + month_columns + ["Total", "Promedio"]
        summary_tree = ttk.Treeview(self.summary_frame, columns=columns, show="headings")
        summary_tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))

        vsb = ttk.Scrollbar(self.summary_frame, orient="vertical", command=summary_tree.yview)
        hsb = ttk.Scrollbar(self.summary_frame, orient="horizontal", command=summary_tree.xview)
        vsb.grid(row=0, column=1, sticky="ns", pady=(10, 0), padx=(0, 10))
        hsb.grid(row=1, column=0, sticky="ew", padx=(10, 0), pady=(0, 10))
        summary_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        summary_tree.heading("Etiqueta", text="Etiqueta", anchor="w")
        summary_tree.column("Etiqueta", width=120, anchor="w", stretch=True)
        summary_tree.heading("Presupuesto", text="Presupuesto", anchor="e")
        summary_tree.column("Presupuesto", width=100, anchor="e", stretch=True)
        summary_tree.heading("Total", text="Total", anchor="e")
        summary_tree.column("Total", width=110, anchor="e", stretch=True)
        summary_tree.heading("Promedio", text="Promedio", anchor="e")
        summary_tree.column("Promedio", width=90, anchor="e", stretch=True)

        for column in month_columns:
            month_key, currency = column.split("_")
            month_name = datetime.strptime(month_key, "%Y-%m").strftime("%b %Y")
            summary_tree.heading(column, text=f"{month_name} {currency}", anchor="center")
            summary_tree.column(column, width=90, anchor="e", stretch=True)

        summary_tree.tag_configure("category", foreground="#111827")
        summary_tree.tag_configure("over_limit", foreground="red")

        tags_by_category = {}
        for tag in sorted(tag_totals):
            category = self._parent_category_for_tag(tag)
            tags_by_category.setdefault(category, []).append(tag)

        for category in sorted(tags_by_category):
            category_tags = tags_by_category[category]
            category_limit = sum((limits.get(tag, ZERO) for tag in category_tags), ZERO)
            category_average = sum((average_by_tag.get(tag, ZERO) for tag in category_tags), ZERO)
            category_total = sum((tag_global_totals.get(tag, ZERO) for tag in category_tags), ZERO)
            category_detail = self._average_spend_detail_values(
                category_tags,
                tag_totals,
                months,
                currencies_by_month,
            )
            category_row_tags = ["over_limit"] if category_average > category_limit else ["category"]
            summary_tree.insert(
                "",
                "end",
                values=[
                    category,
                    format_amount(category_limit),
                    *category_detail,
                    format_amount(category_total) if category_total else "",
                    format_amount(category_average) if category_average else "",
                ],
                tags=category_row_tags,
            )

            for tag in category_tags:
                limit = limits.get(tag, ZERO)
                average = average_by_tag.get(tag, ZERO)
                tag_total = tag_global_totals.get(tag, ZERO)
                detail_values = self._average_spend_detail_values(
                    [tag],
                    tag_totals,
                    months,
                    currencies_by_month,
                )
                row_tags = ["over_limit"] if summary_data["over_limit_by_tag"].get(tag) else []
                summary_tree.insert(
                    "",
                    "end",
                    values=[
                        f"  {tag}",
                        format_amount(limit),
                        *detail_values,
                        format_amount(tag_total) if tag_total else "",
                        format_amount(average) if average else "",
                    ],
                    tags=row_tags,
                )

        total_detail = [
            format_amount(totals.get(month_key, {}).get(currency))
            if totals.get(month_key, {}).get(currency)
            else ""
            for month_key in months
            for currency in currencies_by_month[month_key]
        ]
        total_tags = ["over_limit"] if summary_data["total_over_limit"] else []
        summary_tree.insert(
            "",
            "end",
            values=[
                "Total",
                format_amount(summary_data["total_limit"]),
                *total_detail,
                format_amount(summary_data["total_spend"]),
                format_amount(summary_data["total_average"]),
            ],
            tags=total_tags,
        )
        self.summary_frame.update_idletasks()

    def _parent_category_for_tag(self, tag):
        info = self.tags.get(tag, {})
        if not isinstance(info, dict):
            return DEFAULT_PARENT_CATEGORY
        category = str(info.get("parent_category", DEFAULT_PARENT_CATEGORY) or "").strip()
        return category or DEFAULT_PARENT_CATEGORY

    def _average_spend_detail_values(self, tags, tag_totals, months, currencies_by_month):
        values = []
        for month_key in months:
            for currency in currencies_by_month[month_key]:
                total = sum(
                    (tag_totals[tag].get(month_key, {}).get(currency, ZERO) for tag in tags),
                    ZERO,
                )
                values.append(format_amount(total) if total else "")
        return values

    def browse_pdf(self):
        files = filedialog.askopenfilenames(filetypes=STATEMENT_FILETYPES)
        if files:
            self.pdf_files = list(files)
            self.file_label_var.set(build_file_label(self.pdf_files))
            self.status_var.set(f"{len(self.pdf_files)} archivo(s) seleccionado(s)")
            self.load()

    def clear_pdfs(self):
        self.pdf_files = []
        self.all_rows = []
        self.filtered_rows = []
        self.tree_item_rows.clear()
        self.search_var.set("")
        self.currency_var.set(ALL_CURRENCIES)
        self.import_currency_var.set("")
        self.month_var.set(ALL_MONTHS)
        self.tag_filter_var.set(ALL_TAGS)
        self.bank_var.set(BANK_BAC)
        self.account_type_var.set(ACCOUNT_TYPE_CREDIT)
        self._refresh_account_type_options(BANK_BAC)
        self.file_label_var.set(build_file_label(self.pdf_files))
        self.status_var.set("No hay archivos seleccionados")
        if self.__dict__.get("active_view") == "Imports":
            self.show_view("Imports")
        else:
            self.apply_filter()

    def load(self):
        if not self.pdf_files:
            messagebox.showwarning('Sin archivo', 'Selecciona uno o más archivos de estado de cuenta.')
            return
        self.all_rows = []
        self.status_var.set("Procesando archivos...")
        self.update_idletasks()
        bank = self._var_value("bank_var", BANK_BAC)
        account_type = self._var_value("account_type_var", ACCOUNT_TYPE_CREDIT)
        for pdf in self.pdf_files:
            try:
                raw = process_purchases(pdf, bank=bank, account_type=account_type)
                for d, desc, amt, cur, tag, _ in raw:
                    formatted_amount = format_amount(amt)
                    self.all_rows.append([d, desc, formatted_amount, cur, tag, amount_sign(formatted_amount)])
            except Exception as e:
                messagebox.showerror('Error', f'{os.path.basename(pdf)}: {e}')
        self.apply_filter()
        self.status_var.set(f"Se cargaron y etiquetaron {len(self.all_rows)} compras")
        if self.__dict__.get("active_view") == "Imports":
            self.show_view("Imports")

    def apply_filter(self):
        self._refresh_filter_options()
        selected_currency = self._var_value("currency_var", ALL_CURRENCIES)
        currencies = set() if selected_currency == ALL_CURRENCIES else {selected_currency}
        self.filtered_rows = filter_purchase_rows(
            self.all_rows,
            search_text=self._var_value("search_var", ""),
            currencies=currencies,
            month_key=self._var_value("month_var", ALL_MONTHS),
            tag_name=self._var_value("tag_filter_var", ALL_TAGS),
        )
        self.tree_item_rows.clear()
        if not self._has_live_tree():
            self._update_kpis()
            self.total_var.set(format_totals(self.filtered_rows))
            if "visible_count_var" in self.__dict__:
                self.visible_count_var.set(f"Mostrando {len(self.filtered_rows)} compras")
            return
        for i in self.tree.get_children():
            self.tree.delete(i)
        for index, row in enumerate(self.filtered_rows):
            tags = ("odd",) if index % 2 else ("even",)
            iid = self.tree.insert('', 'end', values=display_purchase_row(row), tags=tags)
            self.tree_item_rows[iid] = row
        self.tree.tag_configure("even", background="#ffffff")
        self.tree.tag_configure("odd", background="#fafbfc")
        self._update_kpis()
        self.total_var.set(format_totals(self.filtered_rows))
        if "visible_count_var" in self.__dict__:
            self.visible_count_var.set(f"Mostrando {len(self.filtered_rows)} compras")

    def reset_filters(self):
        self.search_var.set("")
        self.currency_var.set(ALL_CURRENCIES)
        self.month_var.set(ALL_MONTHS)
        self.tag_filter_var.set(ALL_TAGS)
        self.apply_filter()

    def on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        menu = tk.Menu(self, tearoff=0)
        for t in self.tags:
            menu.add_command(label=t, command=lambda tag=t, iid=iid: self.assign_tag(iid, tag))
        menu.add_separator()
        menu.add_command(label='Nueva etiqueta...', command=lambda iid=iid: self.create_and_assign(iid))
        menu.tk_popup(event.x_root, event.y_root)

    def _row_for_item(self, item_iid):
        return self.tree_item_rows[item_iid]

    def assign_tag(self, item_iid, tag):
        row = self._row_for_item(item_iid)
        old_tag = row[4]
        row[4] = tag
        self.tree.item(item_iid, values=display_purchase_row(row))
        if old_tag == self.natag:
            desc = row[1]
            if desc not in self.tags[tag]["keywords"]:
                self.tags[tag]["keywords"].append(desc)
                save_tags(self.tags)
        if "all_rows" in self.__dict__:
            self.apply_filter()
            self._set_status(f'Se asignó "{tag}" a la compra')

    def create_and_assign(self, item_iid):
        row = self._row_for_item(item_iid)
        desc = row[1]
        name = simple_input(self, 'Nueva etiqueta', 'Nombre de la nueva etiqueta:')
        if not name:
            return
        if name not in self.tags:
            self.tags[name] = default_tag_info(name, keywords=[desc])
        else:
            if desc not in self.tags[name]["keywords"]:
                self.tags[name]["keywords"].append(desc)
        save_tags(self.tags)
        self._refresh_tag_filter_options()
        self.assign_tag(item_iid, name)

    def open_summary(self):
        """Route legacy summary action to the workspace summary view."""
        self.show_view("Summaries")

    def sort_column(self, col, reverse):
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        if col == 'amount':
            data = [(parse_amount(v), k) for v, k in data]
        else:
            data = [(v.lower(), k) for v, k in data]
        data.sort(reverse=reverse)
        for idx, (_, k) in enumerate(data):
            self.tree.move(k, '', idx)
        self.tree.heading(col, command=lambda _c=col: self.sort_column(_c, not reverse))

    def export_csv(self):
        if not self.filtered_rows:
            messagebox.showwarning('Sin datos', 'No hay filas para exportar.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')])
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['fecha', 'descripcion', 'signo', 'monto', 'moneda', 'etiqueta'])
                w.writerows(display_purchase_row(row) for row in self.filtered_rows)
            messagebox.showinfo('Exportado', f'Se exportaron {len(self.filtered_rows)} filas a {path}')
        except Exception as e:
            messagebox.showerror('Error', str(e))

def main():
    set_windows_app_user_model_id()
    PurchaseTaggerUI().mainloop()


if __name__ == '__main__':
    main()
