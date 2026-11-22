# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Demo window for the errcode plug-in. The library does the work; this just shows it.

Paste a log -> ranked 3-digit codes (worst first, noise ignored) -> dictionary meaning
-> EC2 digits -> QR code (split into parts if it is big). Or paste a report on the right to decode it.
Pure tkinter + the pure-Python 'segno' QR package: no Pillow, no GPU, light on RAM.
"""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from . import __build_date__, __version_label__, codec, qr, table
from .detect import ScanStats, scan_text
from .envcheck import machine_check
from .report import DEFAULT_BUDGET, PAGE_BUDGET, Report, decode
from .samples import SAMPLES

SEV_COLOURS = {3: "#b00020", 2: "#c05600", 1: "#8a6d00", 0: "#1b7f3b"}
QR_PIXELS = 280


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ErrCode %s (Built %s) - WORK IN PROGRESS" % (__version_label__, __build_date__))
        self.geometry("1080x720")
        self.minsize(900, 600)
        self.report: Report = None
        self._rows = {}
        self._part = 0

        outer = ttk.Frame(self, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=3)
        outer.columnconfigure(1, weight=2)
        outer.rowconfigure(0, weight=1)

        # ---- left: log input --------------------------------------------
        left = ttk.LabelFrame(outer, text="1. Paste a log, traceback or console output", padding=6)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.log = tk.Text(left, wrap="none", undo=True, font=("TkFixedFont", 10))
        ys = ttk.Scrollbar(left, command=self.log.yview)
        xs = ttk.Scrollbar(left, orient="horizontal", command=self.log.xview)
        self.log.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")

        bar = ttk.Frame(left)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        bar.columnconfigure(0, weight=1)
        self.sample = ttk.Combobox(bar, state="readonly", values=list(SAMPLES))
        self.sample.set("Load a sample...")
        self.sample.bind("<<ComboboxSelected>>", self.load_sample)
        self.sample.grid(row=0, column=0, sticky="ew")
        ttk.Button(bar, text="Analyse", command=self.analyse).grid(row=0, column=1, padx=(8, 0))
        row2 = ttk.Frame(bar)
        row2.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(row2, text="Check this machine", command=self.check_machine).pack(side=tk.LEFT)
        ttk.Button(row2, text="Open log file...", command=self.open_file).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(row2, text="Clear", command=self.clear).pack(side=tk.RIGHT)

        # ---- right: results ---------------------------------------------
        right = ttk.Frame(outer)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        dec = ttk.LabelFrame(right, text="Decode a report, QR text or quick codes (E102 W706)", padding=6)
        dec.grid(row=0, column=0, sticky="ew")
        dec.columnconfigure(0, weight=1)
        self.dec_var = tk.StringVar()
        e = ttk.Entry(dec, textvariable=self.dec_var)
        e.grid(row=0, column=0, sticky="ew")
        e.bind("<Return>", lambda _e: self.decode_entry())
        ttk.Button(dec, text="Decode", command=self.decode_entry).grid(row=0, column=1, padx=(6, 0))

        res = ttk.LabelFrame(right, text="2. Codes - worst first", padding=6)
        res.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        res.columnconfigure(0, weight=1)
        res.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(res, columns=("code", "sev", "key"), show="headings", height=7, selectmode="browse")
        for col, text, w in (("code", "Code", 48), ("sev", "Level", 56), ("key", "Dictionary entry [detail]", 190)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, stretch=(col == "key"))
        for sev, colour in SEV_COLOURS.items():
            self.tree.tag_configure("s%d" % sev, foreground=colour)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.show_detail)
        self.detail = tk.Text(res, height=6, wrap="word", state="disabled", font=("TkDefaultFont", 10))
        self.detail.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        qrf = ttk.LabelFrame(right, text="3. QR code (scan with a phone camera)", padding=6)
        qrf.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        qrf.columnconfigure(1, weight=1)
        # time/date bar: the same stamp is multiplexed inside the QR string itself
        self.when_var = tk.StringVar(value="No report yet")
        ttk.Label(qrf, textvariable=self.when_var, relief="sunken", anchor="center", padding=(6, 3),
                  font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.canvas = tk.Canvas(qrf, width=QR_PIXELS // 2 + 20, height=QR_PIXELS // 2 + 20, bg="white",
                                highlightthickness=1, highlightbackground="#999")
        self.canvas.grid(row=1, column=0, rowspan=3, sticky="n")
        side = ttk.Frame(qrf)
        side.grid(row=1, column=1, sticky="new", padx=(10, 0))
        side.columnconfigure(0, weight=1)
        self.quick_var = tk.StringVar()
        ttk.Label(side, textvariable=self.quick_var, font=("TkFixedFont", 14, "bold"), wraplength=300).grid(
            row=0, column=0, sticky="w")
        self.payload_var = tk.StringVar()
        ttk.Entry(side, textvariable=self.payload_var, state="readonly", font=("TkFixedFont", 10)).grid(
            row=1, column=0, sticky="ew", pady=(4, 0))
        btns = ttk.Frame(side)
        btns.grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Button(btns, text="Copy", command=self.copy_payload).pack(side=tk.LEFT)
        ttk.Button(btns, text="Save QR...", command=self.save_qr).pack(side=tk.LEFT, padx=(6, 0))
        nav = ttk.Frame(side)
        nav.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.prev_btn = ttk.Button(nav, text="<", width=3, command=lambda: self.step_part(-1))
        self.next_btn = ttk.Button(nav, text=">", width=3, command=lambda: self.step_part(1))
        self.part_var = tk.StringVar()
        self.prev_btn.pack(side=tk.LEFT)
        ttk.Label(nav, textvariable=self.part_var, padding=(6, 0)).pack(side=tk.LEFT)
        self.next_btn.pack(side=tk.LEFT)
        self.link_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(side, text="QR opens the online decoder", variable=self.link_var,
                        command=self.redraw).grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.page_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(side, text="Page-sized report (up to 4000 digits)", variable=self.page_var,
                        command=self.analyse).grid(row=5, column=0, sticky="w")
        self.note = tk.StringVar()
        ttk.Label(qrf, textvariable=self.note, wraplength=420, justify="left").grid(
            row=2, column=0, columnspan=2, sticky="nw", pady=(6, 0))

        self.status = tk.StringVar(value="v%s (WIP)  |  built %s  |  launched %s" % (
            __version_label__, __build_date__, datetime.now().strftime("%Y-%m-%d %H:%M")))
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=(6, 2)).pack(
            side=tk.BOTTOM, fill=tk.X, before=outer)

    # ---- actions ------------------------------------------------------
    def load_sample(self, _event=None) -> None:
        self.log.delete("1.0", "end")
        self.log.insert("1.0", SAMPLES[self.sample.get()])
        self.analyse()

    def open_file(self) -> None:
        path = filedialog.askopenfilename(title="Open a log file")
        if path:
            with open(path, "r", errors="replace") as fh:
                self.log.delete("1.0", "end")
                self.log.insert("1.0", fh.read())
            self.analyse()

    def clear(self) -> None:
        self.log.delete("1.0", "end")
        self.tree.delete(*self.tree.get_children())
        self._set_detail("")
        self.canvas.delete("all")
        self.payload_var.set("")
        self.quick_var.set("")
        self.part_var.set("")
        self.when_var.set("No report yet")
        self.note.set("")

    def _budget(self) -> int:
        return PAGE_BUDGET if self.page_var.get() else DEFAULT_BUDGET

    def analyse(self) -> None:
        text = self.log.get("1.0", "end")
        if not text.strip() and self.report is None:
            return
        hits, stats = scan_text(text)
        self.show_report(Report(hits, stats, app="errcode-demo", budget=self._budget()))

    def check_machine(self) -> None:
        self.show_report(Report(machine_check(), ScanStats(), app="errcode-demo", budget=self._budget()))

    def decode_entry(self) -> None:
        try:
            dec = decode(self.dec_var.get())
        except codec.CodecError as exc:
            messagebox.showerror("Cannot decode", str(exc))
            return
        self._fill_tree([(d.code, d.sev, d.key + ("  [%s]" % d.detail if d.detail not in (None, "") else ""),
                          d.message + (" (x%d)" % d.count if d.count > 1 else ""), d.fix) for d in dec.codes])
        when = ("Decoded report made %s (session %s%s)" % (codec.format_when(dec.when), dec.session,
                                                          ", app %s" % dec.app if dec.app else "")
                if dec.when else "Decoded codes")
        if dec.when:
            self.when_var.set("Decoded: " + codec.format_when(dec.when))
        self.note.set(when + ". (The QR above is still the last analysed log.)")
        self.status.set(when)

    def show_report(self, rep: Report) -> None:
        self.report = rep
        self._part = 0
        rows = []
        for h in rep.hits:
            det = "  [%s]" % h.detail if h.detail not in (None, "") else ""
            cnt = " (x%d)" % h.count if h.count > 1 else ""
            rows.append((h.entry.code3, h.sev, h.entry.key + det, h.entry.msg + cnt, h.entry.fix))
        self._fill_tree(rows)
        self.quick_var.set(rep.quick)
        self.when_var.set(rep.when_text())
        self.redraw()
        extra = " +%d lower-priority left out to fit." % rep.omitted if rep.omitted else ""
        self.status.set("%s.%s" % (rep.stats.summary(), extra) if rep.stats.lines else "Machine check done.")

    def step_part(self, delta: int) -> None:
        if self.report:
            n = len(self.report.parts())
            self._part = (self._part + delta) % n
            self.redraw()

    def redraw(self) -> None:
        rep = self.report
        if not rep:
            return
        parts = rep.parts()
        self._part = min(self._part, len(parts) - 1)
        content = rep.qr_content(self._part, link=self.link_var.get())
        self.payload_var.set(parts[self._part])
        many = len(parts) > 1
        self.part_var.set("QR part %d of %d" % (self._part + 1, len(parts)) if many else "one QR")
        for b in (self.prev_btn, self.next_btn):
            b.state(["!disabled"] if many else ["disabled"])
        self._draw_qr(content, len(rep.digits))

    def _fill_tree(self, rows) -> None:
        self.tree.delete(*self.tree.get_children())
        self._rows = {}
        for code, sev, key, msg, fix in rows:
            iid = self.tree.insert("", "end", values=(code, table.SEV_NAMES[sev].upper(), key), tags=("s%d" % sev,))
            self._rows[iid] = (msg, fix)
        kids = self.tree.get_children()
        if kids:
            self.tree.selection_set(kids[0])

    def show_detail(self, _event=None) -> None:
        sel = self.tree.selection()
        if sel:
            msg, fix = self._rows[sel[0]]
            self._set_detail(msg + ("\n\nFix: " + fix if fix else ""))

    def _set_detail(self, text: str) -> None:
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def _draw_qr(self, payload: str, total_digits: int = 0) -> None:
        self.canvas.delete("all")
        try:
            m = qr.matrix(payload)
        except qr.QRUnavailable as exc:
            self.note.set("%s\nThe text code above still works." % exc)
            return
        n, quiet = len(m), 4
        px = max(2, (QR_PIXELS // 2 + 20) // (n + 2 * quiet))     # whole pixels per module keeps edges crisp
        self.canvas.configure(width=(n + 2 * quiet) * px, height=(n + 2 * quiet) * px)
        for y, row in enumerate(m):
            for x, dark in enumerate(row):
                if dark:
                    self.canvas.create_rectangle((x + quiet) * px, (y + quiet) * px,
                                                 (x + quiet + 1) * px, (y + quiet + 1) * px,
                                                 fill="black", outline="")
        self.note.set("%d digits in the whole report; this QR is %dx%d modules (version %d)%s." % (
            total_digits, n, n, (n - 17) // 4,
            " - links to the decoder page" if self.link_var.get() else ""))

    def copy_payload(self) -> None:
        self.clipboard_clear()
        text = self.report.payload if self.report else self.payload_var.get()
        self.clipboard_append(text)
        self.status.set("Copied the full report (%d characters)" % len(text))

    def save_qr(self) -> None:
        if not self.report:
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG image", "*.png"), ("SVG", "*.svg")])
        if path:
            try:
                self.report.save_qr(path, part=self._part, link=self.link_var.get())
                self.status.set("Saved %s" % path)
            except qr.QRUnavailable as exc:
                messagebox.showerror("QR unavailable", str(exc))


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
