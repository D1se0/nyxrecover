"""Raw scan engine — signatures + entropy + carve candidate location.

Reads a device or image file sequentially in large chunks (O(1) memory),
finds signature matches and entropy anomalies, and emits carve candidates
(headers + footers) which the recovery engine then extracts and validates.
"""
from __future__ import annotations

import math
import os
import threading
import time
from pathlib import Path

from .signatures import SIGS

CHUNK = 8 * 1024 * 1024
OVERLAP = 4096  # keep tail so signatures spanning chunk borders are found


def shannon(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    ent = 0.0
    for c in counts:
        if c:
            p = c / n
            ent -= p * math.log2(p)
    return ent


class ScanStats:
    def __init__(self):
        self.bytes_read = 0
        self.candidates = 0
        self.started = time.time()
        self.finished = None
        self.lock = threading.Lock()

    @property
    def elapsed(self) -> float:
        end = self.finished or time.time()
        return max(end - self.started, 1e-9)

    @property
    def speed(self) -> float:
        return self.bytes_read / self.elapsed


def _find_hits(window: bytes) -> list:
    """Find every signature occurrence in window via native bytes.find."""
    out = []
    for s in SIGS:
        h = s.header
        start = 0
        while True:
            i = window.find(h, start)
            if i < 0:
                break
            out.append((i, s))
            start = i + 1
            if len(out) > 200000:
                return out
    return out


def scan_raw(source: str, progress=None, entropy=False, cancel=None,
             max_results: int = 50000) -> dict:
    """Sequential multi-signature scan.

    source: /dev/node or path to an .img/.dd file.
    Returns dict with hits, candidates, entropy anomalies and stats.
    """
    import math
    p = Path(source)
    from nyx.nyxcore.device import media_size
    size = media_size(str(p))

    hits = []
    candidates = []
    entropy_anomalies = []
    stats = ScanStats()

    with open(source, "rb", buffering=0) as fh:
        pos = 0
        prev_tail = b""
        prev_tail_off = 0
        while pos < size:
            if cancel and cancel.is_set():
                break
            to_read = min(CHUNK, size - pos)
            buf = fh.read(to_read)
            if not buf:
                break
            window = prev_tail + buf
            win_off = prev_tail_off

            for i, s in _find_hits(window):
                abs_off = win_off + i
                hits.append({"sig": s.sid, "name": s.name, "ext": s.ext,
                             "cat": s.cat, "offset": abs_off})
                candidates.append({"sig": s.sid, "offset": abs_off, "end": None})
                if len(hits) >= max_results:
                    break
            if len(hits) >= max_results:
                break

            if entropy:
                ent = shannon(buf[: min(len(buf), 1024 * 1024)])
                if ent > 7.90:
                    entropy_anomalies.append(
                        {"offset": pos, "entropy": round(ent, 3),
                         "size": min(len(buf), 1024 * 1024)})

            prev_tail = buf[-OVERLAP:]
            prev_tail_off = pos + len(buf) - OVERLAP
            pos += len(buf)
            stats.bytes_read = pos
            if progress:
                progress(pos, size)

    stats.finished = time.time()
    stats.candidates = len(candidates)
    return {"source": source, "size": size, "hits": hits,
            "candidates": candidates, "entropy_anomalies": entropy_anomalies,
            "stats": stats, "elapsed": stats.elapsed, "speed": stats.speed,
            "cancelled": bool(cancel and cancel.is_set())}


def scan_image_file(path: str, **kw) -> dict:
    return scan_raw(path, **kw)
