# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""ErrCode window built with TK 4K (https://github.com/The-Dorkknight/tk4k): the practical test of the toolkit.

Same features as the tkinter window in gui.py: paste or open a log, analyse, ranked codes (worst first,
coloured), detail, QR code (multi-part), time bar, quick codes, EC2 text, copy, save QR, decode.
The UI is TK 4K (SDL3 + Dear ImGui); the library underneath is unchanged.
"""
from __future__ import annotations

import os
import time
from datetime import datetime

import tk4k as ui

from . import __build_date__, __version_label__, codec, ec2, qr, qrio, table
from .detect import ScanStats, scan_text
from .envcheck import machine_check
from .report import DECODER_URL, DEFAULT_BUDGET, PAGE_BUDGET, SEV_LETTER, Report, decode
from .samples import SAMPLES

SEV_COLOURS = {3: "#e5384f", 2: "#e0701a", 1: "#c9a227", 0: "#2e9e55"}  # readable on dark and light themes
TK4K_LINE = "UI: TK 4K %s (built %s)" % (ui.__version__, ui.__build_date__)


class ErrCodeApp:
    """All state lives here so tests can drive it without a mouse."""

    def __init__(self, size=(1180, 800), theme: str | None = None):
        self.report: Report | None = None
        self.cur_parts: list[str] = []          # the QR parts on show: from the last analysis or an import
        self.collector = qrio.Collector()       # QR parts imported one at a time
        self.part = 0
        self.rows: list[tuple[str, str]] = []  # (message, fix) per table row
        self.title = "ErrCode %s (Built %s) - WORK IN PROGRESS  |  UI: TK 4K %s" % (
            __version_label__, __build_date__, ui.__version__)
        self.log = ui.Var("")
        self.path = ui.Var("")
        self.decode_in = ui.Var("")
        self.payload = ui.Var("")
        self.quick = ui.Var("")
        self.when = ui.Var("No report yet")
        self.part_text = ui.Var("")
        self.note = ui.Var("")
        self.qr_title = ui.Var("3. QR code (scan with a phone camera)")
        self.import_path = ui.Var("")
        self.link = ui.Var(False)
        self.page = ui.Var(False)
        self.status = ui.Var("v%s (WIP)  |  built %s  |  launched %s" % (
            __version_label__, __build_date__, datetime.now().strftime("%Y-%m-%d %H:%M")))
        samples = ["Load a sample..."] + list(SAMPLES)
        with ui.Window(self.title, size=size) as win:
            self.win = win
            if theme:
                win.set_theme(theme)
            with ui.Row(gap=12):
                ui.Label("ErrCode", color="#4f9dff")
                ui.Label("-  error codes you can read off a QR code", dim=True)
            ui.Label(TK4K_LINE + "  -  this window is built with TK 4K, a small modern Tk-shaped toolkit", dim=True)
            ui.Separator()
            with ui.Grid(columns=2, weights=[10, 9]):
                with ui.Column():
                    ui.Label("1. Paste a log, traceback or console output")
                    self.log_box = ui.TextArea(var=self.log, height=440, wrap=False)
                    with ui.Row():
                        self.samples = ui.Dropdown(samples, index=0, width=320, on_change=self.load_sample)
                        ui.Button("Analyse", self.analyse, primary=True)
                    with ui.Row():
                        ui.Button("Check this machine", self.check_machine)
                        ui.Button("Clear", self.clear)
                    with ui.Row():
                        ui.Entry(var=self.path, hint="path of a log file to open", width=380,
                                 on_submit=lambda _t: self.open_file())
                        ui.Button("Open file", self.open_file)
                    ui.Label("QR files", dim=True)
                    with ui.Row():
                        ui.Entry(var=self.import_path, hint="QR image, .txt or .svg to import (blank: choose a file)", width=380,
                                 on_submit=lambda _t: self.import_qr())
                        ui.Button("Import QR", self.import_qr)
                    with ui.Row():
                        ui.Button("Export QR files", self.export_qr)
                        ui.Button("Biggest sample QR", self.load_max_sample)
                with ui.Column():
                    ui.Label("Decode a report, QR text or quick codes (E102 W706)")
                    with ui.Row():
                        ui.Entry(var=self.decode_in, hint="EC2-... or E102 W706", width=330,
                                 on_submit=lambda _t: self.decode_entry())
                        ui.Button("Decode", self.decode_entry)
                    ui.Label("2. Codes - worst first")
                    self.tree = ui.Table(["Code", "Level", "Dictionary entry [detail]"], height=150,
                                         weights=[0.5, 0.6, 2.4], on_select=self.show_detail)
                    self.detail_var = ui.Var("")
                    ui.Label(self.detail_var, wrap=True)
                    ui.Label(self.qr_title, wrap=True)
                    ui.Label(self.when, color="#4f9dff")
                    with ui.Row(gap=14):
                        self.qr = ui.QRView(px=4.0, quiet=3)
                        with ui.Column():
                            ui.Label(self.quick, color="#4f9dff")
                            ui.Entry(var=self.payload, readonly=True, width=215)
                            with ui.Row():
                                ui.Button("Copy", self.copy_payload)
                                ui.Button("Save QR", self.save_qr)
                            with ui.Row():
                                self.prev_btn = ui.Button("<", lambda: self.step_part(-1), width=34)
                                ui.Label(self.part_text)
                                self.next_btn = ui.Button(">", lambda: self.step_part(1), width=34)
                            ui.Checkbox("QR opens decoder page", var=self.link,
                                        on_change=lambda _v: self.redraw())
                            ui.Checkbox("Page-sized (4000 digits)", var=self.page,
                                        on_change=lambda _v: self.analyse())
                    ui.Label(self.note, wrap=True, dim=True)
            ui.Separator()
            with ui.Row():
                ui.Label(self.status, dim=True)
        self.win.title = self.title
        self.load_max_sample()           # the front page opens on the biggest QR one report can fill

    # ---- actions (same behaviour as gui.py) -------------------------------------------------
    def load_sample(self, index=None, _name=None) -> None:
        i = self.samples.index
        if i <= 0:
            return
        self.log.set(SAMPLES[self.samples.items[i]])
        self.analyse()

    def open_file(self) -> None:
        p = os.path.expanduser(self.path.get().strip().strip('"'))
        if not p:  # no path typed: TK 4K's in-app file chooser (no native dialog yet)
            self.win.ask_open_file(self._chosen, start=os.getcwd(), title="Open a log file")
            return
        try:
            with open(p, "r", errors="replace") as fh:
                self.log.set(fh.read())
        except OSError as exc:
            self.win.toast("Cannot open: %s" % exc)
            self.status.set("Cannot open %s: %s" % (p, exc))
            return
        self.analyse()

    def _chosen(self, path) -> None:
        if path:
            self.path.set(path)
            self.open_file()

    def clear(self) -> None:
        self.log.set("")
        self.tree.set_rows([])
        self.rows = []
        self.detail_var.set("")
        self.qr.set_matrix([])
        for v in (self.payload, self.quick, self.part_text, self.note):
            v.set("")
        self.when.set("No report yet")
        self.qr_title.set("3. QR code (scan with a phone camera)")
        self.report, self.cur_parts = None, []

    def _budget(self) -> int:
        return PAGE_BUDGET if self.page.get() else DEFAULT_BUDGET

    def analyse(self) -> None:
        text = self.log.get()
        if not text.strip():
            self.win.toast("Paste a log or open a file first")
            return
        hits, stats = scan_text(text)
        self.show_report(Report(hits, stats, app="errcode-demo", budget=self._budget()))

    def check_machine(self) -> None:
        self.show_report(Report(machine_check(), ScanStats(), app="errcode-demo", budget=self._budget()))

    def decode_entry(self) -> None:
        self._import_text(self.decode_in.get(), "the decode box")

    def _show_decoded(self, dec, where: str) -> None:
        self._fill([(d.code, d.sev, d.key + ("  [%s]" % d.detail if d.detail not in (None, "") else ""),
                     d.message + (" (x%d)" % d.count if d.count > 1 else ""), d.fix) for d in dec.codes])
        when = ("Decoded report made %s (session %s%s)" % (codec.format_when(dec.when), dec.session,
                                                          ", app %s" % dec.app if dec.app else "")
                if dec.when else "Decoded codes")
        if dec.when:
            self.when.set("Decoded: " + codec.format_when(dec.when))
        self.quick.set(" ".join("%s%s" % (SEV_LETTER[d.sev], d.code) for d in dec.codes))
        self.status.set("%s - from %s" % (when, where))
        return when

    def _import_text(self, text: str, where: str) -> None:
        """Decode report text from the decode box or an imported file; QR parts can arrive one at a time."""
        text = text.strip()
        if not text:
            self.win.toast("Nothing to decode")
            return
        try:
            if not ec2.is_ec2(text):                                      # quick codes, EC1 ...
                dec = decode(text)
                when = self._show_decoded(dec, where)
                self.note.set(when + ". (The QR is still the last one shown.)")
                return
            parts = self.collector.add(text)
            if parts is None:
                self.note.set("Imported from %s - %s. Import the other parts too." % (where, self.collector.missing))
                self.status.set(self.collector.missing)
                self.win.toast("Part received")
                return
            dec = decode(parts)
        except (codec.CodecError, ec2.EC2Error) as exc:
            self.win.toast("Cannot decode: %s" % exc)
            self.note.set("Cannot decode: %s" % exc)
            return
        when = self._show_decoded(dec, where)
        self.report, self.cur_parts, self.part = None, parts, 0
        self.qr_title.set("3. QR code - imported from %s (Export QR files writes it out again)" % where)
        self.redraw()
        self.note.set("%s. %s" % (when, self.note.get()))

    # ---- import / export of QR files -------------------------------------------------------------
    def import_qr(self) -> None:
        p = self.import_path.get().strip()
        if not p:   # no path typed: TK 4K's in-app file chooser
            self.win.ask_open_file(self._import_chosen, start=os.getcwd(), title="Import a QR image, .svg or .txt file")
            return
        self._import_file(p)

    def _import_chosen(self, path) -> None:
        if path:
            self.import_path.set(path)
            self._import_file(path)

    def _import_file(self, path: str) -> None:
        try:
            text = qrio.read_file(path)
        except (qrio.QRImportError, OSError) as exc:
            self.win.toast("Cannot import: %s" % exc)
            self.note.set("Cannot import: %s" % exc)
            self.status.set("Import failed")
            return
        self._import_text(text, os.path.basename(os.path.expanduser(path.strip().strip('"'))))

    def export_qr(self) -> None:
        if not self.cur_parts:
            self.win.toast("Nothing to export yet - analyse a log or import a report first")
            return
        try:
            files = qrio.export(self.cur_parts, quick=self.quick.get(), when=self.when.get())
        except (qr.QRUnavailable, OSError) as exc:
            self.win.toast("Cannot export: %s" % exc)
            self.note.set("Cannot export: %s" % exc)
            return
        folder = os.path.dirname(files[0])
        self.status.set("Exported %d files to %s" % (len(files), folder))
        self.note.set("Exported %d QR part(s) as PNG and SVG, plus report.txt, to %s. Import QR reads them back." % (
            len(self.cur_parts), folder))
        self.win.toast("Exported to " + os.path.basename(folder))

    def load_max_sample(self) -> None:
        rep = qrio.max_sample()
        self.show_report(rep)
        self.qr_title.set("3. Sample QR: the biggest report one QR can hold (%d of %d digits, %d codes, QR version 40)" % (
            len(rep.digits), qr.MAX_DIGITS, len(rep.hits)))
        self.status.set("Sample report - paste a log and press Analyse for your own")

    def show_report(self, rep: Report) -> None:
        self.report, self.part = rep, 0
        self.cur_parts = rep.parts()
        self.qr_title.set("3. QR code (scan with a phone camera)")
        rows = []
        for h in rep.hits:
            det = "  [%s]" % h.detail if h.detail not in (None, "") else ""
            cnt = " (x%d)" % h.count if h.count > 1 else ""
            rows.append((h.entry.code3, h.sev, h.entry.key + det, h.entry.msg + cnt, h.entry.fix))
        self._fill(rows)
        self.quick.set(rep.quick)
        self.when.set(rep.when_text())
        self.redraw()
        extra = " +%d lower-priority left out to fit." % rep.omitted if rep.omitted else ""
        self.status.set("%s.%s" % (rep.stats.summary(), extra) if rep.stats.lines else "Machine check done.")

    def _fill(self, rows) -> None:
        self.rows = [(m, f) for _c, _s, _k, m, f in rows]
        self.tree.set_rows([(c, table.SEV_NAMES[s].upper(), k) for c, s, k, _m, _f in rows],
                           [SEV_COLOURS[s] for _c, s, _k, _m, _f in rows])
        if rows:
            self.tree.selected = 0
            self.show_detail(0)
        else:
            self.detail_var.set("")

    def show_detail(self, i: int) -> None:
        if 0 <= i < len(self.rows):
            msg, fix = self.rows[i]
            self.detail_var.set(msg + ("\n\nFix: " + fix if fix else ""))

    def step_part(self, delta: int) -> None:
        if self.cur_parts:
            self.part = (self.part + delta) % len(self.cur_parts)
            self.redraw()

    def redraw(self) -> None:
        parts = self.cur_parts
        if not parts:
            return
        self.part = min(self.part, len(parts) - 1)
        content = DECODER_URL + parts[self.part] if self.link.get() else parts[self.part]
        self.payload.set(parts[self.part])
        many = len(parts) > 1
        self.part_text.set("QR part %d of %d" % (self.part + 1, len(parts)) if many else "one QR")
        self.prev_btn.enabled = self.next_btn.enabled = many
        try:
            m = qr.matrix(content)
        except qr.QRUnavailable as exc:
            self.qr.set_matrix([])
            self.note.set("%s  The text code still works." % exc)
            return
        self.qr.px = max(2.0, min(5.0, 190.0 / (len(m) + 6)))
        self.qr.set_matrix(m)
        n = len(m)
        digits = sum(len(ec2.find(q.upper())[0][3]) for q in parts)
        self.note.set("%d digits in the whole report; this QR is %dx%d modules (version %d)%s." % (
            digits, n, n, (n - 17) // 4, " - links to the decoder page" if self.link.get() else ""))

    def copy_payload(self) -> None:
        text = self.report.payload if self.report else "\n".join(self.cur_parts) or self.payload.get()
        ui.set_clipboard(text)
        self.status.set("Copied the full report (%d characters)" % len(text))
        self.win.toast("Copied")

    def save_qr(self) -> None:
        if not self.cur_parts:
            self.win.toast("Nothing to save yet - analyse a log first")
            return
        path = os.path.join(os.getcwd(), "errcode-qr-%s.png" % time.strftime("%Y%m%d-%H%M%S"))
        try:
            part = self.cur_parts[min(self.part, len(self.cur_parts) - 1)]
            qr.save(DECODER_URL + part if self.link.get() else part, path)
        except qr.QRUnavailable as exc:
            self.win.toast("QR unavailable: %s" % exc)
            return
        except OSError as exc:
            self.win.toast("Cannot save: %s" % exc)
            return
        self.status.set("Saved %s" % path)
        self.win.toast("Saved " + os.path.basename(path))


def main() -> None:
    ErrCodeApp().win.run()


if __name__ == "__main__":
    main()
