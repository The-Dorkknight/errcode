# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Build a Report from ranked hits, and decode report strings / bare codes back.

v0.2: reports are EC2 (all digits, 3-digit codes + details, 20-digit blocks).
EC1 strings and 4-character codes from v0.1 still decode.
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Union

from . import codec, ec2, table
from .detect import Hit, ScanStats, rank

# Digit budgets. 960 digits (48 blocks) still fits one QR of version 15 (77x77 modules) at
# error level M with its header - comfortable to scan off a laptop screen.
# A printed page holds about 4000 digits (split into up to 5 QR parts).
DEFAULT_BUDGET = 960
DEFAULT_PART = 960
PAGE_BUDGET = 4000
MAX_EVENTS = 200
SHORT_DETAIL = 16                 # details are cut to this when space runs out
DECODER_URL = "https://the-dorkknight.github.io/errcode/decode.html#"
SEV_LETTER = "OWEF"               # ok, warn, error, fatal - used in quick codes like E102


class Report:
    """The ranked outcome of a scan, with its EC2 digits, quick codes and QR."""

    def __init__(self, hits: List[Hit], stats: Optional[ScanStats] = None,
                 minute: Optional[int] = None, session: Optional[int] = None,
                 max_codes: Optional[int] = None, app: Optional[str] = None,
                 budget: int = DEFAULT_BUDGET, part_digits: int = DEFAULT_PART):
        everything = rank(hits) or [Hit(table.get("GEN.OK"))]
        ranked = everything[:max_codes or MAX_EVENTS]
        self.stats = stats or ScanStats()
        self.minute = codec.minute_number() if minute is None else minute
        self.session = codec.new_session() if session is None else session
        self.app = (app or "")[:24] or None
        self.budget, self.part_digits = budget, part_digits
        self.hits, self.omitted = self._fit(ranked, len(everything) - len(ranked))

    # ---- fitting the budget -------------------------------------------------
    def _frame(self, hits: List[Hit], omitted: int) -> ec2.Frame:
        st = self.stats
        stats = (st.lines, st.noise, st.repeats) if st.lines else None
        return ec2.Frame([ec2.Event(h.entry.code, h.sev, h.count, h.detail) for h in hits],
                         self.minute, self.session, table.REVISION, self.app, stats, omitted)

    def _digits_of(self, hits: List[Hit], omitted: int) -> int:
        return ec2.digits_for_bits(len(ec2.encode_frame(self._frame(hits, omitted))))

    def _fit(self, ranked: List[Hit], extra: int = 0):
        hits = [Hit(h.entry, h.count, h.first, h.sev, h.detail) for h in ranked]
        if self._digits_of(hits, extra) <= self.budget:
            return hits, extra
        for h in hits:                                       # 1st: shorten long text details
            if isinstance(h.detail, str) and len(h.detail) > SHORT_DETAIL:
                h.detail = h.detail[:SHORT_DETAIL]
        lo, hi = 1, len(hits)                                # 2nd: drop the lowest-priority events
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._digits_of(hits[:mid], len(hits) - mid + extra) <= self.budget:
                lo = mid
            else:
                hi = mid - 1
        return hits[:lo], len(hits) - lo + extra

    # ---- codes and strings --------------------------------------------------
    @property
    def codes(self) -> List[str]:
        """3-digit codes, worst first, e.g. ['102', '706']."""
        return [h.entry.code3 for h in self.hits]

    @property
    def quick(self) -> str:
        """Severity letter + code, e.g. 'E102 W706' - short enough to say on the phone."""
        return " ".join("%s%s" % (SEV_LETTER[h.sev], h.entry.code3) for h in self.hits)

    @property
    def frame(self) -> ec2.Frame:
        return self._frame(self.hits, self.omitted)

    @property
    def digits(self) -> str:
        return ec2.encode(self.frame)

    @property
    def payload(self) -> str:
        """The whole multiplexed report as one string: 'EC2-<digits>'."""
        return ec2.single(self.digits)

    def parts(self, part_digits: Optional[int] = None) -> List[str]:
        """QR-sized pieces ('EC2-...' if it fits in one, else 'EC2/<i><n><set>-...')."""
        digits = self.digits
        per = max(part_digits or self.part_digits,
                  -(-len(digits) // (ec2.MAX_PARTS * ec2.BLOCK_DIGITS)) * ec2.BLOCK_DIGITS)   # never more than 9 parts
        return ec2.split_parts(digits, per, self.session)

    def pretty(self) -> str:
        return "EC2-\n" + ec2.pretty(self.digits)

    @property
    def payload_ec1(self) -> str:
        """Legacy v0.1 string (codes outside domains 0-7 are left out)."""
        old = [codec.pack(h.entry.domain, h.sev, h.entry.id) for h in self.hits if h.entry.domain < 8]
        return codec.build_payload(old[:codec.MAX_CODES] or [codec.pack(0, 0, 0)], self.minute,
                                   self.session & 0x7FFF)

    @property
    def when(self) -> datetime.datetime:
        """When the report was made (aware UTC datetime, minute resolution)."""
        return codec.time_from_minute(self.minute)

    def when_text(self) -> str:
        return codec.format_when(self.when)

    @property
    def worst(self) -> int:
        return max(h.sev for h in self.hits)

    @property
    def ok(self) -> bool:
        return self.worst < table.WARN

    def lines(self) -> List[str]:
        out = []
        for h in self.hits:
            n = " (x%d)" % h.count if h.count > 1 else ""
            d = " [%s]" % h.detail if h.detail not in (None, "") else ""
            out.append("%s  %-5s %-26s %s%s%s" % (h.entry.code3, table.SEV_NAMES[h.sev].upper(), h.entry.key,
                                                  h.entry.msg, d, n))
        if self.omitted:
            out.append("+%d lower-priority code(s) left out to fit %d digits" % (self.omitted, self.budget))
        return out

    def text(self, fixes: bool = True) -> str:
        parts = self.parts()
        head = ["Report made %s%s" % (self.when_text(), "  app %s" % self.app if self.app else ""),
                "Quick codes: %s" % self.quick]
        out = head + self.lines()
        if fixes:
            for h in self.hits:
                if h.sev >= table.WARN and h.entry.fix:
                    out.append("  fix [%s %s]: %s" % (h.entry.code3, h.entry.key, h.entry.fix))
        out.append("Full report (%d digits%s):" % (len(self.digits),
                                                  ", %d QR parts" % len(parts) if len(parts) > 1 else ""))
        out.append(self.pretty())
        return "\n".join(out)

    def to_dict(self) -> dict:
        return {"format": "EC2", "payload": self.payload, "parts": self.parts(), "quick": self.quick,
                "time_utc": self.when.isoformat(), "session": self.session, "app": self.app,
                "omitted": self.omitted, "dictionary_revision": table.REVISION, "ec1": self.payload_ec1,
                "codes": [{"code": h.entry.code3, "key": h.entry.key, "severity": table.SEV_NAMES[h.sev],
                           "message": h.entry.msg, "fix": h.entry.fix, "count": h.count, "detail": h.detail}
                          for h in self.hits]}

    # ---- QR (needs the optional 'segno' package) -------------------------------
    def qr_content(self, part: int = 0, link: bool = False) -> str:
        p = self.parts()[part]
        return DECODER_URL + p if link else p

    def qr_matrix(self, part: int = 0, link: bool = False):
        from . import qr
        return qr.matrix(self.qr_content(part, link))

    def save_qr(self, path: str, scale: int = 8, part: int = 0, link: bool = False) -> None:
        from . import qr
        qr.save(self.qr_content(part, link), path, scale)

    def terminal_qr(self, part: int = 0, link: bool = False) -> str:
        from . import qr
        return qr.terminal(self.qr_content(part, link))


# --------------------------------------------------------------------------
@dataclass
class DecodedCode:
    code: str                   # as shown: '102' (EC2) or '7K3M' (EC1)
    domain: int
    sev: int
    entry_id: int
    check_ok: bool
    entry: Optional[table.Entry]      # None if this dictionary does not know the code
    count: int = 1
    detail: Optional[Union[int, str]] = None

    @property
    def key(self) -> str:
        if self.entry:
            return self.entry.key
        return "%s.#%d" % (table.DOMAINS.get(self.domain, ("?",))[0], self.entry_id)

    @property
    def message(self) -> str:
        if not self.check_ok:
            return "Check digit does not match - this code was probably mistyped or misread."
        if self.entry is None:
            if self.domain == 9:
                return "App-defined code - see the sending program's documentation."
            return "Unknown to this dictionary version (sender may be newer). Severity is still valid."
        return self.entry.msg

    @property
    def fix(self) -> str:
        return self.entry.fix if self.entry and self.check_ok else ""


@dataclass
class Decoded:
    codes: List[DecodedCode]
    when: Optional[datetime.datetime] = None      # aware UTC
    session: Optional[str] = None
    fmt: str = "codes"                            # 'EC2', 'EC1' or 'codes'
    app: Optional[str] = None
    stats: Optional[tuple] = None
    omitted: int = 0
    revision: Optional[int] = None
    notes: List[str] = field(default_factory=list)

    def lines(self) -> List[str]:
        out = []
        if self.when:
            out.append("Made %s   session %s%s" % (codec.format_when(self.when), self.session,
                                                    "   app %s" % self.app if self.app else ""))
        if self.stats:
            out.append("Log: %d lines scanned, %d noise and %d repeats ignored" % tuple(self.stats))
        for d in self.codes:
            flag = "" if d.check_ok else "  [BAD CHECK]"
            det = " [%s]" % d.detail if d.detail not in (None, "") else ""
            n = " (x%d)" % d.count if d.count > 1 else ""
            out.append("%s  %-5s %-26s %s%s%s%s" % (d.code, table.SEV_NAMES[d.sev].upper(), d.key, d.message,
                                                    det, n, flag))
        if self.omitted:
            out.append("+%d lower-priority code(s) were left out by the sender" % self.omitted)
        out.extend(self.notes)
        return out


_QUICK = re.compile(r"^(?:[OWEF]?\d{3}[\s,;]*)+$", re.I)


def _from_frame(f: ec2.Frame) -> Decoded:
    out = []
    for e in f.events:
        entry = table.by_code(e.code)
        out.append(DecodedCode("%03d" % e.code, e.code // 100, e.sev, e.code % 100, True, entry, e.count, e.detail))
    notes = []
    if f.rev > table.REVISION:
        notes.append("Note: sent with dictionary revision %d; this decoder has %d - update errcode for newer codes."
                     % (f.rev, table.REVISION))
    return Decoded(out, codec.time_from_minute(f.minute), "%05d" % f.session, "EC2", f.app, f.stats, f.omitted,
                   f.rev, notes)


def decode(text: Union[str, Iterable[str]]) -> Decoded:
    """Decode an EC2 report (one string, or several QR parts), an EC1 string, quick codes
    such as 'E102 W706' / '102 706', or v0.1 4-character codes such as '7K3M 4Q2P'."""
    if not isinstance(text, str):
        return _from_frame(ec2.decode(list(text)))
    text = text.strip()
    if ec2.is_ec2(text):
        try:
            return _from_frame(ec2.decode(text))
        except ec2.EC2Error as exc:
            raise codec.CodecError(str(exc))
    if codec.is_payload(text):
        minute, ses, raw_codes = codec.parse_payload(text)
        when, session = codec.time_from_minute(minute), codec.b32_encode(ses, 3)
        return Decoded(_ec1_codes(raw_codes), when, session, "EC1")
    if _QUICK.match(text):
        out = []
        for tok in re.findall(r"[OWEF]?\d{3}", text, re.I):
            n = int(tok[-3:])
            entry = table.by_code(n)
            sev = SEV_LETTER.index(tok[0].upper()) if tok[0].isalpha() else (entry.sev if entry else table.ERROR)
            out.append(DecodedCode("%03d" % n, n // 100, sev, n % 100, True, entry))
        return Decoded(out)
    compact = codec.normalise(text)
    if not compact or len(compact) % 4:
        raise codec.CodecError("expected an EC2 report, 3-digit codes, an EC1 string or groups of 4 characters")
    return Decoded(_ec1_codes([compact[i:i + 4] for i in range(0, len(compact), 4)]))


def _ec1_codes(raw_codes: List[str]) -> List[DecodedCode]:
    out = []
    for c in raw_codes:
        domain, sev, eid, ok = codec.unpack(c)
        out.append(DecodedCode(codec.normalise(c), domain, sev, eid, ok, table.lookup(domain, eid)))
    return out
