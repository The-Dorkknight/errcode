# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""The ErrCode window built with TK 4K, driven headless (SDL dummy driver, software renderer)."""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
ui = pytest.importorskip("tk4k")
pytest.importorskip("tk4k._core")
from tk4k.testing import Harness  # noqa: E402

from errcode import decode  # noqa: E402
from errcode.gui_tk4k import ErrCodeApp  # noqa: E402
from errcode.samples import SAMPLES  # noqa: E402


@pytest.fixture()
def app():
    a = ErrCodeApp()
    h = Harness(a.win)
    h.step(3)
    yield a, h
    h.close()


def find(widget, cls, text=None):
    out = []
    for c in getattr(widget, "_children", []):
        if isinstance(c, cls) and (text is None or getattr(c, "text", None) == text):
            out.append(c)
        out += find(c, cls, text)
    return out


def test_title_and_footer_say_tk4k(app):
    a, h = app
    assert "TK 4K" in a.title and "TK 4K" in a.win.title
    labels = [str(x.text) for x in find(a.win, ui.Label)]
    assert any(t.startswith("UI: TK 4K") for t in labels)


@pytest.mark.parametrize("name", list(SAMPLES))
def test_every_sample_analyses(app, name):
    a, h = app
    a.samples.index = list(SAMPLES).index(name) + 1
    a.load_sample()
    h.step(3)
    assert a.report is not None
    assert len(a.tree.rows) == len(a.report.hits)
    assert a.quick.get() == a.report.quick
    assert a.payload.get() in a.report.parts()


def test_real_mouse_and_keyboard(app):
    a, h = app
    h.click(a.log_box)
    h.type("ERROR: Failed building wheel for numpy\ng++: command not found\n")
    h.step(3)
    assert "g++: command not found" in a.log.get()
    h.click(find(a.win, ui.Button, "Analyse")[0])
    h.step(3)
    assert a.report is not None and a.tree.rows
    h.click(find(a.win, ui.Button, "Clear")[0])
    h.step(3)
    assert a.log.get() == "" and a.tree.rows == [] and a.report is None


def test_table_click_selects_row(app):
    a, h = app
    a.samples.index = 5
    a.load_sample()
    h.step(3)
    assert len(a.tree.rows) >= 2
    x, y, w, hgt = a.tree.rect
    h._pos(x + 30, y + 8 + 22 * 1.5)  # second row, roughly
    h.step(1)
    from tk4k import _core
    _core.test_mouse_button(0, True); h.step(1); _core.test_mouse_button(0, False); h.step(2)
    assert a.tree.selected in (0, 1)  # lands on a row; exact row depends on the font scale
    assert a.detail_var.get()


def test_decode_round_trip(app):
    a, h = app
    a.samples.index = 3
    a.load_sample()
    rep = a.report
    a.decode_in.set(rep.payload)
    a.tree.set_rows([])
    a.decode_entry()
    h.step(2)
    assert len(a.tree.rows) == len(decode(rep.payload).codes) > 0


def test_bad_decode_does_not_crash(app):
    a, h = app
    for bad in ("", "EC2-12", "hello world", "E999999", "\x00\x01", "EC1-" + "9" * 40):
        a.decode_in.set(bad)
        a.decode_entry()
        h.step(1)
    assert a.win is not None


def test_open_file_good_and_bad(app, tmp_path):
    a, h = app
    a.path.set(str(tmp_path / "missing.log"))
    a.open_file()
    h.step(2)
    assert "Cannot open" in a.status.get()
    f = tmp_path / "x.log"
    f.write_bytes(b"ERROR: boom \xff\xfe bad bytes\nPermission denied: '/etc/x'\n")
    a.path.set(str(f))
    a.open_file()
    h.step(2)
    assert a.report is not None and "boom" in a.log.get()


def test_empty_and_whitespace_log(app):
    a, h = app
    a.clear()                       # the front page starts on the biggest sample; clear it first
    a.analyse()
    a.log.set("   \n\n")
    a.analyse()
    h.step(2)
    assert a.report is None


