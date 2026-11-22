# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""The plug-in surface: drop one line into any Python program.

    import errcode
    errcode.install(app="stl2step")        # that's it

After install():
  * uncaught exceptions (main thread and worker threads) are recorded
  * logging records at WARNING and above are recorded (INFO/DEBUG chatter ignored)
  * when the program ends - or crashes - a compact footer is printed to stderr:
        [errcode myprog] E102 W706  EC2-34739023820496821288...
        [errcode myprog]   102  ERROR PY.TK_MISSING  Python's Tk GUI toolkit (tkinter) is not installed.
  * you can also call errcode.record("HW.GPU_FALLBACK"), errcode.run([...]) for
    subprocesses, and errcode.report() to get the Report (digits, QR, text)
  * your own codes: errcode.define_app(1, "NO_SCANNER", errcode.table.ERROR, "Scanner not found")
    then errcode.record("APP.NO_SCANNER") -> code 901

It never raises into the host program, and ERRCODE_QUIET=1 silences the footer.
"""
from __future__ import annotations

import atexit
import logging
import os
import subprocess
import sys
import threading
from typing import Dict, List, Optional

from . import codec, detect, table
from .detect import Hit, ScanStats
from .report import Report


class Collector:
    """Accumulates findings over the life of a process."""

    def __init__(self) -> None:
        self._hits: Dict[str, Hit] = {}
        self._stats = ScanStats()
        self._event = 0
        self._lock = threading.Lock()
        self.session = codec.new_session()
        self.app: Optional[str] = None

    def _add(self, hits: List[Hit], stats: Optional[ScanStats] = None) -> None:
        with self._lock:
            self._event += 1
            base = self._event * 1000000       # later events rank after earlier ones
            detect.merge(self._hits, [Hit(h.entry, h.count, base + max(h.first, 0), h.sev, h.detail) for h in hits])
            if stats:
                self._stats.lines += stats.lines
                self._stats.noise += stats.noise
                self._stats.repeats += stats.repeats

    def add_text(self, text: str, unknown: bool = True, cap: Optional[int] = None) -> None:
        """Scan text; `cap` limits the severity of what it finds (e.g. a WARNING log record)."""
        hits, stats = detect.scan_text(text, unknown)
        if cap is not None:
            for h in hits:
                h.sev = min(h.sev, cap)
        self._add(hits, stats)

    def add_exception(self, exc: BaseException) -> None:
        self._add(detect.hits_from_exception(exc))

    def add_returncode(self, rc: Optional[int]) -> None:
        self._add(detect.hits_from_returncode(rc))

    def add_key(self, key: str, sev: Optional[int] = None, detail=None) -> None:
        self._add([detect.hit_for_key(key, sev, detail)])

    def report(self, **kwargs) -> Report:
        with self._lock:
            hits = [Hit(h.entry, h.count, h.first, h.sev, h.detail) for h in self._hits.values()]
            stats = ScanStats(self._stats.lines, self._stats.noise, self._stats.repeats)
        kwargs.setdefault("app", self.app)
        return Report(hits, stats, session=self.session, **kwargs)

    def has_problem(self) -> bool:
        return self.report().worst >= table.WARN

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()
            self._stats = ScanStats()
            self._event = 0


_collector = Collector()
_state: Optional[dict] = None


def collector() -> Collector:
    return _collector


# ---- convenience API ------------------------------------------------------

def scan(text: str, **kwargs) -> Report:
    """Stateless: scan log text and return a Report (does not touch the collector).
    kwargs go to Report, e.g. budget=errcode.report.PAGE_BUDGET for a page-sized report."""
    hits, stats = detect.scan_text(text)
    return Report(hits, stats, **kwargs)


def from_exception(exc: BaseException, **kwargs) -> Report:
    return Report(detect.hits_from_exception(exc), **kwargs)


def record(key: str, sev: Optional[int] = None, detail=None) -> None:
    """Record an app-set code by dictionary key, e.g. record('HW.GPU_FALLBACK') or
    record('PY.MODULE_MISSING', detail='numpy'). The detail (short text or a number) travels in the report."""
    _collector.add_key(key, sev, detail)


def report(**kwargs) -> Report:
    return _collector.report(**kwargs)


def reset() -> None:
    _collector.clear()


def run(cmd, *, timeout: Optional[float] = None, **kwargs) -> "subprocess.CompletedProcess":
    """subprocess.run() that also feeds the output and exit code to the collector."""
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:
        _safe(_collector.add_exception, exc)
        raise
    _safe(_collector.add_text, (cp.stdout or "") + "\n" + (cp.stderr or ""))
    _safe(_collector.add_returncode, cp.returncode)
    return cp


def _safe(fn, *args) -> None:
    try:
        fn(*args)
    except Exception:       # the plug-in must never break the host program
        pass


# ---- hooks ----------------------------------------------------------------

class _LogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.exc_info and record.exc_info[1] is not None:
                _collector.add_exception(record.exc_info[1])
            is_error = record.levelno >= logging.ERROR
            _collector.add_text(record.getMessage(), unknown=is_error,
                                cap=None if is_error else table.WARN)
        except Exception:
            pass


def _emit() -> None:
    st = _state
    if not st or not st["show"] or os.environ.get("ERRCODE_QUIET"):
        return
    try:
        rep = _collector.report()
        if rep.worst < table.WARN or rep.codes == st["printed"]:
            return
        st["printed"] = rep.codes
        out = st["stream"] or sys.stderr
        tag = "[errcode%s] " % (" " + st["app"] if st["app"] else "")
        print(tag + rep.quick + "  " + rep.payload, file=out)
        for line in rep.lines():
            print(tag + "  " + line, file=out)
        top = next((h for h in rep.hits if h.entry.fix), None)
        if top is not None:
            print(tag + "  fix: " + top.entry.fix, file=out)
        if st["qr"]:
            try:
                print(rep.terminal_qr(), file=out)
            except Exception:
                pass
    except Exception:
        pass


def install(app: Optional[str] = None, *, level: int = logging.WARNING, at_exit: bool = True,
            show: bool = True, stream=None, qr: bool = False) -> Collector:
    """Hook uncaught exceptions, threads and logging; print one report footer at exit."""
    global _state
    if _state is not None:
        return _collector
    _collector.app = app
    handler = _LogHandler(level)
    logging.getLogger().addHandler(handler)
    prev_hook = sys.excepthook
    prev_thread = getattr(threading, "excepthook", None)

    def hook(etype, value, tb):
        if value is not None:
            _safe(_collector.add_exception, value)
        try:
            prev_hook(etype, value, tb)
        finally:
            _emit()

    def thread_hook(args):
        if args.exc_value is not None:
            _safe(_collector.add_exception, args.exc_value)
        if prev_thread:
            prev_thread(args)

    sys.excepthook = hook
    if prev_thread:
        threading.excepthook = thread_hook
    if at_exit:
        atexit.register(_emit)
    _state = {"handler": handler, "prev_hook": prev_hook, "prev_thread": prev_thread, "hook": hook,
              "thread_hook": thread_hook, "app": app, "show": show, "stream": stream, "qr": qr,
              "printed": None, "at_exit": at_exit}
    return _collector


def uninstall() -> None:
    """Undo install(); recorded findings are kept (see reset())."""
    global _state
    st = _state
    if st is None:
        return
    logging.getLogger().removeHandler(st["handler"])
    if sys.excepthook is st["hook"]:
        sys.excepthook = st["prev_hook"]
    if st["prev_thread"] and threading.excepthook is st["thread_hook"]:
        threading.excepthook = st["prev_thread"]
    if st["at_exit"]:
        atexit.unregister(_emit)
    _state = None
