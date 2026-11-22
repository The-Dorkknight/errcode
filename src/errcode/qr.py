# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""QR output. Uses the tiny pure-Python 'segno' package (no Pillow, no numpy), so it
stays light enough for old hardware. If segno is missing everything else in
errcode still works; QR calls raise QRUnavailable and callers can fall back to
showing the text code.
"""
from __future__ import annotations

import io
import re
from typing import List


MAX_DIGITS = 5584        # most digits one standard QR holds at level M (version 40, 177 x 177 modules), with the 'EC2-' header


class QRUnavailable(RuntimeError):
    pass


_ALNUM = re.compile(r"^[0-9A-Z $%*+\-./:]*$")
_TAIL_DIGITS = re.compile(r"\d{6,}$")


def segments(payload: str):
    """Split 'EC2-1234...' (or a link ending in digits) into QR segments: the header in
    alphanumeric (or byte) mode, the digits in numeric mode - 3.33 bits per digit
    instead of 5.5 or 8. Returns [(text, mode name)]."""
    m = _TAIL_DIGITS.search(payload)
    if not m or m.start() == 0:
        return [(payload, None)]
    head, digits = payload[:m.start()], m.group(0)
    return [(head, "alphanumeric" if _ALNUM.match(head) else "byte"), (digits, "numeric")]


def _make(payload: str):
    try:
        import segno
        from segno import consts
    except ImportError:
        raise QRUnavailable("QR needs the 'segno' package: pip install segno")
    modes = {"alphanumeric": consts.MODE_ALPHANUMERIC, "byte": consts.MODE_BYTE, "numeric": consts.MODE_NUMERIC}
    segs = segments(payload)
    content = payload if len(segs) == 1 else [(t, modes[m]) for t, m in segs]
    # Standard (not Micro) QR so every phone camera reads it; level M suits on-screen scanning.
    return segno.make(content, error="m", micro=False)


def version(payload: str) -> int:
    """QR version (1-40) the payload needs; size is 17 + 4 * version modules."""
    return _make(payload).version


def available() -> bool:
    try:
        import segno  # noqa: F401
        return True
    except ImportError:
        return False


def matrix(payload: str) -> List[List[int]]:
    """Dark/light modules as rows of 0/1, without the quiet-zone border."""
    return [list(row) for row in _make(payload).matrix]


def save(payload: str, path: str, scale: int = 8) -> None:
    """Write PNG/SVG (chosen by file extension) with the standard 4-module quiet zone."""
    _make(payload).save(path, scale=scale, border=4)


def terminal(payload: str) -> str:
    """Block-character QR for a console (works over SSH)."""
    buf = io.StringIO()
    _make(payload).terminal(out=buf, compact=True)
    return buf.getvalue()
