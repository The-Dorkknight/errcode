# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Measure how much a log shrinks with each approach (errcode bench).

For each log it reports bytes as raw text, zlib -9, zlib -9 after noise removal,
zlib -9 with a preset dictionary, and the EC2 digits - plus the QR version each
needs at error level M (numeric mode for digits, byte mode for everything else).
A printed page is taken as 3000 characters of text or 4000 digits.
"""
from __future__ import annotations

import random
import zlib
from typing import Dict, List, Optional

from . import detect, table
from .report import PAGE_BUDGET, Report
from .samples import SAMPLES
from .words import WORDS

PAGE_TEXT = 3000          # characters of ordinary text on a printed page
PAGE_DIGITS = 4000        # digits on a printed page (5-digit groups, 10 pt)

# QR capacity at error level M, versions 1..40 (ISO/IEC 18004 table; checked against segno).
_NUM_M = [34, 63, 101, 149, 202, 255, 293, 365, 432, 513, 604, 691, 796, 871, 991, 1082, 1212, 1346, 1500, 1600,
          1708, 1872, 2059, 2188, 2395, 2544, 2701, 2857, 3035, 3289, 3486, 3693, 3909, 4134, 4343, 4588, 4775,
          5039, 5313, 5596]
_BYTE_M = [14, 26, 42, 62, 84, 106, 122, 152, 180, 213, 251, 287, 331, 362, 412, 450, 504, 560, 624, 666, 711,
           779, 857, 911, 997, 1059, 1125, 1190, 1264, 1370, 1452, 1538, 1628, 1722, 1809, 1911, 1989, 2099, 2213,
           2331]


def qr_version(n: int, numeric: bool) -> Optional[int]:
    table_ = _NUM_M if numeric else _BYTE_M
    for v, capn in enumerate(table_, 1):
        if n <= capn:
            return v
    return None


def _zdict() -> bytes:
    text = " ".join(WORDS) + " " + " ".join(e.msg for e in table.ENTRIES)
    return text.encode()[-32768:]


def _deflate(data: bytes, zdict: Optional[bytes] = None) -> int:
    c = zlib.compressobj(9, zlib.DEFLATED, -15, 9, zlib.Z_DEFAULT_STRATEGY, *( [zdict] if zdict else []))
    return len(c.compress(data) + c.flush())


def synthetic_log(lines: int = 20000, seed: int = 7) -> str:
    """A long, realistic-looking install/build/run log: mostly noise and repeats, a few real errors."""
    rnd = random.Random(seed)
    r = rnd.randint
    noise = [lambda: "Downloading numpy-1.26.%d-cp311-cp311-manylinux_2_17_x86_64.whl (%d.%d MB)" % (r(0, 4), r(1, 30), r(0, 9)),
             lambda: "     |%s| %d%%" % ("#" * r(1, 40), r(1, 99)),
             lambda: "Collecting package-%d" % r(1, 500),
             lambda: "Requirement already satisfied: pkg%d in ./venv/lib/python3.11/site-packages" % r(1, 500),
             lambda: "INFO: frame %d processed in %d ms" % (r(1, 99999), r(5, 80)),
             lambda: "[debug] tick %d queue=%d" % (r(1, 99999), r(0, 9)),
             lambda: "Get:%d http://archive.ubuntu.com/ubuntu noble/main amd64 libfoo%d amd64 [%d kB]" % (r(1, 300), r(1, 99), r(10, 900)),
             lambda: "Building wheel for thing-%d (pyproject.toml) ... done" % r(1, 50),
             lambda: "Stored in directory: /home/user/.cache/pip/wheels/%02x/%02x" % (r(0, 255), r(0, 255))]
    events = ["WARNING: Retrying (Retry(total=4)) after connection broken by 'ReadTimeoutError: Read timed out.'",
              "ModuleNotFoundError: No module named 'pyrealsense2'",
              "ImportError: libGL.so.1: cannot open shared object file: No such file or directory",
              "serial.serialutil.SerialException: could not open port /dev/ttyUSB0: [Errno 13] Permission denied: '/dev/ttyUSB0'",
              "Lost communication with MCU 'mcu'", "Heater extruder not heating at expected rate",
              "error: something odd happened in the frobnicator (code 77)",
              "Illegal instruction (core dumped)", "CUDA driver version is insufficient for CUDA runtime version"]
    out = []
    for _ in range(lines):
        out.append(rnd.choice(events) if rnd.random() < 0.002 else rnd.choice(noise)())
    return "\n".join(out)


def measure(name: str, text: str) -> Dict[str, object]:
    raw = text.encode("utf-8", "replace")
    kept, _counts, _stats = detect.clean_lines(text)
    filtered = "\n".join(kept).encode("utf-8", "replace")
    rep = Report(*detect.scan_text(text), budget=PAGE_BUDGET * 9, minute=0, session=0)
    digits = len(rep.digits)
    row = {"name": name, "lines": len(text.splitlines()), "raw": len(raw), "zlib": _deflate(raw),
           "zlib_filtered": _deflate(filtered), "zlib_dict": _deflate(filtered, _zdict()),
           "ec2_digits": digits, "events": len(rep.hits)}
    row["qr_raw"] = qr_version(row["raw"], False)
    row["qr_zlib_filtered"] = qr_version(row["zlib_filtered"], False)
    try:
        from . import qr
        row["qr_ec2"] = qr.version(rep.payload)            # real symbol: "EC2-" header + numeric digits
    except Exception:
        row["qr_ec2"] = qr_version(digits + 3, True)          # estimate without segno
    return row


def run(extra: Optional[Dict[str, str]] = None) -> List[Dict[str, object]]:
    logs = dict(SAMPLES)
    logs["synthetic 20,000-line log"] = synthetic_log()
    logs.update(extra or {})
    return [measure(n, t) for n, t in logs.items()]


def format_rows(rows: List[Dict[str, object]]) -> str:
    def v(x):
        return "-" if x is None else str(x)
    head = "%-34s %7s %8s %6s %8s %8s %6s %6s %6s %6s" % ("log", "lines", "raw B", "zlib", "filt+z", "dict+z",
                                                         "EC2 d", "codes", "QRraw", "QRec2")
    out = [head, "-" * len(head)]
    for r in rows:
        out.append("%-34s %7d %8d %6d %8d %8d %6d %6d %6s %6s" % (
            str(r["name"])[:34], r["lines"], r["raw"], r["zlib"], r["zlib_filtered"], r["zlib_dict"],
            r["ec2_digits"], r["events"], v(r["qr_raw"]), v(r["qr_ec2"])))
    out.append("raw/zlib columns are bytes; EC2 is digits. QR = version needed at level M (- = does not fit v40).")
    return "\n".join(out)
