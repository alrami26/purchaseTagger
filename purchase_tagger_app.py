#!/usr/bin/env python3
import csv
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk
from purchase_extractor import process_purchases
from tag_store import load_tags, save_tags
from summary import (
    available_months,
    average_spend_by_tag_month,
    currency_totals,
    filter_rows_by_month,
    filter_rows_by_text,
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
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime

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
    ttk.Button(dlg, text='OK', command=on_ok).pack(pady=5)
    dlg.grab_set()
    parent.wait_window(dlg)
    return res['value']

class PurchaseTaggerUI(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.title("PDF Purchase Tagger")
        self.geometry("900x600")

        self.pdf_files = []
        self.tags = load_tags()
        self.natag = 'N/A'

        self.all_rows = []
        self.filtered_rows = []
        self.tree_item_rows = {}

        self.active_view = "Imports"
        self.search_var = tk.StringVar()
        self.currency_var = tk.StringVar(value="All currencies")
        self.month_var = tk.StringVar(value=ALL_MONTHS)
        self.tag_filter_var = tk.StringVar(value=ALL_TAGS)
        self.status_var = tk.StringVar(value="Ready")
        self.file_label_var = tk.StringVar(value=build_file_label(self.pdf_files))
        self.total_var = tk.StringVar(value="Totals: 0.00")
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

    def _build_sidebar(self):
        title = ctk.CTkLabel(
            self.sidebar,
            text="Purchase Tagger",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#f8fafc",
        )
        title.pack(anchor="w", padx=16, pady=(20, 2))

        subtitle = ctk.CTkLabel(
            self.sidebar,
            text="PDF finance workspace",
            font=ctk.CTkFont(size=12),
            text_color="#aeb8c7",
        )
        subtitle.pack(anchor="w", padx=16, pady=(0, 22))

        self.nav_buttons = {}
        for view in ("Imports", "Purchases", "Summaries", "Tags"):
            button = ctk.CTkButton(
                self.sidebar,
                text=view,
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
            "currency_menu",
            "month_menu",
            "tag_menu",
            "visible_count_var",
            "summary_frame",
            "summary_choice_var",
            "summary_chart_menu",
            "summary_month_menu",
            "summary_month_var",
            "summary_currency_vars",
            "summary_canvas",
            "summary_figure",
            "tag_listbox",
            "keyword_listbox",
            "limit_var",
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

    def _build_imports_view(self):
        self.workspace.grid_rowconfigure(1, weight=1)
        self._build_page_header(
            self.workspace,
            "Imports",
            "Load PDFs, tag purchases, and review results.",
            action_text="Load & Tag",
            action_command=self.load,
        )

        content = ctk.CTkFrame(self.workspace, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(3, weight=1)

        self._build_file_panel(content, row=0)
        self._build_kpi_row(content, row=1)
        self._build_filter_toolbar(content, row=2)
        self._build_purchase_table(content, row=3)
        self._build_totals_footer(content, row=4)
        self.apply_filter()

    def _build_purchases_view(self):
        self.workspace.grid_rowconfigure(1, weight=1)
        self._build_page_header(
            self.workspace,
            "Purchases",
            "Review, search, and correct tagged purchase rows.",
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
        ctk.CTkLabel(panel, text="Selected PDFs", text_color="#6b7280", font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 0)
        )
        ctk.CTkLabel(
            panel,
            textvariable=self.file_label_var,
            text_color="#171a20",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(2, 12))
        ctk.CTkButton(panel, text="Browse", command=self.browse_pdf, width=90).grid(
            row=0, column=1, rowspan=2, padx=(0, 8)
        )
        ctk.CTkButton(panel, text="Clear", command=self.clear_pdfs, width=80, fg_color="#64748b").grid(
            row=0, column=2, rowspan=2, padx=(0, 14)
        )

    def _build_kpi_row(self, parent, row):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        for index in range(5):
            frame.grid_columnconfigure(index, weight=1)
        cards = [
            ("Purchases", "total_rows"),
            ("Visible", "visible_rows"),
            ("Untagged", "untagged_rows"),
            ("Currencies", "currency_count"),
            ("Over Limit", "over_limit_tags"),
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
        search = ctk.CTkEntry(panel, textvariable=self.search_var, placeholder_text="Search purchases, descriptions, tags")
        search.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.currency_menu = ctk.CTkOptionMenu(
            panel,
            variable=self.currency_var,
            values=["All currencies"],
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
        ctk.CTkButton(panel, text="Reset", command=self.reset_filters, width=72, fg_color="#64748b").grid(
            row=0, column=4, padx=(0, 8)
        )
        ctk.CTkButton(panel, text="Export", command=self.export_csv, width=76).grid(row=0, column=5, padx=(0, 10))

    def _build_purchase_table(self, parent, row):
        table_frame = self._panel(parent, row=row, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        cols = ("date", "description", "amount", "currency", "tag")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        for col in cols:
            self.tree.heading(col, text=col.title(), command=lambda selected_col=col: self.sort_column(selected_col, False))
        self.tree.column("date", width=110, anchor="w")
        self.tree.column("description", width=360, anchor="w")
        self.tree.column("amount", width=120, anchor="e")
        self.tree.column("currency", width=90, anchor="center")
        self.tree.column("tag", width=140, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(1, 0), pady=1)
        self.tree.bind("<Button-3>", self.on_right_click)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self._style_treeview()

    def _build_totals_footer(self, parent, row):
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.grid(row=row, column=0, sticky="ew", pady=(8, 0))
        footer.grid_columnconfigure(0, weight=1)
        self.visible_count_var = tk.StringVar(value="Showing 0 purchases")
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
            currency_values = ["All currencies"] + available_currencies(self.all_rows)
            self.currency_menu.configure(values=currency_values)
            if self.currency_var.get() not in currency_values:
                self.currency_var.set("All currencies")
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

    def _build_summary_view(self):
        self.workspace.grid_rowconfigure(1, weight=1)
        self._build_page_header(
            self.workspace,
            "Summaries",
            "Analyze spending by tag, month, cumulative trend, and limits.",
        )

        content = ctk.CTkFrame(self.workspace, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        controls = self._panel(content, row=0, column=0, sticky="ew", pady=(0, 12))
        controls.grid_columnconfigure(3, weight=1)

        chart_options = [
            "Spend by Tag",
            "Monthly Spend",
            "Cumulative Spend",
            "Limite vs Gasto por Tag",
            "Gasto Promedio por Tag/Mes",
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

        rows = self.all_rows
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
            var = tk.BooleanVar(value=True)
            self.summary_currency_vars[currency] = var
            ctk.CTkCheckBox(
                currency_frame,
                text=currency,
                variable=var,
                command=self.draw_summary,
                width=80,
            ).grid(row=0, column=index, padx=(0, 8), pady=2, sticky="w")

        self.summary_frame = self._panel(content, row=1, column=0, sticky="nsew")
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

    def draw_summary(self):
        self._clear_summary_frame()

        rows = self.all_rows
        if not rows:
            self._show_summary_message("Load purchases to see summaries.")
            return

        selected = {cur for cur, var in self.summary_currency_vars.items() if var.get()}
        if not selected:
            self._show_summary_message("Select at least one currency.")
            return

        data_rows = filter_rows_by_month(rows, self.summary_month_var.get())
        choice = self.summary_choice_var.get()
        if choice == "Gasto Promedio por Tag/Mes":
            self._draw_average_spend_table(data_rows, selected)
            return

        aggregates = summary_aggregates(data_rows, selected)
        tag_totals = aggregates["tag_totals"]
        monthly = aggregates["monthly_totals"]
        cumulative_points = aggregates["cumulative_points"]

        fig, ax = plt.subplots(figsize=(6, 4))
        if choice == "Spend by Tag":
            if tag_totals:
                ax.pie(tag_totals.values(), labels=tag_totals.keys(), autopct="%1.1f%%")
            ax.set_title("Spend by Tag")
        elif choice == "Monthly Spend":
            months = sorted(monthly.keys())
            ax.bar(months, [monthly[month] for month in months])
            ax.set_title("Monthly Spend")
            ax.tick_params(axis="x", rotation=45)
        elif choice == "Cumulative Spend":
            xs = [date_label for date_label, _running in cumulative_points]
            ys = [running for _date_label, running in cumulative_points]
            ax.plot(xs, ys, marker="o")
            ax.set_title("Cumulative Spend Over Time")
            ax.set_ylabel("Total")
            ax.tick_params(axis="x", rotation=45)
        elif choice == "Limite vs Gasto por Tag":
            labels = list(tag_totals.keys())
            spend = [tag_totals[tag] for tag in labels]
            limits = [self.tags.get(tag, {}).get("limit", 0) for tag in labels]
            x_values = list(range(len(labels)))
            ax.bar([x - 0.2 for x in x_values], spend, width=0.4, label="Gasto")
            ax.bar([x + 0.2 for x in x_values], limits, width=0.4, label="Limite")
            ax.set_xticks(x_values)
            ax.set_xticklabels(labels, rotation=45, ha="right")
            ax.set_title("Comparacion: Limite vs Gasto por Tag")
            ax.legend()
        else:
            plt.close(fig)
            self._show_summary_message("Choose a summary chart.")
            return

        fig.tight_layout()
        self.summary_figure = fig
        self.summary_canvas = FigureCanvasTkAgg(fig, master=self.summary_frame)
        self.summary_canvas.draw()
        self.summary_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def _draw_average_spend_table(self, data_rows, selected):
        limits = {tag: info.get("limit", 0) for tag, info in self.tags.items()}
        summary_data = average_spend_by_tag_month(data_rows, selected, limits)
        tag_totals = summary_data["tag_month_totals"]
        tag_global_totals = summary_data["tag_global_totals"]
        average_by_tag = summary_data["tag_average_by_month"]
        totals = summary_data["totals"]
        months = summary_data["months"]
        currencies_by_month = summary_data["currencies_by_month"]

        self.summary_frame.grid_rowconfigure(0, weight=1)
        self.summary_frame.grid_columnconfigure(0, weight=1)

        columns = ["Tag", "Limite", "Promedio", "Tag Total"] + [
            f"{month_key}_{currency}"
            for month_key in months
            for currency in currencies_by_month[month_key]
        ]
        summary_tree = ttk.Treeview(self.summary_frame, columns=columns, show="headings")
        summary_tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))

        vsb = ttk.Scrollbar(self.summary_frame, orient="vertical", command=summary_tree.yview)
        hsb = ttk.Scrollbar(self.summary_frame, orient="horizontal", command=summary_tree.xview)
        vsb.grid(row=0, column=1, sticky="ns", pady=(10, 0), padx=(0, 10))
        hsb.grid(row=1, column=0, sticky="ew", padx=(10, 0), pady=(0, 10))
        summary_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        summary_tree.heading("Tag", text="Tag", anchor="w")
        summary_tree.column("Tag", width=120, anchor="w", stretch=True)
        summary_tree.heading("Limite", text="Limite", anchor="e")
        summary_tree.column("Limite", width=80, anchor="e", stretch=True)
        summary_tree.heading("Promedio", text="Promedio", anchor="e")
        summary_tree.column("Promedio", width=90, anchor="e", stretch=True)
        summary_tree.heading("Tag Total", text="Tag Total", anchor="e")
        summary_tree.column("Tag Total", width=100, anchor="e", stretch=True)

        for column in columns[4:]:
            month_key, currency = column.split("_")
            month_name = datetime.strptime(month_key, "%Y-%m").strftime("%b %Y")
            summary_tree.heading(column, text=f"{month_name} {currency}", anchor="center")
            summary_tree.column(column, width=90, anchor="e", stretch=True)

        summary_tree.tag_configure("over_limit", foreground="red")

        for tag in sorted(tag_totals):
            limit = limits.get(tag, 0)
            average = average_by_tag.get(tag, 0)
            tag_total = tag_global_totals.get(tag, 0)
            detail_values = [
                f"{tag_totals[tag].get(month_key, {}).get(currency):,.2f}"
                if tag_totals[tag].get(month_key, {}).get(currency)
                else ""
                for month_key in months
                for currency in currencies_by_month[month_key]
            ]
            row_tags = ["over_limit"] if summary_data["over_limit_by_tag"].get(tag) else []
            summary_tree.insert(
                "",
                "end",
                values=[
                    tag,
                    f"{limit:,.2f}",
                    f"{average:,.2f}" if average else "",
                    f"{tag_total:,.2f}" if tag_total else "",
                    *detail_values,
                ],
                tags=row_tags,
            )

        total_detail = [
            f"{totals.get(month_key, {}).get(currency):,.2f}"
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
                f"{summary_data['total_limit']:,.2f}",
                f"{summary_data['total_average']:,.2f}",
                f"{summary_data['total_spend']:,.2f}",
                *total_detail,
            ],
            tags=total_tags,
        )
        self.summary_frame.update_idletasks()

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
        text = value.strip()
        if not text:
            raise ValueError
        if any(marker in text.lower() for marker in (".", "e")):
            return float(text)
        return int(text)

    def save_current_tag_limit(self, tag_name=None):
        tag = tag_name or self.selected_tag_name()
        if not tag or tag not in self.tags or "limit_var" not in self.__dict__:
            return True
        try:
            limit = self._parse_limit_value(self.limit_var.get())
        except ValueError:
            messagebox.showwarning("Invalid Limit", "Monthly limit must be a number.")
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

    def add_tag(self):
        if not self.save_current_tag_limit():
            return
        name = simple_input(self, "New Tag", "Tag name:")
        if not name or name in self.tags:
            return
        self.tags[name] = {"keywords": [], "limit": 0}
        save_tags(self.tags)
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
        new = simple_input(self, "Edit Tag", f'New name for tag "{old}":', default=old)
        if not new or new == old or new in self.tags:
            return
        self.tags[new] = self.tags.pop(old)
        for row in self.__dict__.get("all_rows", []):
            if row[4] == old:
                row[4] = new
        save_tags(self.tags)
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
        if not messagebox.askyesno("Confirm", f'Remove tag "{tag}"?'):
            return
        del self.tags[tag]
        for row in self.__dict__.get("all_rows", []):
            if row[4] == tag:
                row[4] = self.natag
        save_tags(self.tags)
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
        keyword = simple_input(self, "New Keyword", "Keyword:")
        if not keyword:
            return
        self.tags[tag].setdefault("keywords", []).append(keyword)
        save_tags(self.tags)
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
        new = simple_input(self, "Edit Keyword", f'New value for keyword "{old}":', default=old)
        if not new or new == old:
            return
        self.tags[tag]["keywords"][index] = new
        save_tags(self.tags)
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
        if not messagebox.askyesno("Confirm", f'Remove keyword "{keyword}"?'):
            return
        del self.tags[tag]["keywords"][index]
        save_tags(self.tags)
        self.load_tag_details()
        self._set_status(f'Removed keyword from "{tag}"')

    def save_tags_from_view(self):
        if not self.save_current_tag_limit():
            return
        save_tags(self.tags)
        self._refresh_tag_filter_options()
        self._set_status("Saved tags")

    def browse_pdf(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        if files:
            self.pdf_files = list(files)
            self.file_label_var.set(build_file_label(self.pdf_files))
            self.status_var.set(f"{len(self.pdf_files)} PDF file(s) selected")

    def clear_pdfs(self):
        self.pdf_files = []
        self.file_label_var.set(build_file_label(self.pdf_files))
        self.status_var.set("No PDFs selected")

    def load(self):
        if not self.pdf_files:
            messagebox.showwarning('No File', 'Please select one or more PDF files.')
            return
        self.all_rows = []
        self.status_var.set("Processing PDFs...")
        self.update_idletasks()
        for pdf in self.pdf_files:
            try:
                raw = process_purchases(pdf)
                for d, desc, amt, cur, tag, _ in raw:
                    self.all_rows.append([d, desc, f"{float(amt):,.2f}", cur, tag])
            except Exception as e:
                messagebox.showerror('Error', f'{os.path.basename(pdf)}: {e}')
        self.apply_filter()
        self.status_var.set(f"Loaded and tagged {len(self.all_rows)} purchases")

    def apply_filter(self):
        self._refresh_filter_options()
        selected_currency = self._var_value("currency_var", "All currencies")
        currencies = set() if selected_currency == "All currencies" else {selected_currency}
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
                self.visible_count_var.set(f"Showing {len(self.filtered_rows)} purchases")
            return
        for i in self.tree.get_children():
            self.tree.delete(i)
        for index, row in enumerate(self.filtered_rows):
            tags = ("odd",) if index % 2 else ("even",)
            iid = self.tree.insert('', 'end', values=row, tags=tags)
            self.tree_item_rows[iid] = row
        self.tree.tag_configure("even", background="#ffffff")
        self.tree.tag_configure("odd", background="#fafbfc")
        self._update_kpis()
        self.total_var.set(format_totals(self.filtered_rows))
        if "visible_count_var" in self.__dict__:
            self.visible_count_var.set(f"Showing {len(self.filtered_rows)} purchases")

    def reset_filters(self):
        self.search_var.set("")
        self.currency_var.set("All currencies")
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
        menu.add_command(label='New Tag…', command=lambda iid=iid: self.create_and_assign(iid))
        menu.tk_popup(event.x_root, event.y_root)

    def _row_for_item(self, item_iid):
        return self.tree_item_rows[item_iid]

    def assign_tag(self, item_iid, tag):
        row = self._row_for_item(item_iid)
        old_tag = row[4]
        row[4] = tag
        self.tree.item(item_iid, values=row)
        if old_tag == self.natag:
            desc = row[1]
            if desc not in self.tags[tag]["keywords"]:
                self.tags[tag]["keywords"].append(desc)
                save_tags(self.tags)
        if "all_rows" in self.__dict__:
            self.apply_filter()
            self._set_status(f'Assigned "{tag}" to purchase')

    def create_and_assign(self, item_iid):
        row = self._row_for_item(item_iid)
        desc = row[1]
        name = simple_input(self, 'New Tag', 'Enter new tag name:')
        if not name:
            return
        if name not in self.tags:
            self.tags[name] = {"keywords": [desc], "limit": 0}
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
            data = [(float(v.replace(',', '')), k) for v, k in data]
        else:
            data = [(v.lower(), k) for v, k in data]
        data.sort(reverse=reverse)
        for idx, (_, k) in enumerate(data):
            self.tree.move(k, '', idx)
        self.tree.heading(col, command=lambda _c=col: self.sort_column(_c, not reverse))

    def export_csv(self):
        if not self.filtered_rows:
            messagebox.showwarning('No Data', 'No rows to export.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')])
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['date', 'description', 'amount', 'currency', 'tag'])
                w.writerows(self.filtered_rows)
            messagebox.showinfo('Exported', f'Exported {len(self.filtered_rows)} rows to {path}')
        except Exception as e:
            messagebox.showerror('Error', str(e))

if __name__ == '__main__':
    PurchaseTaggerUI().mainloop()
