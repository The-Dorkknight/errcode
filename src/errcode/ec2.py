# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""EC2: the all-digits multiplexed report format.

Why digits: QR "numeric" mode packs 3 digits into 10 bits (3.33 bits per digit) and
"alphanumeric" packs 2 characters into 11 bits (5.5 bits per character). Measured
per QR module both carry the same information to within 0.5 %, so going all-digits
costs nothing in the QR - and digits can be read aloud, typed on any keypad, sent by
SMS or written on paper. SMART Health Cards use numeric mode for the same reason.

Layout - one bit stream, cut into 20-digit blocks:

    EC2-<block><block>...<last block>          one QR / one line of text
    EC2/<i><n><set:3>-<blocks...>              part i of n (n <= 9) when split over QRs

    block      = 19 data digits (one 63-bit chunk, zero padded) + 1 Damm check digit
    last block = k data digits + 1 check digit, k = fewest digits that hold the
                 remaining bits (cap(k) = largest b with 2**b <= 10**k)
    The Damm digit catches every single wrong digit and every swap of two neighbouring
    digits, so a hand-typed or read-aloud block that is wrong is pinpointed.

Bit stream (most significant bit first). G = exp-Golomb order 0 (0 -> 1 bit,
1-2 -> 3 bits, 3-6 -> 5 bits ...), good for the small numbers that dominate:

    header  rev:G  minute:25  session:15  flags:3 (app, stats, omitted)
            [app: TEXT] [stats: lines:G noise:G repeats:G] [omitted:G]
            events:G
    event   code:10 (0-999; 1000-1023 reserved)  sev:2  (count-1):G
            tag:2 -> 0 none | 1 int >= 0 (G) | 2 TEXT | 3 int < 0 (G of -v-1)
    TEXT    symbols:G then 6-bit symbols:
              0 SHIFT  1 CAPS  2 WORD(+8 bits: words.WORDS index)  3 RAW(+8 bits: byte)
              4-29 a-z   30-39 0-9   40-63 " ._-/\\:,;=+@()[]'\\"~#%&!?"

A decoder that does not know a code still parses the whole report: every field
says how long it is.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Tuple, Union

from .words import WORDS

PREFIX = "EC2"
MINUTE_BITS = 25
SESSION_BITS = 15
CODE_BITS = 10
MAX_CODE = 999
BLOCK_DIGITS = 20                 # 19 data digits + 1 check digit
DATA_DIGITS = BLOCK_DIGITS - 1
CHUNK_BITS = 63                   # 2**63 < 10**19
MAX_PARTS = 9

Detail = Union[None, int, str]


class EC2Error(ValueError):
    """Bad or damaged EC2 text."""


class BlockCheckError(EC2Error):
    def __init__(self, block: int, first_digit: int, last_digit: int):
        self.block, self.first_digit, self.last_digit = block, first_digit, last_digit
        super().__init__("block %d (digits %d-%d) failed its check digit - re-read or re-scan those digits"
                         % (block, first_digit, last_digit))


# ---- Damm check digit (order-10 quasigroup from Damm's 2004 thesis) -------------
_DAMM = (
    (0, 3, 1, 7, 5, 9, 8, 6, 4, 2), (7, 0, 9, 2, 1, 5, 4, 8, 6, 3), (4, 2, 0, 6, 8, 7, 1, 3, 5, 9),
    (1, 7, 5, 0, 9, 8, 3, 4, 2, 6), (6, 1, 2, 3, 0, 4, 5, 9, 7, 8), (3, 6, 7, 4, 2, 0, 9, 5, 8, 1),
    (5, 8, 6, 9, 7, 2, 0, 1, 3, 4), (8, 9, 4, 5, 3, 6, 2, 0, 1, 7), (9, 4, 3, 8, 6, 1, 7, 2, 0, 5),
    (2, 5, 8, 1, 4, 3, 6, 7, 9, 0),
)


def damm(digits: str) -> str:
    """Check digit for a string of digits."""
    interim = 0
    for ch in digits:
        interim = _DAMM[interim][ord(ch) - 48]
    return chr(48 + interim)


def damm_ok(digits_with_check: str) -> bool:
    return damm(digits_with_check) == "0"


# ---- digits <-> bits per block ---------------------------------------------------
def cap(k: int) -> int:
    """Bits that k decimal digits can always hold."""
    b = 0
    while 2 ** (b + 1) <= 10 ** k:
        b += 1
    return b


_CAP = [cap(k) for k in range(DATA_DIGITS + 1)]


def _digits_for(bits: int) -> int:
    for k in range(1, DATA_DIGITS + 1):
        if _CAP[k] >= bits:
            return k
    raise AssertionError(bits)