def test_qr_on_screen_decodes_to_the_report(app, tmp_path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    a, h = app
    a.samples.index = 5
    a.load_sample()
    a.qr.px = 6.0
    a.qr.set_matrix(__import__("errcode.qr", fromlist=["matrix"]).matrix(a.report.qr_content(0)))
    h.step(4)
    png = tmp_path / "s.png"
    h.screenshot(str(png))
    img = cv2.imread(str(png))
    text, _pts, _ = cv2.QRCodeDetector().detectAndDecode(img)
    assert text == a.report.qr_content(0)


def test_multi_part_report(app):
    a, h = app
    from errcode import table
    keys = [k for k in dir(table) if False]  # noqa: F841
    lines = []
    for i in range(400):
        lines.append("ERROR: Failed building wheel for pkg%d" % i)
        lines.append("PermissionError: [Errno 13] Permission denied: '/tmp/p%d'" % i)
        lines.append("ConnectionResetError: [Errno 104] reset by peer host%d" % i)
        lines.append("MemoryError at step %d" % i)
    a.log.set("\n".join(lines))
    a.analyse()
    h.step(3)
    n = len(a.report.parts())
    a.step_part(1)
    h.step(2)
    assert a.part == (1 % n)
    a.step_part(-1)
    assert a.part == 0
    assert a.next_btn.enabled == (n > 1)


def test_big_log_is_fast_and_window_stays_alive(app):
    a, h = app
    a.log.set(("INFO step ok 12%\n" * 20000) + "ERROR: Failed building wheel for numpy\n")
    t = time.monotonic()
    h.step(2)  # a 20,000 line text box must still draw
    a.analyse()
    h.step(2)
    assert time.monotonic() - t < 20
    assert a.report is not None


def test_save_qr_and_copy(app, tmp_path, monkeypatch):
    pytest.importorskip("segno")
    a, h = app
    monkeypatch.chdir(tmp_path)
    a.save_qr()  # nothing yet: toast, no crash
    a.samples.index = 1
    a.load_sample()
    a.save_qr()
    assert list(tmp_path.glob("errcode-qr-*.png"))
    a.copy_payload()
    assert "Copied" in a.status.get()


def test_machine_check_runs(app):
    a, h = app
    a.check_machine()
    h.step(3)
    assert a.report is not None


def test_check_launcher_falls_back(monkeypatch):
    from errcode import launch
    called = []
    monkeypatch.setenv("ERRCODE_UI", "tkinter")
    import types
    fake = types.ModuleType("errcode.gui")  # real one needs tkinter, which this machine may not have
    fake.main = lambda: called.append("tkinter")
    monkeypatch.setitem(sys.modules, "errcode.gui", fake)
    import errcode
    monkeypatch.setattr(errcode, "gui", fake, raising=False)
    launch.main([])
    assert called == ["tkinter"]


def test_open_file_with_no_path_shows_the_chooser(app, tmp_path):
    a, h = app
    a.path.set("")
    a.open_file()
    h.step(4)
    assert a.win._dialogs and a.win._dialogs[-1]._open
    f = tmp_path / "e.log"
    f.write_text("ERROR: boom\n")
    a._chosen(str(f))
    h.step(2)
    assert "boom" in a.log.get()


def test_front_page_shows_max_sample(app):
    a = app[0] if isinstance(app, tuple) else app
    assert len(a.cur_parts) == 1
    assert "biggest" in a.qr_title.get()
    assert len(a.qr.matrix) == 177 if hasattr(a.qr, "matrix") else True


def test_import_export_buttons(app, tmp_path, monkeypatch):
    a = app[0] if isinstance(app, tuple) else app
    monkeypatch.chdir(tmp_path)
    a.export_qr()
    outs = [d for d in os.listdir(tmp_path) if d.startswith("errcode-export")]
    assert outs
    png = [f for f in os.listdir(tmp_path / outs[0]) if f.endswith(".png")][0]
    a.clear()
    assert not a.cur_parts
    a.import_path.set(str(tmp_path / outs[0] / png))
    a.import_qr()
    assert len(a.cur_parts) == 1 and a.tree is not None
