"""Keyword search over raw bytes (device or image) with context extraction."""
from __future__ import annotations

import os
import re
import time

CHUNK = 8 * 1024 * 1024
OVERLAP = 1024


def search(source: str, keywords: list, progress=None, cancel=None,
           context: int = 64, case_sensitive: bool = False,
           max_hits: int = 10000) -> dict:
    """Stream-search raw media for keywords; returns hits with text context."""
    flags = 0 if case_sensitive else re.IGNORECASE
    pats = [(kw, re.compile(re.escape(kw.encode()), flags)) for kw in keywords]
    from nyx.nyxcore.device import media_size
    size = media_size(source)
    hits = []
    started = time.time()
    with open(source, "rb", buffering=0) as fh:
        pos = 0
        tail = b""
        tail_off = 0
        while pos < size:
            if cancel and cancel.is_set():
                break
            buf = fh.read(min(CHUNK, size - pos))
            if not buf:
                break
            window = tail + buf
            win_off = tail_off
            for kw, pat in pats:
                for m in pat.finditer(window):
                    o = win_off + m.start()
                    s = max(0, m.start() - context)
                    e = min(len(window), m.end() + context)
                    snippet = window[s:e]
                    hits.append({"keyword": kw, "offset": o,
                                 "context": snippet.decode("latin-1", "replace"),
                                 "match": m.group(0).decode("latin-1", "replace")})
                    if len(hits) >= max_hits:
                        break
                if len(hits) >= max_hits:
                    break
            tail = buf[-OVERLAP:]
            tail_off = pos + len(buf) - OVERLAP
            pos += len(buf)
            if progress:
                progress(pos, size)
    return {"source": source, "size": size, "keywords": keywords,
            "hits": hits, "total": len(hits),
            "duration_s": round(time.time() - started, 2),
            "cancelled": bool(cancel and cancel.is_set())}
