# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Export a report as QR files and import one back.

Export writes, for every QR part, a PNG and an SVG (the report text is stored inside the file too) and one
report.txt with all the parts. Import accepts any of those, a text file with EC2 text, or - if OpenCV is installed -
a photo or screenshot of any QR code. Without OpenCV, files written by Export still import exactly (the text rides
inside the PNG/SVG), and a phone camera can scan the QR and the text can be pasted into the decode box.
"""
from __future__ import annotations

import os
import re
import struct
import time
import zlib
from typing import List, Optional

from . import ec2, qr, table
from .detect import Hit, ScanStats
from .report import Report

PNG_KEY = "errcode"
# the largest plain EC2 report one QR can hold: standard QR, level M, version 40 = 177 x 177 modules
MAX_QR_DIGITS = 5580        # 279 blocks of 20; segno fits 5,584 digits at version 40 with the 'EC2-' header


class QRImportError(ValueError):
    pass


def max_sample() -> Report:
    """A real, decodable report that fills one QR to the brim (about 5,570 of the 5,584 digits a QR can take)."""
    ents = [e for e in table.ENTRIES if e.code and e.key != "GEN.OK"][:200]
    mods = ["numpy", "scipy", "open3d", "trimesh", "serial", "usb.core", "/dev/ttyUSB0", "libGL.so.1", "192.168.1.50",
            "printer.cfg", "esp32s3", "firmware.bin", "moonraker", "heater_bed"]
    hits = [Hit(e, 1 + (i * 7) % 900, 0, e.sev, (mods[i % len(mods)] + "_" + str(i) * 3 + "_x" * 16)[:16])
            for i, e in enumerate(ents)]
    return Report(hits, ScanStats(lines=60000, noise=48000, repeats=9000), minute=None, session=1234,
                  app="errcode-max-sample", budget=MAX_QR_DIGITS, part_digits=MAX_QR_DIGITS)


# ---- export -----------------------------------------------------------------------
def _png_with_text(path: str, text: str) -> None:
    data = open(path, "rb").read()
    body = PNG_KEY.encode() + b"\0" + text.encode("latin-1", "replace")
    chunk = struct.pack(">I", len(body)) + b"tEXt" + body + struct.pack(">I", zlib.crc32(b"tEXt" + body) & 0xFFFFFFFF)
    i = data.rindex(b"IEND") - 4
    open(path, "wb").write(data[:i] + chunk + data[i:])


def export(parts: List[str], folder: Optional[str] = None, quick: str = "", when: str = "", scale: int = 8) -> List[str]:
    """Write part PNG + SVG files and report.txt into a new folder; returns the paths written."""
    folder = folder or os.path.join(os.getcwd(), "errcode-export-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(folder, exist_ok=True)
    out, n = [], len(parts)
    for i, p in enumerate(parts, 1):
        stem = os.path.join(folder, "errcode-qr-part%dof%d" % (i, n) if n > 1 else "errcode-qr")
        qr.save(p, stem + ".png", scale)
        _png_with_text(stem + ".png", p)
        qr._make(p).save(stem + ".svg", scale=scale, border=4, desc=p, title="ErrCode report, part %d of %d" % (i, n))
        out += [stem + ".png", stem + ".svg"]
    txt = os.path.join(folder, "report.txt")
    with open(txt, "w", encoding="utf-8") as fh:
        fh.write("ErrCode report%s\n%s\n%s\n\n" % (" (%d QR parts)" % n if n > 1 else "", when, quick))
        fh.write("\n".join(parts) + "\n")
    return out + [txt]


# ---- import -----------------------------------------------------------------------
def _png_text(data: bytes) -> Optional[str]:
    i = 8
    while i + 8 <= len(data):
        ln, kind = struct.unpack(">I4s", data[i:i + 8])
        if kind == b"tEXt":
            key, _, val = data[i + 8:i + 8 + ln].partition(b"\0")
            if key == PNG_KEY.encode():
                return val.decode("latin-1")
        i += 12 + ln
    return None


def _read_image(path: str) -> str:
    data = open(path, "rb").read()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        t = _png_text(data)
        if t:
            return t
    try:
        import cv2  # optional: reads photos and screenshots of any QR code
    except ImportError:
        raise QRImportError("This image was not made by ErrCode's Export, and reading other QR images needs OpenCV "
                            "(pip install opencv-python-headless). Or scan it with a phone camera and paste the text "
                            "into the decode box.")
    img = cv2.imread(path)
    if img is None:
        raise QRImportError("Cannot read %s as an image." % os.path.basename(path))
    det = cv2.QRCodeDetector()
    for attempt in (img, cv2.copyMakeBorder(img, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(255, 255, 255))):
        text = det.detectAndDecode(attempt)[0]
        if text:
            return text
    raise QRImportError("No QR code found in %s." % os.path.basename(path))


def read_file(path: str) -> str:
    """The EC2 text held in a PNG/SVG written by Export, a photo/screenshot of a QR (OpenCV), or a text file."""
    path = os.path.expanduser(path.strip().strip('"'))
    if not os.path.isfile(path):
        raise QRImportError("File not found: %s" % path)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"):
        return _read_image(path)
    raw = open(path, "r", encoding="utf-8", errors="replace").read()
    if ext == ".svg":
        m = re.search(r"<desc[^>]*>(.*?)</desc>", raw, re.S)
        if m:
            return m.group(1).strip()
    if not ec2.is_ec2(raw) and not raw.strip():
        raise QRImportError("%s is empty." % os.path.basename(path))
    return raw


class Collector:
    """Gathers QR parts imported one at a time until the report is complete."""

    def __init__(self):
        self.parts: List[str] = []

    def add(self, text: str) -> Optional[List[str]]:
        """Add text (one or several parts). Returns the complete list of part strings, or None while parts are missing
        (see .missing). Raises ec2.EC2Error if there is no report in the text."""
        new = [m.group(0).strip() for m in re.finditer(r"EC2[/\-][^\sEe]*(?:[ \t]*[\d\-_.]+)*", text.upper())] \
            if "EC2/" in text.upper() else [text.strip()]
        pieces = ec2.find(" ".join(new).upper())
        if not pieces:
            raise ec2.EC2Error("no EC2 report found")
        if len(pieces) == 1 and pieces[0][1] == 1:          # a whole single-QR report replaces anything pending
            self.parts = []
            return [new[0] if new[0].upper().startswith("EC2") else text.strip()]
        keep = [p for p in self.parts if ec2.find(p.upper())[0][2] == pieces[0][2]]
        self.parts = keep + new
        try:
            ec2.join_parts(self.parts)
        except ec2.EC2Error as exc:
            if "still need" in str(exc):
                self.missing = str(exc)
                return None
            raise
        done, self.parts = self.parts, []
        return sorted(done, key=lambda s: ec2.find(s.upper())[0][0])
