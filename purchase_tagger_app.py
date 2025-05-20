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
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_tags(tags, path=TAG_FILE):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(tags, f, indent=2)

def tag_purchase(description, tags, natag='N/A'):
    desc_upper = description.upper()
    for tag, keywords in tags.items():
        for kw in keywords:
            if kw.upper() in desc_upper:
                return tag
    return natag

def simple_input(parent, title, prompt):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.geometry('300x100')
    dlg.configure(bg='#FAFAFA')
    ttk.Label(dlg, text=prompt).pack(pady=5)
    entry = ttk.Entry(dlg)
    entry.pack(padx=10)
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
        self.geometry('650x400')
        self.configure(bg='#FAFAFA')
        self.tags = tags

        self.tag_list = tk.Listbox(self, exportselection=False, bg='white', bd=1, relief='solid')
        self.tag_list.grid(row=0, column=0, sticky='ns', padx=10, pady=10)
        self.keyword_list = tk.Listbox(self, exportselection=False, bg='white', bd=1, relief='solid')
        self.keyword_list.grid(row=0, column=1, sticky='ns', padx=10, pady=10)

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.grid(row=1, column=0, columnspan=2)
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
        self.tag_list.bind('<<ListboxSelect>>', lambda e: self.load_keywords())

    def load_keywords(self):
        sel = self.tag_list.curselection()
        if not sel:
            return
        self.keyword_list.delete(0, 'end')
        tag = self.tag_list.get(sel[0])
        for kw in self.tags.get(tag, []):
            self.keyword_list.insert('end', kw)

    def add_tag(self):
        name = simple_input(self, 'New Tag', 'Tag name:')
        if name and name not in self.tags:
            self.tags[name] = []
            self.tag_list.insert('end', name)

    def edit_tag(self):
        sel = self.tag_list.curselection()
        if not sel:
            return
        idx = sel[0]
        old = self.tag_list.get(idx)
        new = simple_input(self, 'Edit Tag', f'New name for tag "{old}":')
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
            self.tags[tag].append(kw)
            self.keyword_list.insert('end', kw)

    def edit_keyword(self):
        sel = self.tag_list.curselection()
        ksel = self.keyword_list.curselection()
        if not (sel and ksel):
            return
        tag = self.tag_list.get(sel[0])
        old = self.keyword_list.get(ksel[0])
        new = simple_input(self, 'Edit Keyword', f'New value for keyword "{old}":')
        if new and new != old:
            self.tags[tag][ksel[0]] = new
            self.keyword_list.delete(ksel[0])
            self.keyword_list.insert(ksel[0], new)
            self.keyword_list.selection_set(ksel[0])

    def remove_keyword(self):
        sel = self.tag_list.curselection()
        ksel = self.keyword_list.curselection()
        if not (sel and ksel):
            return
        tag = self.tag_list.get(sel[0])
        kw = self.keyword_list.get(ksel[0])
        if messagebox.askyesno('Confirm', f'Remove keyword "{kw}"?'):
            self.tags[tag].remove(kw)
            self.keyword_list.delete(ksel[0])

    def save(self):
        save_tags(self.tags)
        messagebox.showinfo('Saved', 'Tags saved to tags.json')
        self.destroy()

class PurchaseTaggerUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF Purchase Tagger")
        self.geometry("900x600")
        self.configure(bg='#FAFAFA')
        ttk.Style(self).theme_use('clam')

        # allow multiple PDF selection
        self.pdf_files = []
        # initialize tags and default tag
        self.tags = load_tags()
        self.natag = 'N/A'

        menubar = tk.Menu(self, bg='#FAFAFA')
        tm = tk.Menu(menubar, tearoff=0)
        tm.add_command(label='Manage Tags...', command=self.open_tag_editor)
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
            self.tree.column(c, width=100 if c not in ('description', 'amount') else 250)
        self.tree.pack(fill='both', expand=True)
        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set)

        self.total_var = tk.StringVar(value="Total: 0.00")
        ttk.Label(self, textvariable=self.total_var, font=('Roboto', 12, 'bold'), background='#FAFAFA')\
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
                for d, desc, amt, cur in raw:
                    tag = tag_purchase(desc, self.tags, self.natag)
                    self.all_rows.append([d, desc, f"{float(amt):,.2f}", cur, tag])
            except Exception as e:
                messagebox.showerror('Error', f'{os.path.basename(pdf)}: {e}')
        self.apply_filter()
        messagebox.showinfo('Loaded', f'Loaded and tagged {len(self.all_rows)} purchases from {len(self.pdf_files)} files.')

    def apply_filter(self):
        text = self.search_var.get().lower()
        self.filtered_rows = [r for r in self.all_rows if not text or text in ' '.join(r).lower()]
        for i in self.tree.get_children():
            self.tree.delete(i)
        total = 0.0
        for r in self.filtered_rows:
            self.tree.insert('', 'end', values=r)
            try:
                total += float(r[2].replace(',', ''))
            except:
                pass
        self.total_var.set(f"Total: {total:,.2f}")

    def open_summary(self):
        """Show a summary window with three selectable chart types."""
        # precompute our three data series:
        tag_totals = Counter()
        monthly = Counter()
        daily = Counter()
        month_map = {
            'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
        }
        for date_str, desc, amt, cur, tag in self.filtered_rows:
            amt_f = float(amt.replace(',', ''))
            tag_totals[tag] += amt_f

            m = re.match(r"(\d{2})-([A-Z]{3})-(\d{2})", date_str)
            if not m:
                continue
            day, mon, yr = m.groups()
            dt = datetime(int('20' + yr), month_map[mon], int(day))
            monthly[dt.strftime('%Y-%m')] += amt_f
            daily[dt] += amt_f

        # prepare the window
        win = tk.Toplevel(self)
        win.title('Summary')
        win.geometry('900x600')

        # row/column 0 will be our combo + chart; we'll grid charts into row=1
        opts = ['Spend by Tag', 'Monthly Spend', 'Cumulative Spend']
        sel = tk.StringVar(value=opts[0])
        cb = ttk.Combobox(win, values=opts, textvariable=sel, state='readonly')
        cb.grid(row=0, column=0, padx=10, pady=10, sticky='w')

        chart_frame = ttk.Frame(win)
        chart_frame.grid(row=1, column=0, columnspan=2, sticky='nsew')
        win.grid_rowconfigure(1, weight=1)
        win.grid_columnconfigure(0, weight=1)

        def draw():
            # clear out any old charts
            for w in chart_frame.winfo_children():
                w.destroy()

            choice = sel.get()
            if choice == 'Spend by Tag':
                fig, ax = plt.subplots(figsize=(5, 4))
                ax.pie(tag_totals.values(), labels=tag_totals.keys(), autopct='%1.1f%%')
                ax.set_title('Spend by Tag')

            elif choice == 'Monthly Spend':
                fig, ax = plt.subplots(figsize=(5, 4))
                months = sorted(monthly.keys())
                ax.bar(months, [monthly[m] for m in months])
                ax.set_title('Monthly Spend')
                ax.set_xticklabels(months, rotation=45)

            else:  # Cumulative Spend
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

            # embed
            FigureCanvasTkAgg(fig, master=chart_frame).get_tk_widget().pack(fill='both', expand=True)

        # redraw whenever they pick a new option
        cb.bind('<<ComboboxSelected>>', lambda e: draw())
        # initial draw
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
