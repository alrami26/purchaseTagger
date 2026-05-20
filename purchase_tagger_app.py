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

class TagEditor(tk.Toplevel):
    def __init__(self, parent, tags):
        super().__init__(parent)
        self.title('Manage Tags')
        self.geometry('750x400')
        self.configure(bg='#FAFAFA')
        self.tags = tags
        self.current_tag = None   # ← para trackear la selección previa

        # Listas de tags y keywords
        self.tag_list = tk.Listbox(self, exportselection=False, bg='white', bd=1, relief='solid')
        self.tag_list.grid(row=0, column=0, sticky='ns', padx=10, pady=10)
        self.keyword_list = tk.Listbox(self, exportselection=False, bg='white', bd=1, relief='solid')
        self.keyword_list.grid(row=0, column=1, sticky='ns', padx=10, pady=10)

        # Entry editable para el límite
        ttk.Label(self, text='Limit:').grid(row=0, column=2, sticky='nw', padx=(20,5), pady=(10,0))
        self.limit_var = tk.StringVar(value='0')
        self.limit_entry = ttk.Entry(self, textvariable=self.limit_var, width=10)
        self.limit_entry.grid(row=0, column=2, sticky='nw', padx=(60,10), pady=(10,0))

        # Botones...
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.grid(row=1, column=0, columnspan=3)
        btns = [
            ('Add Tag', self.add_tag),
            ('Edit Tag', self.edit_tag),
            ('Remove Tag', self.remove_tag),
            ('Add Keyword', self.add_keyword),
            ('Edit Keyword', self.edit_keyword),
            ('Remove Keyword', self.remove_keyword),
            ('Save', self.save)
        ]
        for idx, (txt, cmd) in enumerate(btns):
            ttk.Button(btn_frame, text=txt, command=cmd).grid(row=0, column=idx, padx=5)

        for tag in self.tags:
            self.tag_list.insert('end', tag)
        # Ahora bind directo, pasando el evento
        self.tag_list.bind('<<ListboxSelect>>', self.load_keywords)

    def load_keywords(self, event=None):
        # ① Antes de cambiar de tag, salva el límite de la anterior
        if self.current_tag is not None:
            try:
                self.tags[self.current_tag]['limit'] = int(self.limit_var.get())
            except ValueError:
                pass

        sel = self.tag_list.curselection()
        if not sel:
            return
        tag = self.tag_list.get(sel[0])
        self.current_tag = tag

        # ② Cargar keywords
        self.keyword_list.delete(0, 'end')
        for kw in self.tags[tag]["keywords"]:
            self.keyword_list.insert('end', kw)
        # ③ Precargar el límite en el Entry
        self.limit_var.set(str(self.tags[tag]["limit"]))

    def add_tag(self):
        name = simple_input(self, 'New Tag', 'Tag name:')
        if name and name not in self.tags:
            self.tags[name] = {"keywords": [], "limit": 0}
            self.tag_list.insert('end', name)

    def edit_tag(self):
        sel = self.tag_list.curselection()
        if not sel:
            return
        idx = sel[0]
        old = self.tag_list.get(idx)
        new = simple_input(self, 'Edit Tag', f'New name for tag "{old}":', default=old)
        if new and new != old and new not in self.tags:
            self.tags[new] = self.tags.pop(old)
            self.tag_list.delete(idx)
            self.tag_list.insert(idx, new)
            self.tag_list.selection_set(idx)

    def remove_tag(self):
        sel = self.tag_list.curselection()
        if not sel:
            return
        idx = sel[0]
        tag = self.tag_list.get(idx)
        if messagebox.askyesno('Confirm', f'Remove tag "{tag}"?'):
            del self.tags[tag]
            self.tag_list.delete(idx)
            self.keyword_list.delete(0, 'end')

    def add_keyword(self):
        sel = self.tag_list.curselection()
        if not sel:
            return
        tag = self.tag_list.get(sel[0])
        kw = simple_input(self, 'New Keyword', 'Keyword:')
        if kw:
            self.tags[tag]["keywords"].append(kw)
            self.keyword_list.insert('end', kw)

    def edit_keyword(self):
        sel = self.tag_list.curselection()
        ksel = self.keyword_list.curselection()
        if not (sel and ksel):
            return
        tag = self.tag_list.get(sel[0])
        old = self.keyword_list.get(ksel[0])
        new = simple_input(self, 'Edit Keyword', f'New value for keyword "{old}":', default=old)
        if new and new != old:
            self.tags[tag]["keywords"][ksel[0]] = new
            self.keyword_list.delete(ksel[0])
            self.keyword_list.insert(ksel[0], new)
            self.keyword_list.selection_set(ksel[0])

    def edit_limit(self):
        sel = self.tag_list.curselection()
        if not sel:
            return
        tag = self.tag_list.get(sel[0])
        old = self.tags[tag]["limit"]
        new = simple_input(self, 'Edit Limit', f'New limit for "{tag}":', default=str(old))
        if new.isdigit():
            self.tags[tag]["limit"] = int(new)
            self.limit_var.set(new)

    def remove_keyword(self):
        sel = self.tag_list.curselection()
        ksel = self.keyword_list.curselection()
        if not (sel and ksel):
            return
        tag = self.tag_list.get(sel[0])
        kw = self.keyword_list.get(ksel[0])
        if messagebox.askyesno('Confirm', f'Remove keyword "{kw}"?'):
            self.tags[tag]["keywords"].remove(kw)
            self.keyword_list.delete(ksel[0])

    def save(self):
        # ④ Antes de cerrar, asegúrate de guardar el limit de la etiqueta actual
        if self.current_tag:
            try:
                self.tags[self.current_tag]['limit'] = int(self.limit_var.get())
            except ValueError:
                pass

        save_tags(self.tags)
        messagebox.showinfo('Saved', 'Tags (incluyendo límites) guardados en tags.json')
        self.destroy()

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

        for child in self.workspace.winfo_children():
            child.destroy()

        if view_name == "Imports":
            self._build_imports_view()
        elif view_name == "Purchases":
            self._build_purchases_view()
        elif view_name == "Summaries":
            self._build_summary_view()
        elif view_name == "Tags":
            self._build_tags_view()

    def _build_placeholder_view(self, title):
        ctk.CTkLabel(
            self.workspace,
            text=title,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#171a20",
        ).grid(row=0, column=0, sticky="w", padx=24, pady=24)

    def _build_imports_view(self):
        self._build_placeholder_view("Imports")

    def _build_purchases_view(self):
        self._build_placeholder_view("Purchases")

    def _build_summary_view(self):
        self._build_placeholder_view("Summaries")

    def _build_tags_view(self):
        self._build_placeholder_view("Tags")

    def open_tag_editor(self):
        TagEditor(self, self.tags)

    def browse_pdf(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        if files:
            self.pdf_files = list(files)
            if hasattr(self, "file_label_var"):
                self.file_label_var.set(build_file_label(self.pdf_files))
            if hasattr(self, "pdf_entry"):
                self.pdf_entry.delete(0, tk.END)
                self.pdf_entry.insert(0, "; ".join(os.path.basename(f) for f in files))

    def load(self):
        if not self.pdf_files:
            messagebox.showwarning('No File', 'Please select one or more PDF files.')
            return
        self.all_rows = []
        for pdf in self.pdf_files:
            try:
                raw = process_purchases(pdf)
                for d, desc, amt, cur, tag, _ in raw:
                    self.all_rows.append([d, desc, f"{float(amt):,.2f}", cur, tag])
            except Exception as e:
                messagebox.showerror('Error', f'{os.path.basename(pdf)}: {e}')
        self.apply_filter()
        messagebox.showinfo('Loaded', f'Loaded and tagged {len(self.all_rows)} purchases.')

    def apply_filter(self):
        text = self.search_var.get()
        selected_currency = getattr(self, "currency_var", tk.StringVar(value="All currencies")).get()
        currencies = None if selected_currency == "All currencies" else {selected_currency}
        month_key = getattr(self, "month_var", tk.StringVar(value=ALL_MONTHS)).get()
        tag_name = getattr(self, "tag_filter_var", tk.StringVar(value=ALL_TAGS)).get()
        self.filtered_rows = filter_purchase_rows(self.all_rows, text, currencies, month_key, tag_name)
        self.tree_item_rows.clear()
        if not hasattr(self, "tree"):
            self.total_var.set(format_totals(self.filtered_rows))
            stats = kpi_stats(self.all_rows, self.filtered_rows, self.tags, self.natag)
            for name, value in stats.items():
                if hasattr(self, "kpi_vars") and name in self.kpi_vars:
                    self.kpi_vars[name].set(str(value))
            return
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in self.filtered_rows:
            iid = self.tree.insert('', 'end', values=r)
            self.tree_item_rows[iid] = r
        self.total_var.set(format_totals(self.filtered_rows))
        stats = kpi_stats(self.all_rows, self.filtered_rows, self.tags, self.natag)
        for name, value in stats.items():
            if hasattr(self, "kpi_vars") and name in self.kpi_vars:
                self.kpi_vars[name].set(str(value))

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
        self.assign_tag(item_iid, name)

    def open_summary(self):
        """Show a summary window with selectable chart types and currency/month filters."""
        # 1️⃣ figure out which currencies appear
        rows = getattr(self, 'filtered_rows', []) or getattr(self, 'all_rows', [])
        self.apply_filter()
        currencies = sorted({r[3] for r in rows})
        self.cur_vars = {cur: tk.BooleanVar(value=True) for cur in currencies}

        # 2️⃣ chart options
        opts = ['Spend by Tag', 'Monthly Spend', 'Cumulative Spend', 'Límite vs Gasto por Tag', 'Gasto Promedio por Tag/Mes']

        # 3️⃣ build window
        win = tk.Toplevel(self)
        win.title('Summary')
        win.geometry('900x600')

        sel = tk.StringVar(value=opts[0])
        cb = ttk.Combobox(win, values=opts, textvariable=sel, state='readonly')
        cb.grid(row=0, column=0, padx=10, pady=10, sticky='w')

        # currency checkboxes
        cur_frame = ttk.LabelFrame(win, text="Currencies")
        cur_frame.grid(row=0, column=1, padx=10, pady=10, sticky='e')
        for i, cur in enumerate(currencies):
            ttk.Checkbutton(
                cur_frame,
                text=cur,
                variable=self.cur_vars[cur],
                command=lambda: draw()
            ).grid(row=0, column=i, padx=5)

        chart_frame = ttk.Frame(win)
        chart_frame.grid(row=1, column=0, columnspan=2, sticky='nsew')
        win.grid_rowconfigure(1, weight=1)
        win.grid_columnconfigure(0, weight=1)

        # months list
        rows = getattr(self, 'filtered_rows', []) or getattr(self, 'all_rows', [])
        opciones_mes = ['Todos'] + available_months(rows)

        # month filter
        self.month_var = tk.StringVar(value='Todos')
        ttk.Label(win, text="Mes:").grid(row=0, column=2, padx=(20, 5), sticky='w')
        ttk.Combobox(win, values=opciones_mes, textvariable=self.month_var, state='readonly', width=10) \
            .grid(row=0, column=3, padx=(0, 10), sticky='w')

        def draw():
            # clear old charts
            for w in chart_frame.winfo_children():
                w.destroy()

            # selected currencies
            selected = {cur for cur, var in self.cur_vars.items() if var.get()}
            if not selected:
                ttk.Label(chart_frame, text="No currencies selected.").pack()
                return

            ows = getattr(self, 'filtered_rows', []) or getattr(self, 'all_rows', [])
            sel_mes = self.month_var.get()

            data_rows = filter_rows_by_month(ows, sel_mes)

            # aggregates
            aggregates = summary_aggregates(data_rows, selected)
            tag_totals = aggregates["tag_totals"]
            monthly = aggregates["monthly_totals"]
            cumulative_points = aggregates["cumulative_points"]

            # plot choice
            choice = sel.get()
            if choice == 'Spend by Tag':
                fig, ax = plt.subplots(figsize=(5, 4))
                ax.pie(tag_totals.values(), labels=tag_totals.keys(), autopct='%1.1f%%')
                ax.set_title('Spend by Tag')

            elif choice == 'Monthly Spend':
                fig, ax = plt.subplots(figsize=(5, 4))
                ms = sorted(monthly.keys())
                ax.bar(ms, [monthly[m] for m in ms])
                ax.set_title('Monthly Spend')
                ax.set_xticklabels(ms, rotation=45)

            elif choice == 'Cumulative Spend':
                fig, ax = plt.subplots(figsize=(5, 4))
                xs = [date_label for date_label, _running in cumulative_points]
                ys = [running for _date_label, running in cumulative_points]
                ax.plot(xs, ys, marker='o')
                ax.set_title('Cumulative Spend Over Time')
                ax.set_xticklabels(xs, rotation=45)
                ax.set_ylabel('Total')

            elif choice == 'Límite vs Gasto por Tag':
                labels = list(tag_totals.keys())
                gastos = [tag_totals[tag] for tag in labels]
                limites = [self.tags.get(tag, {}).get('limit', 0) for tag in labels]

                fig, ax = plt.subplots(figsize=(6, 4))
                x = range(len(labels))
                ax.bar([i - 0.2 for i in x], gastos, width=0.4, label='Gasto')
                ax.bar([i + 0.2 for i in x], limites, width=0.4, label='Límite')
                ax.set_xticks(list(x))
                ax.set_xticklabels(labels, rotation=45, ha='right')
                ax.set_title('Comparación: Límite vs Gasto por Tag')
                ax.legend()


            elif choice == 'Gasto Promedio por Tag/Mes':

                # límites
                limits = {}
                try:
                    limits_data = load_tags()
                    limits = {t: info.get('limit', 0) for t, info in limits_data.items()}
                except Exception:
                    pass

                summary_data = average_spend_by_tag_month(data_rows, selected, limits)
                tag_totals = summary_data["tag_month_totals"]
                tag_global_totals = summary_data["tag_global_totals"]
                promedio_tag = summary_data["tag_average_by_month"]
                totals = summary_data["totals"]

                # columnas de detalle
                months = summary_data["months"]
                currencies_by_month = summary_data["currencies_by_month"]

                # tabla
                for w in chart_frame.winfo_children():
                    w.destroy()
                chart_frame.grid_rowconfigure(0, weight=1)
                chart_frame.grid_columnconfigure(0, weight=1)

                # 👇 añadimos "Tag Total"
                cols = ['Tag', 'Límite', 'Promedio', 'Tag Total'] + [f"{mk}_{cur}" for mk in months for cur in
                                                                     currencies_by_month[mk]]
                summary_tree = ttk.Treeview(chart_frame, columns=cols, show='headings')
                summary_tree.grid(row=0, column=0, sticky='nsew')

                vsb = ttk.Scrollbar(chart_frame, orient='vertical', command=summary_tree.yview)
                hsb = ttk.Scrollbar(chart_frame, orient='horizontal', command=summary_tree.xview)
                vsb.grid(row=0, column=1, sticky='ns')
                hsb.grid(row=1, column=0, sticky='ew')
                summary_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

                summary_tree.heading('Tag', text='Tag', anchor='w')
                summary_tree.column('Tag', width=120, anchor='w', stretch=True)
                summary_tree.heading('Límite', text='Límite', anchor='e')
                summary_tree.column('Límite', width=80, anchor='e', stretch=True)
                summary_tree.heading('Promedio', text='Promedio', anchor='e')
                summary_tree.column('Promedio', width=80, anchor='e', stretch=True)
                summary_tree.heading('Tag Total', text='Tag Total', anchor='e')
                summary_tree.column('Tag Total', width=100, anchor='e', stretch=True)

                for col in cols[4:]:
                    mk, cur = col.split('_')
                    mname = datetime.strptime(mk, '%Y-%m').strftime('%b %Y')
                    summary_tree.heading(col, text=f"{mname} {cur}", anchor='center')
                    summary_tree.column(col, width=80, anchor='e', stretch=True)

                summary_tree.tag_configure('over_limit', foreground='red')

                for tg in sorted(tag_totals):
                    lim = limits.get(tg, 0)
                    prom = promedio_tag.get(tg, 0)
                    total_tag = tag_global_totals.get(tg, 0)
                    lim_text = f"{lim:,.2f}"
                    prom_text = f"{prom:,.2f}" if prom else ''
                    total_text = f"{total_tag:,.2f}" if total_tag else ''
                    detalle_vals = [
                        f"{tag_totals[tg].get(mk, {}).get(cur):,.2f}" if tag_totals[tg].get(mk, {}).get(cur) else ''
                        for mk in months for cur in currencies_by_month[mk]
                    ]
                    tags_row = ['over_limit'] if summary_data["over_limit_by_tag"].get(tg) else []
                    summary_tree.insert('', 'end', values=[tg, lim_text, prom_text, total_text, *detalle_vals],
                                        tags=tags_row)

                sum_lim = summary_data["total_limit"]
                sum_prom = summary_data["total_average"]
                sum_total = summary_data["total_spend"]
                total_detail = [
                    f"{totals.get(mk, {}).get(cur):,.2f}" if totals.get(mk, {}).get(cur) else ''
                    for mk in months for cur in currencies_by_month[mk]
                ]
                total_tags = ['over_limit'] if summary_data["total_over_limit"] else []
                summary_tree.insert('', 'end', values=[
                    'Total', f"{sum_lim:,.2f}", f"{sum_prom:,.2f}", f"{sum_total:,.2f}", *total_detail
                ], tags=total_tags)

                chart_frame.update_idletasks()

            if choice in ['Spend by Tag','Monthly Spend','Cumulative Spend','Límite vs Gasto por Tag']:
                FigureCanvasTkAgg(fig, master=chart_frame).get_tk_widget().pack(fill='both', expand=True)

        self.month_var.trace_add('write', lambda *a: draw())
        cb.bind('<<ComboboxSelected>>', lambda e: draw())
        draw()

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
