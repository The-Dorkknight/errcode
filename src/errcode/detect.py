# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Turn raw material (log text, exceptions, exit codes) into ranked dictionary hits.

Pipeline for text:
  1. split into lines, drop inconsequential noise (progress bars, "12%",
     download sizes/speeds, ETA, routine INFO/DEBUG chatter, blank/divider lines)
     - but NEVER drop a line that also contains a failure word, so
       "download failed at 12%" survives
  2. collapse repeated lines (digits normalised) so a retry loop counts once
  3. match what is left against the dictionary patterns
  4. rank: fatal -> error -> warn -> ok; wrapper/symptom entries are dropped when
     a specific cause was found; "ok/info" is dropped whenever anything failed
"""
from __future__ import annotations

import errno as _errno
import re
import traceback
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple, Union

from . import table
from .table import Entry

MAX_LINES = 20000          # of the lines left AFTER noise removal: head 5000 + tail 15000
MAX_LINE_LEN = 2000


@dataclass
class Hit:
    entry: Entry
    count: int = 1          # occurrences (after collapsing repeats)
    first: int = 0          # order of first sighting; lower = earlier
    sev: int = -1           # effective severity; defaults to the entry's own
    detail: Optional[Union[int, str]] = None   # e.g. the missing module's name (travels in EC2)

    def __post_init__(self):
        if self.sev < 0:
            self.sev = self.entry.sev


@dataclass
class ScanStats:
    lines: int = 0          # non-blank lines seen
    noise: int = 0          # dropped as inconsequential
    repeats: int = 0        # dropped as repeats of an earlier line

    def summary(self) -> str:
        return "%d lines scanned, %d noise and %d repeats ignored" % (self.lines, self.noise, self.repeats)


# A line containing any of these is never treated as noise.
_KEEP = re.compile(
    r"error|fail|fatal|exception|traceback|denied|refused|time[d ]?-?out|not found|cannot|can't|unable|"
    r"no such|invalid|killed|segmentation|abort|panic|critical|warning|errno|winerror|0x[cC]0[0-9a-fA-F]{6}|"
    r"alloc|sig(?:segv|ill|abrt|kill)|undefined|unresolved|missing|unsupported|reset|unreach|unrecogni|"
    r"corrupt|overflow|illegal|incompatible|mismatch|not (?:valid|installed|allowed|permitted|authori[sz]ed)|"
    r"permission|blocked|quarantine|deprecat", re.I)

# Lines that are certainly a problem even if no dictionary entry matches them.
_STRONG = re.compile(r"\b(?:error|fatal|exception|traceback|critical|panic)\b|\bfailed\b|segmentation fault", re.I)
_CLEAN = re.compile(r"\b(?:no|without|0|zero)\s+(?:\w+\s+)?errors?\b", re.I)

_NOISE = [re.compile(p, re.I) for p in (
    r"\d{1,3}(?:\.\d+)?\s?%",                                             # 12%  45.3 %
    r"[#=>.\- █-▏░-▓━╺╸]{10,}",         # progress bars
    r"\b\d+(?:\.\d+)?\s?[kmgt]i?b(?:/s|ps)?\b",                            # 3.1 MB  2.4MB/s
    r"\beta\b",
    r"^\s*(?:downloading|collecting|using cached|requirement already satisfied|building wheel|"
    r"preparing metadata|installing collected|obtaining|resolving|fetching|unpacking|extracting|"
    r"processing|reading package lists|building dependency tree|get:\d+|hit:\d+|ign:\d+|"
    r"selecting previously|preparing to unpack|setting up|created wheel|stored in directory|running setup)\b",
    r"^\s*\[?(?:debug|info|trace|verbose)\]?[:\s\]]",                      # routine log chatter
    r"^\s*(?:\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?|\d{4}-\d{2}-\d{2}[ t]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s*$",
    r"^\W*$",                                  # no letters/digits at all: dividers, spinners, bars
)]
_DIGITS = re.compile(r"\d+")
_WARN_PREFIX = re.compile(r"^\W*warn(?:ing)?\b", re.I)

MAX_DETAIL = 40            # characters kept from a captured detail / unknown line
_PATH_TAIL = re.compile(r"[^/\\]+$")
_LINE_PREFIX = re.compile(r"^\W*(?:\d{4}-\d\d-\d\d[ T][\d:.,]+\S*|\d\d:\d\d:\d\d[.,\d]*)?\s*"
                          r"(?:\[?(?:error|fatal|critical|err)\]?[:\s]+)?", re.I)


def clean_detail(value) -> Optional[Union[int, str]]:
    """Make a captured detail short: ints stay ints, paths keep their last part, text is trimmed."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    s = str(value).strip().strip("'\"`").strip()
    if not s:
        return None
    if re.fullmatch(r"-?\d{1,12}", s):
        return int(s)
    if ("/" in s or "\\" in s) and len(s) > 12:
        tail = _PATH_TAIL.search(s.rstrip("/\\"))
        s = tail.group(0) if tail else s
    return s[:MAX_DETAIL]


