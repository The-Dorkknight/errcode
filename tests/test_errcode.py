# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
import errno
import io
import logging
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import errcode                                   # noqa: E402
from errcode import codec, detect, plugin, qr, table   # noqa: E402
from errcode.samples import SAMPLES              # noqa: E402


def keys(rep):
    return [h.entry.key for h in rep.hits]


class TableIntegrity(unittest.TestCase):
    def test_ids_unique_and_in_range(self):
        seen = set()
        for e in table.ENTRIES:
            self.assertLess(e.id, 4096)
            self.assertNotIn((e.domain, e.id), seen)
            seen.add((e.domain, e.id))

    def test_every_entry_has_text(self):
        for e in table.ENTRIES:
            self.assertTrue(e.msg.strip(), e.key)
            if e.sev >= table.WARN:
                self.assertTrue(e.fix.strip(), "%s needs a fix hint" % e.key)

    def test_all_domains_populated(self):
        used = {e.domain for e in table.ENTRIES}
        self.assertEqual(used | {9}, set(table.DOMAINS))        # 9 = app-defined, filled by programs


class Codec(unittest.TestCase):
    def test_every_entry_round_trips(self):
        for e in table.ENTRIES:
            if e.domain >= 8:                                   # EC1 only had domains 0-7
                continue
            code = codec.pack(e.domain, e.sev, e.id)
            self.assertEqual(len(code), 4)
            d, s, i, ok = codec.unpack(code)
            self.assertEqual((d, s, i, ok), (e.domain, e.sev, e.id, True), e.key)

    def test_ok_code_is_0000(self):
        self.assertEqual(codec.pack(0, 0, 0), "0000")

    def test_confusable_characters_forgiven(self):
        code = codec.pack(1, 2, 2)
        typed = code.replace("0", "O").replace("1", "l").lower()
        self.assertEqual(codec.unpack(typed), codec.unpack(code))

    def test_every_single_bit_flip_is_detected(self):
        for e in table.ENTRIES[:40]:
            value = codec.b32_decode(codec.pack(e.domain, e.sev, e.id))
            for bit in range(20):
                bad = codec.b32_encode(value ^ (1 << bit), 4)
                self.assertFalse(codec.unpack(bad)[3], "%s bit %d" % (e.key, bit))

    def test_payload_round_trip(self):
        codes = [codec.pack(1, 2, 2), codec.pack(3, 3, 14)]
        p = codec.build_payload(codes, minute=123456, session=4567)
        self.assertTrue(p.startswith("EC1-"))
        minute, ses, back = codec.parse_payload(p)
        self.assertEqual((minute, ses, back), (123456, 4567, codes))

    def test_payload_uses_only_qr_alphanumeric_chars(self):
        p = errcode.scan(SAMPLES["Windows: missing C++ runtime"]).payload
        allowed = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:")
        self.assertTrue(set(p) <= allowed, p)

    def test_time_stamp_round_trips_to_the_minute(self):
        import datetime
        utc = datetime.timezone.utc
        for when in (datetime.datetime(2026, 10, 2, 10, 36, tzinfo=utc), datetime.datetime(2026, 1, 1, tzinfo=utc),
                     datetime.datetime(2080, 12, 31, 23, 59, tzinfo=utc)):
            n = codec.minute_number(when)
            self.assertEqual(codec.time_from_minute(n), when)
            self.assertEqual(len(codec.b32_encode(n, 5)), 5)

    def test_naive_time_is_treated_as_local(self):
        import datetime
        naive = datetime.datetime(2026, 10, 2, 11, 36)
        self.assertEqual(codec.time_from_minute(codec.minute_number(naive)), naive.astimezone(datetime.timezone.utc))

    def test_out_of_range_time_rejected(self):
        import datetime
        with self.assertRaises(codec.CodecError):
            codec.minute_number(datetime.datetime(2025, 12, 31, tzinfo=datetime.timezone.utc))

    def test_payload_carries_the_time(self):
        rep = errcode.Report([detect.hit_for_key("HW.LOW_RAM")], minute=codec.minute_number() - 90)
        dec = errcode.decode(rep.payload)
        self.assertEqual(dec.when, rep.when)
        self.assertIn("UTC", rep.when_text())
        self.assertIn("local", errcode.decode(rep.payload).lines()[0])

    def test_bad_input_rejected(self):
        for bad in ("EC1-XX", "EC1-AAAAAAAA-123", "EC1-AAAAAA-0000", "", "hello"):
            with self.assertRaises(codec.CodecError):
                errcode.decode(bad)

    def test_decode_flags_mistyped_code(self):
        good = codec.pack(1, 2, 2)
        bad = codec.b32_encode(codec.b32_decode(good) ^ 1, 4)
        d = errcode.decode(bad)
        self.assertFalse(d.codes[0].check_ok)
        self.assertIn("mistyped", d.codes[0].message)

    def test_unknown_entry_still_reports_severity(self):
        code = codec.pack(1, 3, 4000)           # no such entry
        d = errcode.decode(code).codes[0]
        self.assertIsNone(d.entry)
        self.assertEqual(d.sev, 3)
        self.assertIn("Unknown", d.message)


