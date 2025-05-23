#!/usr/bin/env python3
import json
import csv
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from purchase_extractor import process_purchases
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import Counter
from datetime import datetime

TAG_FILE = 'tags.json'

def load_tags(path=TAG_FILE):
    """
    Carga tags desde JSON, migrando el formato antiguo (lista de keywords)
    al nuevo: { tag: { "keywords": [...], "limit": int } }.
    """
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    migrated = {}
    for tag, v in data.items():
        if isinstance(v, list):
            migrated[tag] = {"keywords": v, "limit": 0}
        else:
            migrated[tag] = {
                "keywords": v.get("keywords", []),
                "limit": v.get("limit", 0)
            }
    return migrated
# Migración de tags asegurada :contentReference[oaicite:0]{index=0}

def save_tags(tags, path=TAG_FILE):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(tags, f, indent=2)

def tag_purchase(description, tags, natag='N/A'):
    desc_upper = description.upper()
    for tag, info in tags.items():
        for kw in info["keywords"]:
            if kw.upper() in desc_upper:
                return tag
    return natag
# Ahora usa info["keywords"] para búsqueda :contentReference[oaicite:1]{index=1}

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
# Input pre-cargado con default :contentReference[oaicite:2]{index=2}

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
# Interfaz de edición con límite :contentReference[oaicite:3]{index=3}

class PurchaseTaggerUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF Purchase Tagger")
        self.geometry("900x600")
        self.configure(bg='#FAFAFA')
        ttk.Style(self).theme_use('clam')

        self.pdf_files = []
        self.tags = load_tags()
        self.natag = 'N/A'

        menubar = tk.Menu(self, bg='#FAFAFA')
        tm = tk.Menu(menubar, tearoff=0)
        tm.add_command(label='Manage Tags…', command=self.open_tag_editor)
        menubar.add_cascade(label='Tags', menu=tm)
        self.config(menu=menubar)

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill='x')
        ttk.Label(frm, text="PDF Files:").grid(row=0, column=0, sticky='e')
        self.pdf_entry = ttk.Entry(frm, width=50)
        self.pdf_entry.grid(row=0, column=1, padx=5)
        ttk.Button(frm, text='Browse', command=self.browse_pdf).grid(row=0, column=2)
        ttk.Button(frm, text='Load & Tag', command=self.load).grid(row=0, column=3, padx=5)
        ttk.Button(frm, text='Summary', command=self.open_summary).grid(row=0, column=4, padx=5)
        ttk.Label(frm, text="Search:").grid(row=1, column=0, sticky='e')
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *a: self.apply_filter())
        ttk.Entry(frm, textvariable=self.search_var, width=30).grid(row=1, column=1, padx=5)
        ttk.Button(frm, text='Export', command=self.export_csv).grid(row=1, column=3)

        cols = ('date', 'description', 'amount', 'currency', 'tag')
        self.tree = ttk.Treeview(self, columns=cols, show='headings')
        for c in cols:
            self.tree.heading(c, text=c.title(), command=lambda _col=c: self.sort_column(_col, False))
            self.tree.column(c, width=100 if c not in ('description','amount') else 250)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Button-3>', self.on_right_click)
        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set)
        self.all_rows = []
        self.filtered_rows = []

        self.total_var = tk.StringVar(value="Totals: 0.00")
        ttk.Label(self, textvariable=self.total_var, font=('Roboto',12,'bold'), background='#FAFAFA')\
            .pack(side='bottom', anchor='e', padx=10, pady=5)

    def open_tag_editor(self):
        TagEditor(self, self.tags)

    def browse_pdf(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        if files:
            self.pdf_files = list(files)
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
        text = self.search_var.get().lower()
        self.filtered_rows = [r for r in self.all_rows if not text or text in ' '.join(r).lower()]
        for i in self.tree.get_children():
            self.tree.delete(i)
        totals = {}
        for r in self.filtered_rows:
            self.tree.insert('', 'end', values=r)
            try:
                amt = float(r[2].replace(',', ''))
                cur = r[3]
                totals[cur] = totals.get(cur,0.0) + amt
            except:
                pass
        parts = [f"{cur} {amt:,.2f}" for cur,amt in sorted(totals.items())]
        self.total_var.set(f"Totals by currency: {'; '.join(parts) if parts else '0.00'}")

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

    def assign_tag(self, item_iid, tag):
        idx = self.tree.index(item_iid)
        row = self.filtered_rows[idx]
        old_tag = row[4]
        row[4] = tag
        self.tree.item(item_iid, values=row)
        if old_tag == self.natag:
            desc = row[1]
            if desc not in self.tags[tag]["keywords"]:
                self.tags[tag]["keywords"].append(desc)
                save_tags(self.tags)
    # Al reasignar de N/A, persiste keyword :contentReference[oaicite:4]{index=4}

    def create_and_assign(self, item_iid):
        idx = self.tree.index(item_iid)
        desc = self.filtered_rows[idx][1]
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
        """Show a summary window with three selectable chart types and currency filters."""
        # 1️⃣ Figure out which currencies appear in the filtered rows
        rows = getattr(self, 'filtered_rows', []) or getattr(self, 'all_rows', [])
        self.apply_filter()
        currencies = sorted({r[3] for r in rows})
        self.cur_vars = {cur: tk.BooleanVar(value=True) for cur in currencies}

        # 2️⃣ Chart‐type options
        opts = ['Spend by Tag', 'Monthly Spend', 'Cumulative Spend', 'Límite vs Gasto por Tag', 'Gasto Promedio por Tag/Mes']


        # 3️⃣ Build the window
        win = tk.Toplevel(self)
        win.title('Summary')
        win.geometry('900x600')

        sel = tk.StringVar(value=opts[0])
        cb = ttk.Combobox(win, values=opts, textvariable=sel, state='readonly')
        cb.grid(row=0, column=0, padx=10, pady=10, sticky='w')

        # Currency checkboxes
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

        # 4️⃣ The draw() function now recomputes everything each time
        def draw():
            # clear old charts
            for w in chart_frame.winfo_children():
                w.destroy()

            # figure out which currencies are checked
            selected = {cur for cur, var in self.cur_vars.items() if var.get()}
            if not selected:
                ttk.Label(chart_frame, text="No currencies selected.").pack()
                return

            # re-aggregate based on selection
            tag_totals = Counter()
            monthly = Counter()
            daily = Counter()
            month_map = {
                'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
                'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
            }

            for date_str, desc, amt, cur, tag in self.filtered_rows:
                if cur not in selected:
                    continue
                amt_f = float(amt.replace(',', ''))
                tag_totals[tag] += amt_f

                m = re.match(r"(\d{2})-([A-Z]{3})-(\d{2})", date_str)
                if m:
                    day, mon, yr = m.groups()
                    dt = datetime(int('20' + yr), month_map[mon], int(day))
                    monthly[dt.strftime('%Y-%m')] += amt_f
                    daily[dt] += amt_f

            # now plot the chosen chart
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
                dates = sorted(daily.keys())
                running = 0.0
                xs, ys = [], []
                for dt in dates:
                    running += daily[dt]
                    xs.append(dt.strftime('%Y-%m-%d'))
                    ys.append(running)
                ax.plot(xs, ys, marker='o')
                ax.set_title('Cumulative Spend Over Time')
                ax.set_xticklabels(xs, rotation=45)
                ax.set_ylabel('Total')
            elif choice == 'Límite vs Gasto por Tag':
                # ① Calcular gasto total por tag (ya lo hacemos en tag_totals)
                # ② Obtener el límite desde self.tags
                labels = list(tag_totals.keys())
                gastos = [tag_totals[tag] for tag in labels]
                limites = [self.tags.get(tag, {}).get('limit', 0) for tag in labels]

                fig, ax = plt.subplots(figsize=(6, 4))
                x = range(len(labels))
                # Barras lado a lado: gasto y límite
                ax.bar([i - 0.2 for i in x], gastos, width=0.4, label='Gasto')
                ax.bar([i + 0.2 for i in x], limites, width=0.4, label='Límite')
                ax.set_xticks(x)
                ax.set_xticklabels(labels, rotation=45, ha='right')
                ax.set_title('Comparación: Límite vs Gasto por Tag')
                ax.legend()
            elif choice == 'Gasto Promedio por Tag/Mes':
                # ① Preparar datos (agrupación, promedio y totales)
                data, avg, totals = {}, {}, {}
                for date_str, desc, amt, cur, tag in self.filtered_rows:
                    if cur not in selected: continue
                    try:
                        val = float(amt.replace(',', ''))
                    except ValueError:
                        continue
                    m = re.match(r"(\d{2})-([A-Z]{3})-(\d{2})", date_str)
                    if not m: continue
                    day, mon, yr = m.groups()
                    dt = datetime(int('20' + yr), month_map[mon], int(day))
                    mk = dt.strftime('%Y-%m')
                    data.setdefault((mk, cur), {}).setdefault(tag, []).append(val)
                # Calcular promedios y totales
                for (mk, cur), tags in data.items():
                    for tg, vals in tags.items():
                        avg.setdefault(tg, {}).setdefault(mk, {})[cur] = sum(vals) / len(vals)
                    totals.setdefault(mk, {})[cur] = sum(sum(vals) for vals in tags.values())
                # Meses y monedas
                months = sorted({mk for mk, _ in data.keys()})
                currencies_by_month = {mk: sorted({c for (m2, c) in data.keys() if m2 == mk}) for mk in months}

                # ② Limpiar frame y permitir expansión completa
                for w in chart_frame.winfo_children(): w.destroy()
                chart_frame.grid_rowconfigure(0, weight=1)
                chart_frame.grid_rowconfigure(1, weight=0)
                chart_frame.grid_columnconfigure(0, weight=1)

                # ③ Crear Treeview (un único encabezado) sin altura fija
                cols = ['Tag'] + [f"{mk}_{cur}" for mk in months for cur in currencies_by_month[mk]]
                summary_tree = ttk.Treeview(
                    chart_frame,
                    columns=cols,
                    show='headings'
                )
                summary_tree.grid(row=0, column=0, sticky='nsew')

                # ④ Scrollbars
                vsb = ttk.Scrollbar(chart_frame, orient='vertical', command=summary_tree.yview)
                hsb = ttk.Scrollbar(chart_frame, orient='horizontal', command=summary_tree.xview)
                vsb.grid(row=0, column=1, sticky='ns')
                hsb.grid(row=1, column=0, sticky='ew')
                summary_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

                # ⑤ Configurar encabezados (Mes Moneda en un solo renglón)
                summary_tree.heading('Tag', text='Tag', anchor='w')
                summary_tree.column('Tag', width=120, anchor='w', stretch=True)
                for col in cols[1:]:
                    mk, cur = col.split('_')
                    mname = datetime.strptime(mk, '%Y-%m').strftime('%b %Y')
                    summary_tree.heading(col, text=f"{mname} {cur}", anchor='center')
                    summary_tree.column(col, width=80, anchor='e', stretch=True)

                # ⑥ Insertar datos por Tag
                for tg in sorted(avg):
                    row = [tg] + [
                        f"{avg[tg].get(mk, {}).get(cur):,.2f}" if avg[tg].get(mk, {}).get(cur) else ''
                        for mk in months for cur in currencies_by_month[mk]
                    ]
                    summary_tree.insert('', 'end', values=row)

                # ⑦ Fila Total
                total_row = ['Total'] + [
                    f"{totals.get(mk, {}).get(cur):,.2f}" if totals.get(mk, {}).get(cur) else ''
                    for mk in months for cur in currencies_by_month[mk]
                ]
                summary_tree.insert('', 'end', values=total_row)

                # ⑧ Forzar expansión en la grilla
                chart_frame.update_idletasks()

            if choice in ['Spend by Tag','Monthly Spend','Cumulative Spend','Límite vs Gasto por Tag']:
                FigureCanvasTkAgg(fig, master=chart_frame).get_tk_widget().pack(fill='both', expand=True)

        # 5️⃣ Wire up and draw initially
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
