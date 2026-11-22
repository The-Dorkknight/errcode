# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Compact code format.

One failure = ONE 4-character code (20 bits, Crockford base32):

    [ domain:3 ][ severity:2 ][ entry id:12 ][ check:3 ]

  * domain   - which dictionary (Python, Windows, Linux, ...), see table.DOMAINS
  * severity - 0 ok, 1 warn, 2 error, 3 fatal (so a scanner can rank codes even
               if it has an older/newer dictionary than the sender)
  * entry id - index into that domain (4096 per domain, 32768 in total)
  * check    - 3-bit XOR fold; catches every single-bit slip and ~7 in 8 random
               mis-reads. Crockford base32 also folds O->0, I/L->1 so hand-typed
               codes forgive the usual confusions.

A whole report multiplexes many codes plus a date and session tag into one
short string, which is also what goes in the QR code:

    EC1-<TIME:5><SESSION:3>-<CODE:4><CODE:4>...
    e.g. EC1-00A3F9KQ2-7K3M4Q2P

  * TIME    - minutes since 2026-01-01 00:00 UTC (5 chars = 63 years; no "20xx",
              and the hour/minute travel inside the QR too)
  * SESSION - random 15-bit tag so a longer log can be looked up elsewhere
  * CODEs   - worst first
Only characters valid for QR alphanumeric mode are used (0-9 A-Z -), which is
the densest QR encoding, so even 12 codes stay a small, easy-to-scan symbol.
"""
from __future__ import annotations

import datetime
import secrets
from typing import List, Optional, Tuple

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"   # Crockford: no I L O U
_DECODE = {c: i for i, c in enumerate(ALPHABET)}
_DECODE.update({"O": 0, "I": 1, "L": 1})

PREFIX = "EC1"
EPOCH = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
MAX_CODES = 12


class CodecError(ValueError):
    pass


def b32_encode(value: int, width: int) -> str:
    if not 0 <= value < 32 ** width:
        raise CodecError("value %r does not fit in %d base32 chars" % (value, width))
    out = []
    for _ in range(width):
        out.append(ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(out))


def b32_decode(text: str) -> int:
    value = 0
    for ch in text.upper():
        try:
            value = (value << 5) | _DECODE[ch]
        except KeyError:
            raise CodecError("invalid character %r" % ch)
    return value


def _check(body17: int) -> int:
    c = 0
    while body17:
        c ^= body17 & 7
        body17 >>= 3
    return c


def pack(domain: int, sev: int, entry: int) -> str:
    """(domain, severity, entry id) -> 4-char code."""
    if not 0 <= domain < 8:
        raise CodecError("domain must be 0..7")
    if not 0 <= sev < 4:
        raise CodecError("severity must be 0..3")
    if not 0 <= entry < 4096:
        raise CodecError("entry id must be 0..4095")
    body = (domain << 14) | (sev << 12) | entry
    return b32_encode((body << 3) | _check(body), 4)


def unpack(code: str) -> Tuple[int, int, int, bool]:
    """4-char code -> (domain, severity, entry id, checksum_ok)."""
    code = normalise(code)
    if len(code) != 4:
        raise CodecError("a code is exactly 4 characters, got %r" % code)
    value = b32_decode(code)
    body, chk = value >> 3, value & 7
    return body >> 14, (body >> 12) & 3, body & 0xFFF, _check(body) == chk


def normalise(text: str) -> str:
    """Upper-case and strip separators people add when reading codes aloud."""
    return "".join(ch for ch in text.upper() if ch not in " -._\t\r\n")


# ---- time and sessions --------------------------------------------------

def minute_number(now: Optional[datetime.datetime] = None) -> int:
    """Minutes since 2026-01-01 00:00 UTC (the time stamp carried in a report)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.astimezone()                     # naive = local time
    n = int((now - EPOCH).total_seconds() // 60)
    if not 0 <= n < 32 ** 5:
        raise CodecError("time outside the supported range (2026-01-01 + 63 years)")
    return n


def time_from_minute(n: int) -> datetime.datetime:
    """Inverse of minute_number(); returns an aware UTC datetime."""
    return EPOCH + datetime.timedelta(minutes=n)


def format_when(utc: datetime.datetime) -> str:
    """'2026-10-02 10:36 UTC  |  11:36 local' - local = the viewing machine's time zone."""
    local = utc.astimezone()
    return "%s UTC  |  %s local" % (utc.strftime("%Y-%m-%d %H:%M"), local.strftime("%Y-%m-%d %H:%M"))


def new_session() -> int:
    return secrets.randbits(15)


# ---- multiplexed report string ------------------------------------------

def build_payload(codes: List[str], minute: int, session: int) -> str:
    if len(codes) > MAX_CODES:
        raise CodecError("at most %d codes per report" % MAX_CODES)
    return "%s-%s%s-%s" % (PREFIX, b32_encode(minute, 5), b32_encode(session, 3), "".join(codes))


def is_payload(text: str) -> bool:
    return text.strip().upper().startswith(PREFIX + "-")


def parse_payload(text: str) -> Tuple[int, int, List[str]]:
    """'EC1-...' -> (minute number, session, [4-char codes]). Raises CodecError."""
    parts = text.strip().upper().split("-")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise CodecError("not an %s report string" % PREFIX)
    stamp, codes = normalise(parts[1]), normalise(parts[2])
    if len(stamp) != 8:
        raise CodecError("time/session part must be 8 characters")
    if len(codes) % 4 or not codes:
        raise CodecError("codes must be groups of 4 characters")
    return b32_decode(stamp[:5]), b32_decode(stamp[5:]), [codes[i:i + 4] for i in range(0, len(codes), 4)]