# ---- bit writer / reader ---------------------------------------------------------
class BitWriter:
    def __init__(self) -> None:
        self.bits: List[int] = []

    def put(self, value: int, n: int) -> None:
        if value < 0 or value >= (1 << n):
            raise EC2Error("value %r does not fit in %d bits" % (value, n))
        self.bits.extend((value >> (n - 1 - i)) & 1 for i in range(n))

    def gamma(self, value: int) -> None:
        """exp-Golomb order 0."""
        if value < 0:
            raise EC2Error("exp-Golomb needs a value >= 0")
        v = value + 1
        n = v.bit_length()
        self.bits.extend([0] * (n - 1))
        self.put(v, n)

    def __len__(self) -> int:
        return len(self.bits)


class BitReader:
    def __init__(self, bits: Sequence[int]) -> None:
        self.bits, self.pos = bits, 0

    def get(self, n: int) -> int:
        if self.pos + n > len(self.bits):
            raise EC2Error("report is truncated (ran out of digits) - a part or block may be missing")
        v = 0
        for b in self.bits[self.pos:self.pos + n]:
            v = (v << 1) | b
        self.pos += n
        return v

    def gamma(self) -> int:
        zeros = 0
        while True:
            if self.pos >= len(self.bits):
                raise EC2Error("report is truncated (ran out of digits) - a part or block may be missing")
            if self.bits[self.pos]:
                break
            zeros += 1
            self.pos += 1
            if zeros > 64:
                raise EC2Error("damaged report (number field too long)")
        return self.get(zeros + 1) - 1


# ---- text coder ------------------------------------------------------------------
SHIFT, CAPS, WORD, RAW = 0, 1, 2, 3
_PUNCT = " ._-/\\:,;=+@()[]'\"~#%&!?"
_SYM = {}
for _i, _c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _SYM[_c] = 4 + _i
for _i, _c in enumerate("0123456789"):
    _SYM[_c] = 30 + _i
for _i, _c in enumerate(_PUNCT):
    _SYM[_c] = 40 + _i
_CHAR = {v: k for k, v in _SYM.items()}
assert len(_SYM) == 60 and max(_SYM.values()) == 63
_WORD_INDEX = {}
for _i, _w in enumerate(WORDS):
    _WORD_INDEX.setdefault(_w[0], []).append((_w, _i))
for _lst in _WORD_INDEX.values():
    _lst.sort(key=lambda t: -len(t[0]))


def _is_letter(c: str) -> bool:
    return "a" <= c <= "z" or "A" <= c <= "Z"


def text_symbols(text: str) -> List[Tuple[int, Optional[int]]]:
    """Text -> [(symbol, extra byte or None)]."""
    out: List[Tuple[int, Optional[int]]] = []
    caps = False
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        hit = next(((w, idx) for w, idx in _WORD_INDEX.get(c, ()) if text.startswith(w, i)), None)
        if hit:
            out.append((WORD, hit[1]))
            i += len(hit[0])
            continue
        if _is_letter(c):
            up = c.isupper()
            if up != caps:
                j = i
                while j < n and _is_letter(text[j]) and text[j].isupper() == up:
                    j += 1
                if j - i >= 2 or not up:          # a run of 2+, or one lower-case letter inside caps
                    out.append((CAPS, None))
                    caps = not caps
                else:
                    out.append((SHIFT, None))
            out.append((_SYM[c.lower()], None))
        elif c in _SYM:
            out.append((_SYM[c], None))
        else:
            o = ord(c)
            out.append((RAW, o if o < 256 else ord("?")))
        i += 1
    return out


def put_text(w: BitWriter, text: str) -> None:
    syms = text_symbols(text)
    w.gamma(len(syms))
    for s, extra in syms:
        w.put(s, 6)
        if extra is not None:
            w.put(extra, 8)


def get_text(r: BitReader) -> str:
    n = r.gamma()
    if n > 4096:
        raise EC2Error("damaged report (text field too long)")
    out, caps, shift = [], False, False
    for _ in range(n):
        s = r.get(6)
        if s == SHIFT:
            shift = True
        elif s == CAPS:
            caps = not caps
        elif s == WORD:
            idx = r.get(8)
            out.append(WORDS[idx] if idx < len(WORDS) else "<word %d>" % idx)
            shift = False
        elif s == RAW:
            out.append(chr(r.get(8)))
            shift = False
        else:
            ch = _CHAR[s]
            if ch.isalpha() and (caps != shift):
                ch = ch.upper()
            out.append(ch)
            shift = False
    return "".join(out)


def text_bits(text: str) -> int:
    w = BitWriter()
    put_text(w, text)
    return len(w)


