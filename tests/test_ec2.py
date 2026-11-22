# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Tests for v0.2: 3-digit codes, details, the EC2 digit format, budgets, parts, decoders."""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import errcode                                         # noqa: E402
from errcode import cli, codec, detect, ec2, qr, table  # noqa: E402
from errcode.report import PAGE_BUDGET               # noqa: E402
from errcode.samples import SAMPLES                  # noqa: E402
from errcode.words import WORDS                      # noqa: E402


class ThreeDigitCodes(unittest.TestCase):
    def test_codes_unique_and_follow_ranges(self):
        seen = set()
        for e in table.ENTRIES:
            self.assertTrue(0 <= e.code <= 999)
            self.assertEqual(e.code // 100, e.domain)
            self.assertNotIn(e.code, seen)
            seen.add(e.code)
        self.assertGreaterEqual(len(table.ENTRIES), 280)

    def test_v01_entries_keep_their_identity(self):
        # code = domain * 100 + v0.1 id, so nothing old moved
        self.assertEqual(table.get("PY.TK_MISSING").code, 102)
        self.assertEqual(table.get("GEN.OK").code, 0)
        self.assertEqual(table.get("HW.GPU_FALLBACK").code, 706)
        self.assertEqual(table.by_code(306).key, "WIN.MOD_NOT_FOUND")

    def test_supersedes_targets_exist(self):
        for e in table.ENTRIES:
            for k in e.supersedes:
                self.assertIn(k, table.BY_KEY, e.key)

    def test_define_app(self):
        e = errcode.define_app(7, "no_scanner", table.ERROR, "Scanner not detected", "Plug it in",
                               r"scanner (?:is )?missing")
        self.assertEqual((e.code, e.key), (907, "APP.NO_SCANNER"))
        self.assertIs(errcode.define_app(7, "NO_SCANNER", table.ERROR, "x"), e)      # idempotent
        with self.assertRaises(ValueError):
            errcode.define_app(7, "OTHER", table.ERROR, "x")
        rep = errcode.scan("fatal: scanner missing")
        self.assertEqual(rep.codes, ["907"])


class DetailCapture(unittest.TestCase):
    def test_module_name(self):
        rep = errcode.scan("ModuleNotFoundError: No module named 'pyrealsense2'")
        self.assertEqual([(h.entry.key, h.detail) for h in rep.hits], [("PY.MODULE_MISSING", "pyrealsense2")])

    def test_shared_library(self):
        rep = errcode.scan("./app: error while loading shared libraries: libxyz.so.3: cannot open shared object file")
        self.assertEqual((rep.hits[0].entry.key, rep.hits[0].detail), ("LIN.SHARED_LIB_MISSING", "libxyz.so.3"))

    def test_klipper_and_esp(self):
        rep = errcode.scan("Lost communication with MCU 'toolhead'\nBrownout detector was triggered")
        got = {h.entry.key: h.detail for h in rep.hits}
        self.assertEqual(got["EMB.KLIPPER_LOST_COMM"], "toolhead")
        self.assertIn("EMB.ESP_BROWNOUT", got)

    def test_paths_keep_last_part(self):
        self.assertEqual(detect.clean_detail("/home/someone/projects/thing/config.json"), "config.json")
        self.assertEqual(detect.clean_detail("139"), 139)
        self.assertEqual(detect.clean_detail("  'x'  "), "x")
        self.assertLessEqual(len(detect.clean_detail("y" * 500)), detect.MAX_DETAIL)

    def test_exception_details(self):
        try:
            import no_such_module_xyz  # noqa: F401
        except ImportError as exc:
            rep = errcode.from_exception(exc)
        self.assertEqual(rep.hits[0].detail, "no_such_module_xyz")
        try:
            open(os.path.join(tempfile.gettempdir(), "nope", "missing-file.txt"))
        except OSError as exc:
            rep = errcode.from_exception(exc)
        self.assertEqual((rep.hits[0].entry.key, rep.hits[0].detail), ("GEN.ENOENT", "missing-file.txt"))

    def test_unknown_exit_code_kept(self):
        hits = detect.hits_from_returncode(77)
        self.assertEqual((hits[0].entry.key, hits[0].detail), ("GEN.EXIT_NONZERO", 77))

    def test_unknown_line_text_travels(self):
        rep = errcode.scan("12:00:01 ERROR: the frobnicator jammed")
        self.assertEqual(rep.hits[0].entry.key, "GEN.UNKNOWN")
        self.assertEqual(rep.hits[0].detail, "the frobnicator jammed")
        self.assertEqual(errcode.decode(rep.payload).codes[0].detail, "the frobnicator jammed")


class EC2Format(unittest.TestCase):
    def test_damm_catches_single_errors_and_adjacent_swaps(self):
        rnd = random.Random(1)
        for _ in range(200):
            body = "".join(rnd.choice("0123456789") for _ in range(19))
            blk = body + ec2.damm(body)
            self.assertTrue(ec2.damm_ok(blk))
            for i in range(20):
                for d in "0123456789":
                    if d != blk[i]:
                        self.assertFalse(ec2.damm_ok(blk[:i] + d + blk[i + 1:]))
                if i < 19 and blk[i] != blk[i + 1]:
                    self.assertFalse(ec2.damm_ok(blk[:i] + blk[i + 1] + blk[i] + blk[i + 2:]))

    def test_capacity_table(self):
        for k in range(1, 20):
            self.assertLessEqual(2 ** ec2.cap(k), 10 ** k)
            self.assertGreater(2 ** (ec2.cap(k) + 1), 10 ** k)
        self.assertEqual(ec2.cap(19), 63)

    def test_text_round_trip(self):
        rnd = random.Random(2)
        alphabet = "abcXYZ019 ._-/\\:,;=+@()[]'\"~#%&!?<>{}|`$^*é"
        for _ in range(300):
            t = "".join(rnd.choice(WORDS) if rnd.random() < .3 else rnd.choice(alphabet) for _ in range(rnd.randint(0, 12)))
            w = ec2.BitWriter()
            ec2.put_text(w, t)
            self.assertEqual(ec2.get_text(ec2.BitReader(w.bits)), t)

    def test_words_compress(self):
        self.assertLess(ec2.text_bits("No module named"), 6 * 4)
        self.assertEqual(len(WORDS), len(set(WORDS)))
        self.assertLessEqual(len(WORDS), 256)

    def test_random_frames_round_trip(self):
        rnd = random.Random(3)
        for _ in range(300):
            ev = [ec2.Event(rnd.randint(0, 999), rnd.randint(0, 3), rnd.randint(1, 500),
                            rnd.choice([None, rnd.randint(-10 ** 6, 10 ** 12), "detail %d" % rnd.randint(0, 99)]))
                  for _ in range(rnd.randint(0, 20))]
            f = ec2.Frame(ev, rnd.randint(0, 2 ** 25 - 1), rnd.randint(0, 2 ** 15 - 1), rnd.randint(0, 50),
                          rnd.choice([None, "stl2step"]), rnd.choice([None, (5, 4, 3)]), rnd.choice([0, 9]))
            digits = ec2.encode(f)
            self.assertTrue(digits.isdigit())
            self.assertEqual(len(digits), ec2.digits_for_bits(len(ec2.encode_frame(f))))
            self.assertEqual(ec2.decode(ec2.single(digits)), f)
            parts = ec2.split_parts(digits, max(40, (len(digits) // 9 // 20 + 1) * 20), f.session)
            rnd.shuffle(parts)
            self.assertEqual(ec2.decode(parts), f)

    def test_damaged_digits_are_pinpointed(self):
        rep = errcode.scan(SAMPLES["Windows: missing C++ runtime"])
        d = rep.digits
        bad = d[:25] + str((int(d[25]) + 3) % 10) + d[26:]
        with self.assertRaises(ec2.BlockCheckError) as cm:
            ec2.decode("EC2-" + bad)
        self.assertEqual(cm.exception.block, 2)
        with self.assertRaises(ec2.EC2Error):
            ec2.decode("EC2-" + d[:-1])                  # missing digit

    def test_missing_part_named(self):
        rep = errcode.scan(SAMPLES["Windows: missing C++ runtime"], part_digits=20)
        parts = rep.parts()
        self.assertGreater(len(parts), 1)
        with self.assertRaises(ec2.EC2Error) as cm:
            ec2.decode(parts[1:])
        self.assertIn("part(s) 1", str(cm.exception))

    def test_found_inside_a_link_and_with_spaces(self):
        rep = errcode.scan(SAMPLES["Linux: tkinter missing"])
        link = rep.qr_content(link=True)
        self.assertTrue(link.startswith("https://"))
        self.assertEqual(errcode.decode(link).codes[0].code, "102")
        self.assertEqual(errcode.decode(rep.pretty()).codes[0].code, "102")


class ReportsAndBudgets(unittest.TestCase):
    def test_samples_decode_back_exactly(self):
        for name, text in SAMPLES.items():
            rep = errcode.scan(text, app="demo")
            dec = errcode.decode(rep.payload)
            self.assertEqual(dec.fmt, "EC2")
            self.assertEqual([(c.code, c.sev, c.count, c.detail) for c in dec.codes],
                             [(h.entry.code3, h.sev, h.count, h.detail) for h in rep.hits], name)
            self.assertEqual(dec.app, "demo")
            self.assertEqual(dec.when, rep.when)

    def test_quick_codes(self):
        rep = errcode.scan(SAMPLES["Crash with GPU + CPU warnings"])
        self.assertEqual(rep.quick, "F212 W701")
        dec = errcode.decode(rep.quick)
        self.assertEqual([(c.code, c.sev) for c in dec.codes], [("212", 3), ("701", 1)])
        self.assertEqual(errcode.decode("102").codes[0].key, "PY.TK_MISSING")

    def test_ec1_still_decodes(self):
        rep = errcode.scan(SAMPLES["Linux: tkinter missing"])
        dec = errcode.decode(rep.payload_ec1)
        self.assertEqual((dec.fmt, dec.codes[0].key), ("EC1", "PY.TK_MISSING"))

    def test_page_budget_and_parts(self):
        from errcode.bench import synthetic_log
        many = [detect.Hit(e, 1, i, -1, "detail-%d-%s" % (i, e.name.lower())) for i, e in enumerate(table.ENTRIES)
                if e.sev >= table.WARN]
        rep = errcode.Report(many, budget=PAGE_BUDGET, part_digits=960)
        self.assertLessEqual(len(rep.digits), PAGE_BUDGET)
        self.assertGreater(len(rep.hits), 60)
        parts = rep.parts()
        self.assertTrue(2 <= len(parts) <= 5)
        for p in parts:
            if qr.available():
                self.assertLessEqual(qr.version(p), 15)
        self.assertEqual(len(errcode.decode(parts).codes), len(rep.hits))
        big = errcode.scan(synthetic_log())
        self.assertLess(len(big.digits), 400)

    @unittest.skipUnless(qr.available(), "segno not installed")
    def test_digits_use_numeric_mode(self):
        rep = errcode.scan(SAMPLES["Windows: missing C++ runtime"])
        self.assertEqual(qr.segments(rep.payload)[1][1], "numeric")
        self.assertLessEqual(qr.version(rep.payload), 3)
        page = errcode.Report([detect.Hit(e) for e in table.ENTRIES if e.sev >= table.WARN], budget=960)
        self.assertLessEqual(qr.version(page.parts()[0]), 15)


class OtherLanguages(unittest.TestCase):
    def test_export_has_what_a_decoder_needs(self):
        data = cli.export_data()
        self.assertEqual(data["words"], list(WORDS))
        self.assertEqual(len({e["code"] for e in data["entries"]}), len(data["entries"]))
        json.dumps(data)

    def test_decoder_page_builds(self):
        from errcode.decoder_page import build
        html = build(cli.export_data())
        self.assertIn("window.ERRCODE_DATA=", html)
        self.assertNotIn("</script><", html.split("window.ERRCODE_DATA=")[1].split(";</script>")[0])

    def test_decoder_page_in_docs_is_current(self):
        from errcode.decoder_page import build
        path = os.path.join(HERE, "..", "docs", "decode.html")
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), build(cli.export_data()),
                             "docs/decode.html is stale: run python -m errcode decoder docs/decode.html")

    @unittest.skipUnless(shutil.which("cc") or shutil.which("gcc"), "no C compiler")
    def test_c_encoder_matches(self):
        cc = shutil.which("cc") or shutil.which("gcc")
        src = os.path.join(HERE, "..", "c", "example.c")
        with tempfile.TemporaryDirectory() as tmp:
            exe = os.path.join(tmp, "ec2_example")
            subprocess.run([cc, "-std=c99", "-Wall", "-Werror", "-O2", "-o", exe, src], check=True)
            out = subprocess.run([exe], capture_output=True, text=True, check=True).stdout.strip()
        dec = errcode.decode(out)
        self.assertEqual(dec.app, "esp-printhost")
        self.assertEqual([(c.code, c.count, c.detail) for c in dec.codes],
                         [("815", 3, "mcu"), ("803", 1, None), ("043", 1, -11), ("101", 1, "PyQt6 <x>")])


if __name__ == "__main__":
    unittest.main()