def _unknown_detail(line: str) -> Optional[str]:
    return clean_detail(_LINE_PREFIX.sub("", line, count=1)[:MAX_DETAIL])


def _entries_for(table_entries):
    return [e for e in table_entries if e.patterns]


_PATTERN_ENTRIES = _entries_for(table.ENTRIES)
# One combined regex rejects the (many) lines that match nothing, before the per-entry pass.
_ANY = re.compile("|".join("(?:%s)" % p.pattern.replace("(?P<d>", "(?:")
                           for e in _PATTERN_ENTRIES for p in e.patterns), re.I | re.M)
_ERRNO_INDEX: Dict[str, List[Entry]] = {}
_WINERR_INDEX: Dict[int, List[Entry]] = {}
for _e in table.ENTRIES:
    if _e.errno_name:
        _ERRNO_INDEX.setdefault(_e.errno_name, []).append(_e)
    if _e.winerr:
        _WINERR_INDEX.setdefault(_e.winerr, []).append(_e)
del _e

# process exit codes -> entry keys
_RC_POSIX = {137: "LIN.OOM_KILLED", -9: "LIN.OOM_KILLED", 139: "CPP.SEGFAULT", -11: "CPP.SEGFAULT",
             132: "CPP.ILLEGAL_INSTRUCTION", -4: "CPP.ILLEGAL_INSTRUCTION",
             134: "CPP.ABORT", -6: "CPP.ABORT"}
_RC_NT = {0xC0000135: "WIN.STATUS_DLL_NOT_FOUND", 0xC000007B: "WIN.STATUS_BAD_IMAGE",
          0xC0000005: "WIN.ACCESS_VIOLATION", 0xC00000FD: "WIN.STACK_OVERFLOW_NT",
          0xC0000409: "WIN.STACK_BUFFER_OVERRUN", 0xC0000142: "WIN.DLL_INIT_FAILED",
          0xC0000374: "WIN.STATUS_HEAP_CORRUPTION", 0xC000001D: "WIN.STATUS_ILLEGAL_INSTRUCTION",
          0xC0000017: "WIN.STATUS_NO_MEMORY", 0xC000013A: "WIN.CTRL_C_EXIT"}
_RC_POSIX.update({136: "CPP.FPE", -8: "CPP.FPE", 135: "CPP.BUS_ERROR", -7: "CPP.BUS_ERROR"})


# --------------------------------------------------------------------------
def clean_lines(text: str) -> Tuple[List[str], List[int], ScanStats]:
    """Return (kept lines, repeat counts, stats) after noise removal."""
    raw = [s for s in re.split(r"[\r\n]+", text) if s.strip()]
    stats = ScanStats(lines=len(raw))
    kept: List[str] = []
    counts: List[int] = []
    index: Dict[str, int] = {}
    for line in raw:
        s = line.strip()[:MAX_LINE_LEN]
        if not _KEEP.search(s) and any(p.search(s) for p in _NOISE):
            stats.noise += 1
            continue
        key = _DIGITS.sub("#", s)
        if key in index:
            counts[index[key]] += 1
            stats.repeats += 1
            continue
        index[key] = len(kept)
        kept.append(s)
        counts.append(1)
    # Noise/repeats are removed from the WHOLE log first (cheap); only if what is left is still
    # huge do we keep the head and the tail, so a failure in the middle of a long log is not lost.
    if len(kept) > MAX_LINES:
        head = 5000
        kept = kept[:head] + kept[-(MAX_LINES - head):]
        counts = counts[:head] + counts[-(MAX_LINES - head):]
    return kept, counts, stats


def merge(into: Dict[str, Hit], hits: Iterable[Hit]) -> None:
    for h in hits:
        cur = into.get(h.entry.key)
        if cur is None:
            into[h.entry.key] = Hit(h.entry, h.count, h.first, h.sev, h.detail)
        else:
            cur.count += h.count
            if h.first < cur.first and h.detail is not None:
                cur.detail = h.detail
            elif cur.detail is None:
                cur.detail = h.detail
            cur.first = min(cur.first, h.first)
            cur.sev = max(cur.sev, h.sev)