# ---- frame -----------------------------------------------------------------------
class Event:
    __slots__ = ("code", "sev", "count", "detail")

    def __init__(self, code: int, sev: int, count: int = 1, detail: Detail = None):
        self.code, self.sev, self.count, self.detail = code, sev, count, detail

    def __repr__(self) -> str:
        return "Event(%03d, sev=%d, count=%d, detail=%r)" % (self.code, self.sev, self.count, self.detail)

    def __eq__(self, other) -> bool:
        return isinstance(other, Event) and (self.code, self.sev, self.count, self.detail) == \
            (other.code, other.sev, other.count, other.detail)


class Frame:
    def __init__(self, events: List[Event], minute: int, session: int, rev: int,
                 app: Optional[str] = None, stats: Optional[Tuple[int, int, int]] = None, omitted: int = 0):
        self.events, self.minute, self.session, self.rev = events, minute, session, rev
        self.app, self.stats, self.omitted = app, stats, omitted

    def __eq__(self, other) -> bool:
        return isinstance(other, Frame) and vars_(self) == vars_(other)


def vars_(f: Frame) -> tuple:
    return (f.events, f.minute, f.session, f.rev, f.app, tuple(f.stats) if f.stats else None, f.omitted)


def _put_event(w: BitWriter, e: Event) -> None:
    if not 0 <= e.code <= MAX_CODE:
        raise EC2Error("code must be 000-999, got %r" % e.code)
    if not 0 <= e.sev <= 3:
        raise EC2Error("severity must be 0-3")
    w.put(e.code, CODE_BITS)
    w.put(e.sev, 2)
    w.gamma(max(1, e.count) - 1)
    d = e.detail
    if d is None or d == "":
        w.put(0, 2)
    elif isinstance(d, bool) or not isinstance(d, (int, str)):
        raise EC2Error("detail must be None, int or str")
    elif isinstance(d, int):
        if d >= 0:
            w.put(1, 2)
            w.gamma(d)
        else:
            w.put(3, 2)
            w.gamma(-d - 1)
    else:
        w.put(2, 2)
        put_text(w, d)


def event_bits(e: Event) -> int:
    w = BitWriter()
    _put_event(w, e)
    return len(w)


def encode_frame(f: Frame) -> BitWriter:
    w = BitWriter()
    w.gamma(f.rev)
    w.put(f.minute, MINUTE_BITS)
    w.put(f.session, SESSION_BITS)
    w.put(1 if f.app else 0, 1)
    w.put(1 if f.stats else 0, 1)
    w.put(1 if f.omitted else 0, 1)
    if f.app:
        put_text(w, f.app)
    if f.stats:
        for v in f.stats:
            w.gamma(v)
    if f.omitted:
        w.gamma(f.omitted)
    w.gamma(len(f.events))
    for e in f.events:
        _put_event(w, e)
    return w


def decode_frame(bits: Sequence[int]) -> Frame:
    r = BitReader(bits)
    rev = r.gamma()
    minute = r.get(MINUTE_BITS)
    session = r.get(SESSION_BITS)
    has_app, has_stats, has_omit = r.get(1), r.get(1), r.get(1)
    app = get_text(r) if has_app else None
    stats = (r.gamma(), r.gamma(), r.gamma()) if has_stats else None
    omitted = r.gamma() if has_omit else 0
    n = r.gamma()
    if n > 10000:
        raise EC2Error("damaged report (event count)")
    events = []
    for _ in range(n):
        code = r.get(CODE_BITS)
        if code > MAX_CODE:
            raise EC2Error("code %d uses an extension this decoder does not know - update errcode" % code)
        sev = r.get(2)
        count = r.gamma() + 1
        tag = r.get(2)
        detail: Detail = None
        if tag == 1:
            detail = r.gamma()
        elif tag == 2:
            detail = get_text(r)
        elif tag == 3:
            detail = -r.gamma() - 1
        events.append(Event(code, sev, count, detail))
    if any(r.bits[r.pos:]):
        # padding must be zero; anything else means the digits do not belong together
        raise EC2Error("unexpected data after the last event - parts from different reports mixed?")
    return Frame(events, minute, session, rev, app, stats, omitted)


# ---- bits <-> digits ---------------------------------------------------------------
def to_digits(w: BitWriter) -> str:
    bits = w.bits
    out = []
    for start in range(0, len(bits), CHUNK_BITS):
        chunk = bits[start:start + CHUNK_BITS]
        if len(chunk) == CHUNK_BITS:
            k, nbits = DATA_DIGITS, CHUNK_BITS
        else:
            k = _digits_for(len(chunk))
            nbits = _CAP[k]
        v = 0
        for b in chunk:
            v = (v << 1) | b
        v <<= nbits - len(chunk)                 # zero padding goes at the end of the stream
        body = str(v).zfill(k)
        out.append(body + damm(body))
    return "".join(out)


