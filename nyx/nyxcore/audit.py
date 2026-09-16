"""Tamper-evident audit trail for every NyxRecover operation.

Each entry is appended to the session journal and hash-chained with SHA-256
(entry N includes the hash of N-1), so any later modification or deletion of
a line is detectable — a must when recovery output is used as evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from pathlib import Path

LAIR = Path(os.environ.get("NYX_HOME", Path.home() / ".nyxrecover"))
GENESIS = "0" * 64


def _ensure(lair: Path | None = None) -> Path:
    root = Path(lair) if lair else LAIR
    (root / "journal").mkdir(parents=True, exist_ok=True)
    return root


def _hash_entry(prev: str, ts: float, event: str, payload: dict) -> str:
    blob = json.dumps({"prev": prev, "ts": ts, "event": event,
                       "payload": payload}, sort_keys=True,
                      default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def log(event: str, payload: dict | None = None, lair: Path | None = None,
        session: str | None = None) -> str:
    root = _ensure(lair)
    ts = time.time()
    payload = payload or {}
    jdir = root / "journal"
    fname = f"{session or time.strftime('%Y%m%d')}.jsonl"
    jpath = jdir / fname
    prev = GENESIS
    if jpath.exists():
        lines = jpath.read_text().splitlines()
        for line in reversed(lines):
            line = line.strip()
            if line:
                try:
                    prev = json.loads(line)["hash"]
                except Exception:
                    pass
                break
    h = _hash_entry(prev, ts, event, payload)
    entry = {"ts": ts, "iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
             "host": platform.node(), "user": os.environ.get("USER", ""),
             "event": event, "payload": payload, "prev": prev, "hash": h}
    with open(jpath, "a") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")
    return h


def verify(lair: Path | None = None, session: str | None = None) -> dict:
    """Recompute the chain; report the first tampered line, if any."""
    root = _ensure(lair)
    jpath = root / "journal" / f"{session or time.strftime('%Y%m%d')}.jsonl"
    if not jpath.exists():
        return {"ok": True, "entries": 0, "first_bad": None}
    prev = GENESIS
    entries = 0
    first_bad = None
    for i, line in enumerate(jpath.read_text().splitlines()):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except Exception:
            first_bad = first_bad or i + 1
            break
        expected = _hash_entry(prev, e["ts"], e["event"], e["payload"])
        if e["prev"] != prev or e["hash"] != expected:
            first_bad = first_bad or i + 1
            break
        prev = e["hash"]
        entries += 1
    return {"ok": first_bad is None, "entries": entries, "first_bad": first_bad,
            "path": str(jpath)}


def sessions(lair: Path | None = None) -> list:
    root = _ensure(lair)
    out = []
    for p in sorted((root / "journal").glob("*.jsonl")):
        n = sum(1 for l in p.read_text().splitlines() if l.strip())
        out.append({"file": p.name, "entries": n, "path": str(p)})
    return out
