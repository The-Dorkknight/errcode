# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Command line: python -m errcode <command>   (also installed as 'errcode')."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import __build_date__, __version_label__, codec, ec2, table
from .plugin import scan
from .report import DEFAULT_BUDGET, DEFAULT_PART, PAGE_BUDGET, decode
from .samples import SAMPLES
from .words import WORDS


def _print_report(rep, args) -> None:
    if getattr(args, "json", False):
        print(json.dumps(rep.to_dict(), indent=2))
        return
    print(rep.text())
    print("(%s)" % rep.stats.summary())
    parts = rep.parts()
    if getattr(args, "png", None):
        root, ext = os.path.splitext(args.png)
        for i in range(len(parts)):
            path = args.png if len(parts) == 1 else "%s-%d%s" % (root, i + 1, ext or ".png")
            rep.save_qr(path, part=i, link=args.link)
            print("QR saved to %s" % path)
    if getattr(args, "qr", False):
        for i in range(len(parts)):
            if len(parts) > 1:
                print("QR part %d of %d:" % (i + 1, len(parts)))
            try:
                print(rep.terminal_qr(part=i, link=args.link))
            except UnicodeEncodeError:
                print("(this console cannot show block characters; use --png FILE instead)")
                break


def _read_input(args) -> str:
    if args.sample is not None:
        names = list(SAMPLES)
        print("sample: %s" % names[args.sample])
        return SAMPLES[names[args.sample]]
    if args.file in (None, "-"):
        return sys.stdin.read()
    with open(args.file, "r", errors="replace") as fh:
        return fh.read()


def cmd_scan(args) -> int:
    budget = PAGE_BUDGET if args.page else args.budget
    rep = scan(_read_input(args), app=args.app, budget=budget, part_digits=args.part)
    _print_report(rep, args)
    return 0 if rep.ok else 1            # exit status 1 = something failed (handy in scripts)


def cmd_decode(args) -> int:
    try:
        texts = args.text
        if len(texts) > 1 and all(ec2.is_ec2(t) for t in texts):
            dec = decode(texts)                       # several QR parts
        else:
            dec = decode(" ".join(texts))
    except (codec.CodecError, ec2.EC2Error) as exc:
        print("cannot decode: %s" % exc, file=sys.stderr)
        return 2
    print("\n".join(dec.lines()))
    for d in dec.codes:
        if d.fix and d.sev >= table.WARN:
            print("  fix [%s %s]: %s" % (d.code, d.key, d.fix))
    return 0


def cmd_list(args) -> int:
    for e in table.ENTRIES:
        dom = table.DOMAINS[e.domain][0]
        if args.domain and dom != args.domain.upper():
            continue
        print("%s  %-5s %-28s %s" % (e.code3, e.sev_name.upper(), e.key, e.msg))
    return 0


def export_data() -> dict:
    """Everything a decoder in another language needs (also embedded in decode.html)."""
    return {
        "format": 2, "revision": table.REVISION, "version": __version_label__,
        "domains": {str(i): {"key": k, "title": t} for i, (k, t) in table.DOMAINS.items()},
        "severities": list(table.SEV_NAMES),
        "words": list(WORDS),
        "entries": [{"code": e.code, "domain": e.domain, "id": e.id, "name": e.name, "key": e.key,
                     "severity": e.sev, "message": e.msg, "fix": e.fix,
                     "patterns": [p.pattern for p in e.patterns], "errno": e.errno_name, "winerr": e.winerr,
                     "generic": e.generic, "supersedes": list(e.supersedes),
                     "ec1": codec.pack(e.domain, e.sev, e.id) if e.domain < 8 else None}
                    for e in table.ENTRIES if e.domain != 9],
    }


def cmd_export(args) -> int:
    out = json.dumps(export_data(), indent=1)
    if args.path:
        with open(args.path, "w", encoding="utf-8") as fh:
            fh.write(out)
        print("wrote %d entries to %s" % (len(table.ENTRIES), args.path))
    else:
        print(out)
    return 0


def cmd_decoder(args) -> int:
    from .decoder_page import build
    html = build(export_data())
    with open(args.path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("wrote the offline decoder page to %s (%d KB)" % (args.path, len(html) // 1024))
    return 0


def cmd_bench(args) -> int:
    from . import bench
    extra = {}
    for path in args.files:
        with open(path, "r", errors="replace") as fh:
            extra[os.path.basename(path)] = fh.read()
    rows = bench.run(extra)
    if args.json:
        print(json.dumps(rows, indent=1))
    else:
        print(bench.format_rows(rows))
    return 0


def cmd_gui(args) -> int:
    from .gui import main as gui_main
    gui_main()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="errcode", description="Compact error codes: scan logs, decode codes, make QR.")
    p.add_argument("--version", action="version", version="errcode %s (built %s) - WORK IN PROGRESS" % (__version_label__, __build_date__))
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("scan", help="scan a log file (or stdin) and print the ranked report")
    s.add_argument("file", nargs="?", help="log file, or - for stdin")
    s.add_argument("--sample", type=int, metavar="N", help="use built-in sample log number N (0..%d)" % (len(SAMPLES) - 1))
    s.add_argument("--app", help="program name to carry in the report")
    s.add_argument("--budget", type=int, default=DEFAULT_BUDGET, metavar="DIGITS",
                   help="most digits the report may use (default %d = one QR)" % DEFAULT_BUDGET)
    s.add_argument("--page", action="store_true", help="allow a page-sized report (%d digits)" % PAGE_BUDGET)
    s.add_argument("--part", type=int, default=DEFAULT_PART, metavar="DIGITS",
                   help="digits per QR before splitting into parts (default %d)" % DEFAULT_PART)
    s.add_argument("--qr", action="store_true", help="also print the QR code(s) in the terminal")
    s.add_argument("--png", metavar="FILE", help="save the QR code(s) as PNG or SVG")
    s.add_argument("--link", action="store_true", help="QR opens the online decoder page (GitHub Pages)")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.set_defaults(fn=cmd_scan)

    d = sub.add_parser("decode", help="decode EC2 digits (one or more QR parts), quick codes like E102, or EC1")
    d.add_argument("text", nargs="+")
    d.set_defaults(fn=cmd_decode)

    l = sub.add_parser("list", help="list the dictionary (optionally one domain, e.g. WIN or EMB)")
    l.add_argument("domain", nargs="?")
    l.set_defaults(fn=cmd_list)

    x = sub.add_parser("export", help="export the dictionary + word list as JSON for other languages")
    x.add_argument("path", nargs="?")
    x.set_defaults(fn=cmd_export)

    h = sub.add_parser("decoder", help="write the offline HTML decoder page (works on a phone)")
    h.add_argument("path", nargs="?", default="decode.html")
    h.set_defaults(fn=cmd_decoder)

    b = sub.add_parser("bench", help="compare raw text, zlib and EC2 sizes on the samples (and your logs)")
    b.add_argument("files", nargs="*")
    b.add_argument("--json", action="store_true")
    b.set_defaults(fn=cmd_bench)

    g = sub.add_parser("gui", help="open the demo window")
    g.set_defaults(fn=cmd_gui)

    args = p.parse_args(argv)
    if not getattr(args, "fn", None):
        p.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