def scan_text(text: str, unknown: bool = True) -> Tuple[List[Hit], ScanStats]:
    """Scan log text. Returns UNRANKED hits (see rank()) and noise statistics."""
    lines, counts, stats = clean_lines(text)
    found: Dict[str, Hit] = {}
    first_unknown = None
    entries, any_re = _matchers()
    for i, (line, cnt) in enumerate(zip(lines, counts)):
        matched = False
        if any_re.search(line):
            # A line the producer itself labels "WARNING:" is capped at warn (e.g. a retry that recovered).
            warn_only = bool(_WARN_PREFIX.match(line))
            for e in entries:
                for p in e.patterns:
                    m = p.search(line)
                    if m:
                        d = clean_detail(m.groupdict().get("d")) if p.groupindex else None
                        merge(found, [Hit(e, cnt, i, min(e.sev, table.WARN) if warn_only else -1, d)])
                        matched = True
                        break
        if unknown and not matched and first_unknown is None \
                and _STRONG.search(line) and not _CLEAN.search(line):
            first_unknown = i
    if first_unknown is not None:
        merge(found, [Hit(table.get("GEN.UNKNOWN"), 1, first_unknown, -1, _unknown_detail(lines[first_unknown]))])
    return list(found.values()), stats


def hits_from_exception(exc: BaseException) -> List[Hit]:
    """Structured (errno / WinError) hits plus a scan of the formatted traceback."""
    found: Dict[str, Hit] = {}
    seen = set()
    e: Optional[BaseException] = exc
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        en = getattr(e, "errno", None)
        name = _errno.errorcode.get(en) if isinstance(en, int) else None
        fname = clean_detail(getattr(e, "filename", None)) if isinstance(e, OSError) else None
        for entry in _ERRNO_INDEX.get(name, ()):
            merge(found, [Hit(entry, 1, -1, -1, fname)])
        if isinstance(e, ImportError) and getattr(e, "name", None):
            merge(found, [Hit(table.get("PY.MODULE_MISSING") if isinstance(e, ModuleNotFoundError)
                              else table.get("PY.IMPORT_NAME"), 1, -1, -1, clean_detail(e.name))])
        we = getattr(e, "winerror", None)
        for entry in _WINERR_INDEX.get(we, ()):
            merge(found, [Hit(entry, 1, -1)])
        e = e.__cause__ or e.__context__
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    merge(found, scan_text(text)[0])
    return list(found.values())


def hits_from_returncode(rc: Optional[int]) -> List[Hit]:
    if rc is None or rc == 0:
        return []
    key = _RC_POSIX.get(rc) or _RC_NT.get(rc & 0xFFFFFFFF)
    if key:
        return [Hit(table.get(key), 1, -1)]
    return [Hit(table.get("GEN.EXIT_NONZERO"), 1, -1, -1, rc)]


def hit_for_key(key: str, sev: Optional[int] = None, detail=None) -> Hit:
    """An app-set code, e.g. hit_for_key('HW.GPU_FALLBACK') or hit_for_key('PY.MODULE_MISSING', detail='numpy')."""
    return Hit(table.get(key), 1, 0, -1 if sev is None else sev, clean_detail(detail))


_MATCH_CACHE = {"n": len(table.ENTRIES), "v": (_PATTERN_ENTRIES, _ANY)}


def _matchers():
    """Entries + prefilter, rebuilt if define_app() added entries with patterns."""
    if _MATCH_CACHE["n"] != len(table.ENTRIES):
        ents = _entries_for(table.ENTRIES)
        any_re = re.compile("|".join("(?:%s)" % p.pattern.replace("(?P<d>", "(?:") for e in ents for p in e.patterns),
                            re.I | re.M)
        _MATCH_CACHE.update(n=len(table.ENTRIES), v=(ents, any_re))
    return _MATCH_CACHE["v"]


# --------------------------------------------------------------------------
def rank(hits: Iterable[Hit]) -> List[Hit]:
    """Order worst-first and discard what does not matter.

    * entries superseded by a more specific one are removed
    * wrapper/symptom ("generic") entries are removed when a specific cause exists
    * GEN.UNKNOWN is removed when anything else was found (when it stays, its detail is
      the text of the first unrecognised error line)
    * ok/info entries are removed when anything at warn or above exists
    * sort: fatal, error, warn, ok; ties by first appearance (root causes come first)
    """
    by_key: Dict[str, Hit] = {}
    merge(by_key, hits)
    drop = set()
    for h in by_key.values():
        drop.update(h.entry.supersedes)
    live = [h for k, h in by_key.items() if k not in drop]
    specific = [h for h in live if not h.entry.generic]
    if specific:
        live = specific
    elif len(live) > 1:
        live = [h for h in live if h.entry.key != "GEN.UNKNOWN"]
    if any(h.sev >= table.WARN for h in live):
        live = [h for h in live if h.sev >= table.WARN]
    live.sort(key=lambda h: (-h.sev, h.first, h.entry.domain, h.entry.id))
    return live
