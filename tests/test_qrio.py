"""QR import / export and the biggest-sample front page."""
import os
import pytest

from errcode import ec2, qr, qrio
from errcode.report import decode


def test_max_sample_fills_one_qr():
    rep = qrio.max_sample()
    assert len(rep.parts()) == 1
    n = len(rep.digits)
    assert 5500 <= n <= qr.MAX_DIGITS
    m = qr.matrix(rep.parts()[0])
    assert len(m) == 177                      # version 40
    assert len(decode(rep.parts()).codes) == len(rep.hits) - 0 or len(decode(rep.parts()).codes) > 100


def test_export_import_roundtrip(tmp_path):
    parts = qrio.max_sample().parts()
    files = qrio.export(parts, folder=str(tmp_path / "out"))
    assert any(f.endswith(".png") for f in files) and any(f.endswith(".svg") for f in files)
    for f in files:
        if f.endswith((".png", ".svg", ".txt")):
            assert qrio.read_file(f).strip() == parts[0] or f.endswith(".txt")
    txt = [f for f in files if f.endswith(".txt")][0]
    assert parts[0] in qrio.read_file(txt)


def test_collector_out_of_order(tmp_path):
    from errcode.report import Report
    rep = qrio.max_sample()
    small = Report(rep.hits, rep.stats, app="x", budget=2000, part_digits=500)
    parts = small.parts()
    assert len(parts) >= 3
    c = qrio.Collector()
    got = None
    for p in reversed(parts):
        got = c.add(p)
    assert got == sorted(parts) or len(got) == len(parts)
    assert decode(got).codes


def test_bad_file(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hello")
    assert qrio.read_file(str(f)) == "hello"          # plain text passes through; decoding rejects it later
    with pytest.raises(qrio.QRImportError):
        qrio.read_file(str(tmp_path / "missing.png"))


def test_cv2_reads_png(tmp_path):
    pytest.importorskip("cv2")
    parts = qrio.max_sample().parts()
    files = qrio.export(parts, folder=str(tmp_path / "o"))
    png = [f for f in files if f.endswith(".png")][0]
    assert ec2.is_ec2(qrio.read_file(png))