def from_digits(digits: str) -> List[int]:
    if not digits or not digits.isdigit():
        raise EC2Error("no digits found")
    if len(digits) % BLOCK_DIGITS == 1:
        raise EC2Error("the last block is 1 digit long - a digit is missing or extra somewhere")
    bits: List[int] = []
    for bi, start in enumerate(range(0, len(digits), BLOCK_DIGITS)):
        block = digits[start:start + BLOCK_DIGITS]
        if not damm_ok(block):
            raise BlockCheckError(bi + 1, start + 1, start + len(block))
        k = len(block) - 1
        nbits = CHUNK_BITS if k == DATA_DIGITS else _CAP[k]
        v = int(block[:-1])
        if v >= 1 << nbits:
            raise BlockCheckError(bi + 1, start + 1, start + len(block))
        bits.extend((v >> (nbits - 1 - i)) & 1 for i in range(nbits))
    return bits


def digits_for_bits(nbits: int) -> int:
    """How many digits a stream of nbits becomes (for budgeting)."""
    full, rest = divmod(nbits, CHUNK_BITS)
    return full * BLOCK_DIGITS + ((_digits_for(rest) + 1) if rest else 0)


# ---- text forms --------------------------------------------------------------------
def single(digits: str) -> str:
    return "%s-%s" % (PREFIX, digits)


def split_parts(digits: str, part_digits: int, set_id: int) -> List[str]:
    """Cut into QR-sized parts on block boundaries; one part -> plain 'EC2-...'."""
    per = max(1, part_digits // BLOCK_DIGITS) * BLOCK_DIGITS
    chunks = [digits[i:i + per] for i in range(0, len(digits), per)] or [""]
    if len(chunks) == 1:
        return [single(digits)]
    if len(chunks) > MAX_PARTS:
        raise EC2Error("report needs %d parts; at most %d - raise part_digits or lower the budget"
                       % (len(chunks), MAX_PARTS))
    n = len(chunks)
    return ["%s/%d%d%03d-%s" % (PREFIX, i + 1, n, set_id % 1000, c) for i, c in enumerate(chunks)]


def pretty(digits: str, per_line: int = 1) -> str:
    """Blocks shown as 4 groups of 5 for reading aloud: '12345 67890 12345 67890'."""
    blocks = [digits[i:i + BLOCK_DIGITS] for i in range(0, len(digits), BLOCK_DIGITS)]
    shown = [" ".join(b[j:j + 5] for j in range(0, len(b), 5)) for b in blocks]
    lines = ["   ".join(shown[i:i + per_line]) for i in range(0, len(shown), per_line)]
    return "\n".join(lines)


_PART = re.compile(r"EC2(?:/([1-9])([1-9])(\d{3}))?-?([\d\s.\-_]*)", re.I)


def find(text: str) -> List[Tuple[int, int, int, str]]:
    """All EC2 pieces in text (also inside a URL): [(part, of, set, digits)]."""
    out = []
    for m in _PART.finditer(text):
        digits = re.sub(r"\D", "", m.group(4))
        if not digits:
            continue
        if m.group(1):
            out.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), digits))
        else:
            out.append((1, 1, -1, digits))
    return out


def is_ec2(text: str) -> bool:
    return bool(find(text.upper()))


def join_parts(texts: Iterable[str]) -> str:
    """Pieces in any order -> the full digit string. Raises EC2Error if incomplete."""
    pieces = []
    for t in texts:
        pieces.extend(find(t.upper()))
    if not pieces:
        raise EC2Error("no EC2 report found")
    if len(pieces) == 1 and pieces[0][1] == 1:
        return pieces[0][3]
    n = pieces[0][1]
    sets = {p[2] for p in pieces}
    if len(sets) != 1 or any(p[1] != n for p in pieces):
        raise EC2Error("these parts come from different reports")
    have = {p[0]: p[3] for p in pieces}
    missing = [i for i in range(1, n + 1) if i not in have]
    if missing:
        raise EC2Error("still need part(s) %s of %d" % (", ".join(map(str, missing)), n))
    return "".join(have[i] for i in range(1, n + 1))


def encode(frame: Frame) -> str:
    return to_digits(encode_frame(frame))


def decode(text_or_parts: Union[str, Iterable[str]]) -> Frame:
    texts = [text_or_parts] if isinstance(text_or_parts, str) else list(text_or_parts)
    return decode_frame(from_digits(join_parts(texts)))