class NoiseAndRanking(unittest.TestCase):
    def test_progress_and_download_noise_ignored(self):
        text = "12% downloading foo\n 55% 3.1/12.0 MB 2.4 MB/s eta 0:00:04\nINFO: tick\n=======>      \n"
        hits, stats = detect.scan_text(text)
        self.assertEqual(hits, [])
        self.assertEqual(stats.noise, 4)

    def test_failure_line_survives_even_with_percent(self):
        rep = errcode.scan("Download failed at 12%: Connection refused")
        self.assertEqual(keys(rep), ["NET.CONN_REFUSED"])

    def test_repeats_collapse(self):
        text = "\n".join("retry %d: Connection refused" % i for i in range(50))
        hits, stats = detect.scan_text(text)
        self.assertEqual(stats.repeats, 49)
        self.assertEqual(hits[0].count, 50)

    def test_ranked_fatal_to_ok(self):
        text = "clGetPlatformIDs failed\nPermission denied: x\nIllegal instruction (core dumped)\nSIGINT KeyboardInterrupt"
        rep = errcode.scan(text)
        sevs = [h.sev for h in rep.hits]
        self.assertEqual(sevs, sorted(sevs, reverse=True))
        self.assertEqual(keys(rep)[0], "CPP.ILLEGAL_INSTRUCTION")
        self.assertNotIn("GEN.CANCELLED", keys(rep))          # ok/info dropped when anything failed

    def test_healthy_log_is_just_ok(self):
        rep = errcode.scan(SAMPLES["Healthy run (nothing wrong)"])
        self.assertEqual(keys(rep), ["GEN.OK"])
        self.assertTrue(rep.ok)

    def test_specific_beats_wrapper(self):
        rep = errcode.scan(SAMPLES["Linux: tkinter missing"])
        self.assertEqual(keys(rep), ["PY.TK_MISSING"])      # not MODULE_MISSING, not UNCAUGHT

    def test_wrapper_kept_when_it_is_all_we_know(self):
        self.assertEqual(keys(errcode.scan("ERROR: Failed building wheel for foo")), ["PY.WHEEL_BUILD_FAILED"])

    def test_unknown_error_gets_generic_code(self):
        self.assertEqual(keys(errcode.scan("FATAL: flux capacitor overload")), ["GEN.UNKNOWN"])

    def test_no_errors_phrase_is_not_an_error(self):
        self.assertEqual(keys(errcode.scan("finished with 0 errors")), ["GEN.OK"])

    def test_warning_prefix_caps_severity(self):
        rep = errcode.scan("WARNING: Retrying after Read timed out")
        self.assertEqual(rep.hits[0].sev, table.WARN)

    def test_windows_entry_supersedes_portable_one(self):
        rep = errcode.scan("FileNotFoundError: [WinError 2] The system cannot find the file specified")
        self.assertEqual(keys(rep), ["WIN.FILE_NOT_FOUND"])

    def test_cap_and_omitted_count(self):
        hits = [detect.Hit(e, 1, i) for i, e in enumerate(e for e in table.ENTRIES if e.sev == table.ERROR)]
        rep = errcode.Report(hits, budget=100)
        self.assertGreater(rep.omitted, 0)
        self.assertLessEqual(len(rep.digits), 100)
        self.assertEqual(len(rep.hits) + rep.omitted, len(detect.rank(hits)))
        self.assertEqual(errcode.decode(rep.payload).omitted, rep.omitted)

    def test_huge_log_is_fast_enough(self):
        import time
        text = "\n".join("INFO step %d ok 12%% 1.0 MB/s" % i for i in range(100000)) + "\nPermission denied\n"
        t = time.time()
        rep = errcode.scan(text)
        self.assertEqual(keys(rep), ["GEN.EACCES"])
        self.assertLess(time.time() - t, 8)


