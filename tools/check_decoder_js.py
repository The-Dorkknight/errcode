#!/usr/bin/env python3
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Cross-check the JavaScript decoder in docs/decode.html against the Python encoder.

Needs Playwright + Chromium (pip install playwright; playwright install chromium).
Not part of the normal test run because of that dependency.

    python tools/check_decoder_js.py docs/decode.html
"""
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from errcode import ec2, table  # noqa: E402
from errcode.words import WORDS  # noqa: E402

ALPH = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ._-/\\:,;=+@()[]'\"~#%&!?<>{}|`$^*é"


def rand_text(rnd):
    parts = []
    for _ in range(rnd.randint(0, 5)):
        if rnd.random() < 0.4:
            parts.append(rnd.choice(WORDS))
        else:
            parts.append("".join(rnd.choice(ALPH) for _ in range(rnd.randint(1, 8))))
    return "".join(parts)


def rand_frame(rnd):
    codes = [e.code for e in table.ENTRIES] + [950, 999, 873]
    events = []
    for _ in range(rnd.randint(1, 12)):
        kind = rnd.random()
        detail = None if kind < 0.4 else (rnd.randint(-5000, 10 ** rnd.randint(1, 10)) if kind < 0.7 else rand_text(rnd))
        events.append(ec2.Event(rnd.choice(codes), rnd.randint(0, 3), rnd.choice([1, 1, 2, 7, 300]), detail))
    return ec2.Frame(events, rnd.randint(0, 2 ** 25 - 1), rnd.randint(0, 2 ** 15 - 1), rnd.randint(0, 9),
                     rand_text(rnd) or None if rnd.random() < 0.5 else None,
                     (rnd.randint(0, 10 ** 6), rnd.randint(0, 9999), rnd.randint(0, 99)) if rnd.random() < 0.5 else None,
                     rnd.choice([0, 0, 3]))


def main(path):
    from playwright.sync_api import sync_playwright
    rnd = random.Random(42)
    cases = []
    for i in range(300):
        f = rand_frame(rnd)
        digits = ec2.encode(f)
        if i % 3 == 0:
            text = "\n".join(reversed(ec2.split_parts(digits, 60, f.session)))
        elif i % 3 == 1:
            text = "EC2-" + ec2.pretty(digits)
        else:
            text = "https://example.invalid/decode.html#" + ec2.single(digits)
        want = {"app": f.app, "stats": list(f.stats) if f.stats else None, "omitted": f.omitted,
                "session": "%05d" % f.session, "rev": f.rev,
                "codes": [[e.code, e.sev, e.count, None if e.detail == "" else e.detail] for e in f.events]}
        cases.append((text, want))
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.goto(pathlib.Path(path).resolve().as_uri())
        bad = 0
        for text, want in cases:
            got = page.evaluate("""t => { const r = window.ERRCODE_DECODE(t);
                return {app: r.app, stats: r.stats, omitted: r.omitted, session: r.session, rev: r.rev,
                        codes: r.codes.map(c => [c.code, c.sev, c.count, c.detail])}; }""", text)
            if got != want:
                bad += 1
                if bad < 4:
                    print("MISMATCH\n text=%r\n want=%s\n got =%s" % (text[:120], json.dumps(want), json.dumps(got)))
        # one wrong digit must be caught and pinpointed
        digits = ec2.encode(rand_frame(rnd))
        broken = digits[:3] + str((int(digits[3]) + 1) % 10) + digits[4:]
        msg = page.evaluate("t => { try { window.ERRCODE_DECODE(t); return 'no error'; } catch (e) { return e.message; } }",
                            "EC2-" + broken)
        b.close()
    print("%d/%d random reports decoded identically by the JS decoder" % (len(cases) - bad, len(cases)))
    print("wrong-digit test: %s" % msg)
    return 1 if bad or "Block 1" not in msg else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "docs/decode.html"))