class BigLogs(unittest.TestCase):
    def test_error_in_the_middle_of_a_huge_log_is_found(self):
        noise = ["INFO step %d ok 12%% 1.0 MB/s" % i for i in range(60000)]
        lines = noise[:30000] + ["Permission denied: /etc/shadow"] + noise[30000:]
        self.assertEqual(keys(errcode.scan("\n".join(lines))), ["GEN.EACCES"])

    def test_cap_keeps_head_and_tail_when_everything_is_signal(self):
        lines = ["unique failure %d: error code %d" % (i, i * 7919) for i in range(30000)]
        lines[3] = "Segmentation fault"
        lines[-2] = "Illegal instruction"
        got = keys(errcode.scan("\n".join(lines)))
        self.assertIn("CPP.SEGFAULT", got)
        self.assertIn("CPP.ILLEGAL_INSTRUCTION", got)


class Samples(unittest.TestCase):
    EXPECT = {
        "pip install fails (noisy log)": ["CPP.NO_COMPILER", "NET.TIMEOUT"],
        "Linux: tkinter missing": ["PY.TK_MISSING"],
        "Windows: missing C++ runtime": ["PY.DLL_LOAD_FAILED", "WIN.MOD_NOT_FOUND", "WIN.VCRUNTIME_MISSING"],
        "macOS: Gatekeeper blocked app": ["MAC.GATEKEEPER"],
        "Crash with GPU + CPU warnings": ["CPP.ILLEGAL_INSTRUCTION", "HW.OPENCL_NONE"],
        "Healthy run (nothing wrong)": ["GEN.OK"],
    }

    def test_samples(self):
        self.assertEqual(set(self.EXPECT), set(SAMPLES))
        for name, want in self.EXPECT.items():
            self.assertEqual(keys(errcode.scan(SAMPLES[name])), want, name)

    def test_scan_then_decode_round_trip(self):
        for text in SAMPLES.values():
            rep = errcode.scan(text)
            dec = errcode.decode(rep.payload)
            self.assertEqual([d.key for d in dec.codes], keys(rep))
            self.assertTrue(all(d.check_ok for d in dec.codes))
            self.assertEqual(dec.when, rep.when)


class Detectors(unittest.TestCase):
    def test_exception_errno_mapping(self):
        rep = errcode.from_exception(OSError(errno.ENOSPC, "No space left on device"))
        self.assertIn("GEN.ENOSPC", keys(rep))

    def test_exception_chain_is_walked(self):
        try:
            try:
                raise PermissionError(errno.EACCES, "denied")
            except PermissionError as inner:
                raise RuntimeError("wrapper") from inner
        except RuntimeError as exc:
            self.assertIn("GEN.EACCES", keys(errcode.from_exception(exc)))

    def test_module_missing_exception(self):
        try:
            import _definitely_not_installed_xyz  # noqa: F401
        except ImportError as exc:
            self.assertEqual(keys(errcode.from_exception(exc)), ["PY.MODULE_MISSING"])

    def test_returncodes(self):
        self.assertEqual(detect.hits_from_returncode(139)[0].entry.key, "CPP.SEGFAULT")
        self.assertEqual(detect.hits_from_returncode(137)[0].entry.key, "LIN.OOM_KILLED")
        self.assertEqual(detect.hits_from_returncode(-1073741515)[0].entry.key, "WIN.STATUS_DLL_NOT_FOUND")
        self.assertEqual(detect.hits_from_returncode(0), [])

    def test_every_dictionary_pattern_compiles_and_nothing_matches_empty(self):
        for e in table.ENTRIES:
            for p in e.patterns:
                self.assertIsNone(p.search(""), e.key)


class PluginHooks(unittest.TestCase):
    def setUp(self):
        plugin.uninstall()
        errcode.reset()
        self.out = io.StringIO()
        self._hook = sys.excepthook

    def tearDown(self):
        plugin.uninstall()
        errcode.reset()
        self.assertIs(sys.excepthook, self._hook)

    def test_install_is_idempotent_and_reversible(self):
        errcode.install(stream=self.out)
        errcode.install(stream=self.out)
        self.assertEqual(sum(isinstance(h, plugin._LogHandler) for h in logging.getLogger().handlers), 1)
        plugin.uninstall()
        self.assertEqual(sum(isinstance(h, plugin._LogHandler) for h in logging.getLogger().handlers), 0)

    def test_excepthook_records_and_prints_footer(self):
        errcode.install(app="demo", stream=self.out)
        try:
            raise ModuleNotFoundError("No module named 'tkinter'", name="tkinter")
        except ModuleNotFoundError:
            real_stderr, sys.stderr = sys.stderr, io.StringIO()
            try:
                sys.excepthook(*sys.exc_info())
            finally:
                sys.stderr = real_stderr
        text = self.out.getvalue()
        self.assertIn("[errcode demo] E102  EC2-", text)
        self.assertIn("PY.TK_MISSING", text)

    def test_logging_warning_and_above_only(self):
        errcode.install(stream=self.out)
        log = logging.getLogger("t.plugin")
        log.setLevel(logging.DEBUG)
        log.info("Connection refused (info is ignored)")
        self.assertTrue(errcode.report().ok)
        log.error("Connection refused")
        self.assertEqual(keys(errcode.report()), ["NET.CONN_REFUSED"])

    def test_warning_level_log_is_capped_at_warn(self):
        errcode.install(stream=self.out)
        logging.getLogger("t.cap").warning("Read timed out")
        self.assertEqual(errcode.report().hits[0].sev, table.WARN)
        logging.getLogger("t.cap").error("Permission denied")
        rep = errcode.report()
        self.assertEqual(keys(rep)[0], "GEN.EACCES")            # a real error outranks the warning

    def test_thread_exception_recorded(self):
        saved = threading.excepthook
        threading.excepthook = lambda a: None            # quiet the "original" hook that install() wraps
        try:
            errcode.install(stream=self.out)

            def boom():
                raise MemoryError("x")
            t = threading.Thread(target=boom)
            t.start()
            t.join()
            self.assertIn("GEN.ENOMEM", keys(errcode.report()))
        finally:
            plugin.uninstall()
            threading.excepthook = saved

    def test_record_app_set_code(self):
        errcode.record("HW.GPU_FALLBACK")
        rep = errcode.report()
        self.assertEqual(keys(rep), ["HW.GPU_FALLBACK"])
        self.assertEqual(rep.hits[0].sev, table.WARN)

    def test_quiet_env_silences_footer(self):
        os.environ["ERRCODE_QUIET"] = "1"
        try:
            errcode.install(stream=self.out)
            errcode.record("HW.LOW_RAM")
            plugin._emit()
        finally:
            del os.environ["ERRCODE_QUIET"]
        self.assertEqual(self.out.getvalue(), "")

    def test_footer_printed_once(self):
        errcode.install(stream=self.out)
        errcode.record("HW.LOW_RAM")
        plugin._emit()
        plugin._emit()
        self.assertEqual(self.out.getvalue().count("EC2-"), 1)

    def test_run_captures_exit_code_and_output(self):
        cp = errcode.run([sys.executable, "-c", "import sys; sys.stderr.write('Permission denied\\n'); sys.exit(139)"])
        self.assertEqual(cp.returncode, 139)
        self.assertEqual(set(keys(errcode.report())), {"GEN.EACCES", "CPP.SEGFAULT"})

    def test_run_missing_command_records_and_raises(self):
        with self.assertRaises(FileNotFoundError):
            errcode.run(["/definitely/not/a/real/command"])
        self.assertIn("GEN.ENOENT", keys(errcode.report()))


@unittest.skipUnless(qr.available(), "segno not installed")
class QR(unittest.TestCase):
    def test_matrix_is_square_and_small(self):
        rep = errcode.scan(SAMPLES["Windows: missing C++ runtime"])
        m = rep.qr_matrix()
        self.assertEqual(len(m), len(m[0]))
        self.assertLessEqual(len(m), 29)          # <= version 3: easy to scan

    def test_png_and_svg_written(self):
        import tempfile
        rep = errcode.scan(SAMPLES["Linux: tkinter missing"])
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.png", "a.svg"):
                rep.save_qr(os.path.join(d, name))
                self.assertGreater(os.path.getsize(os.path.join(d, name)), 100)

    def test_terminal_qr(self):
        self.assertTrue(errcode.scan("Permission denied").terminal_qr().strip())


if __name__ == "__main__":
    unittest.main()
