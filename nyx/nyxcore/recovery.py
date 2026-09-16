"""Recovery engine — turns scan candidates and FS metadata into real files.

Three strategies:
  * carve: signature-based extraction (footer-aware, sanity-checked).
  * selective: user picks entries from a tree walk (ext/fat/ntfs).
  * full: export everything alive AND every recoverable deleted entry.

Recovered bytes go to an output dir with a session subfolder, and a
manifest.json records provenance for every file (source, offset, inode,
method, sha256) — the chain of custody of what you rescued.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from . import scan as scanmod
from .signatures import by_id, refine_ooxml
from .device import human_size

CARVE_EXT_FROM_SIG = {"jpeg": "jpg", "png": "png", "gif": "gif", "gif89a": "gif",
                      "pdf": "pdf", "zip": "zip", "zip_eof": "zip", "gzip": "gz",
                      "sqlite": "sqlite", "elf": "elf"}

# Signatures safe for blind carving on real media: >=4-byte headers or
# validated containers. Short/ambiguous magics are excluded by default
# (they explode into millions of false positives on 10 GB disks).
CARVE_SIGS = {"jpeg", "png", "gif", "gif89a", "pdf", "zip", "zip_eof",
              "gzip", "xz", "bzip2", "7z", "rar", "sqlite", "elf", "mp4",
              "mkv", "flac", "ogg", "iso", "ole", "luks", "rtf"}


def _session_dir(outdir: str, source: str) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe = Path(source).name.replace("/", "_").replace("!", "_")
    d = Path(outdir) / f"nyx-{safe}-{stamp}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sha256_file(path: Path, limit: int = 64 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


class RecoveryEngine:
    def __init__(self, source: str, outdir: str):
        self.source = source
        self.outdir = outdir
        self.cancel = None
        self.session = None
        self.manifest = []
        self.stats = {"recovered": 0, "failed": 0, "bytes": 0,
                      "skipped_empty": 0}

    # ── Carving ───────────────────────────────────────────────────────────
    def carve(self, progress=None, min_size: int = 128,
              max_file_size: int = 512 * 1024 * 1024) -> dict:
        """Signature carving with footer-aware end detection.

        Streams the medium in chunks; matches signatures through a 2-byte
        prefix index with full-header verification (any header length).
        """
        from nyx.nyxcore.signatures import SIGS
        footer_of = {}
        prefix_index = {}
        for s in SIGS:
            if s.sid not in CARVE_SIGS:
                continue
            if s.footer:
                footer_of.setdefault(s.header, s.footer)
            if s.sid == "mp4":
                # '00 00' prefix matches every zero run on disk; index by
                # the real brand mark instead and back up 4 bytes (box size)
                prefix_index.setdefault(b"ftyp", []).append((s, 4))
                continue
            prefix_index.setdefault(s.header[:2], []).append((s, 0))
        for lst in prefix_index.values():
            lst.sort(key=lambda x: -len(x[0].header))

        self.session = _session_dir(self.outdir, self.source)
        started = time.time()
        results = []
        from nyx.nyxcore.device import media_size
        size = media_size(self.source)
        CHUNK = 4 * 1024 * 1024

        def footer_length(fh, abs_off: int, sig) -> int:
            footer = footer_of.get(sig.header)
            cap = min(max_file_size, size - abs_off)
            default_cap = min(4 * 1024 * 1024, cap)
            if not footer:
                return default_cap
            hlen = len(sig.header)
            scanned = 0
            fh.seek(abs_off + hlen)
            while scanned < cap:
                buf = fh.read(min(CHUNK, cap - scanned))
                if not buf:
                    break
                end = buf.find(footer)
                if end >= 0:
                    return hlen + scanned + end + len(footer)
                scanned += max(len(buf) - len(footer) + 1, 1)
            return default_cap

        prefixes = list(prefix_index.keys())

        def next_hit(buf: bytes, start: int):
            """Nearest candidate position >= start using C-speed find."""
            best_i, best_cands = -1, None
            for pre in prefixes:
                i = buf.find(pre, start)
                if i >= 0 and (best_i < 0 or i < best_i):
                    best_i, best_cands = i, prefix_index[pre]
            return best_i, best_cands

        with open(self.source, "rb", buffering=0) as fh:
            pos = 0
            while pos < size:
                if self.cancel and self.cancel.is_set():
                    break
                fh.seek(pos)
                buf = fh.read(min(CHUNK, size - pos))
                if not buf:
                    break
                i = 0
                n = len(buf)
                advanced = 0
                last_resume = n  # where to continue when no more hits
                while i + 4 <= n:
                    i, cands = next_hit(buf, i)
                    if i < 0 or i + 4 > n:
                        break
                    sig = None
                    for s, back in cands:
                        start = i - back
                        if start < 0:
                            continue
                        if buf[start:start + len(s.header)] == s.header:
                            sig = s
                            i = start
                            break
                    if sig is None:
                        i += 1
                        continue
                    abs_off = pos + i
                    length = min(footer_length(fh, abs_off, sig), max_file_size)
                    if length < min_size:
                        i += 1
                        continue
                    fh.seek(abs_off)
                    data = fh.read(length)
                    ext_name = CARVE_EXT_FROM_SIG.get(sig.sid, sig.ext)
                    if sig.sid in ("zip", "zip_eof"):
                        ext_name = refine_ooxml(data)
                    if sig.sid == "webp" and data[8:12] != b"WEBP":
                        i += 1
                        continue
                    if sig.sid == "avi" and data[8:12] != b"AVI ":
                        i += 1
                        continue
                    if sig.sid == "wav" and data[8:12] != b"WAVE":
                        i += 1
                        continue
                    # Negative checks to cut false positives
                    if sig.sid == "ole" and data[24:26] not in (b"\x00\x03",
                                                                b"\x00\x04"):
                        i += 1
                        continue
                    if sig.sid == "rtf" and data[6:7] not in (b"a", b"A"):
                        i += 1
                        continue
                    count = self.stats["recovered"]
                    fname = f"{sig.sid}_{count:05d}.{ext_name}"
                    outp = self.session / "carved" / ext_name
                    outp.mkdir(parents=True, exist_ok=True)
                    outp = outp / fname
                    outp.write_bytes(data)
                    self.manifest.append({
                        "file": str(outp), "method": "carve", "sig": sig.sid,
                        "name": sig.name, "offset": abs_off, "size": len(data),
                        "sha256": _sha256_file(outp)})
                    results.append({"name": fname, "sig": sig.sid,
                                    "cat": sig.cat, "offset": abs_off,
                                    "size": len(data), "path": str(outp)})
                    self.stats["recovered"] += 1
                    self.stats["bytes"] += len(data)
                    i += max(len(data), 1)
                    advanced = i
                    last_resume = max(i, 0)
                    if progress:
                        progress(min(pos + i, size), size)
                if advanced > 0:
                    pos += advanced
                else:
                    pos += max(last_resume, 1)
                if progress:
                    progress(min(pos, size), size)
        return {"session": str(self.session), "count": len(results),
                "results": results,
                "duration_s": round(time.time() - started, 2),
                "stats": dict(self.stats)}

    # ── FS-aware recovery ─────────────────────────────────────────────────
    def recover_fs(self, include_alive: bool = False, only_paths=None,
                   progress=None, preserve_tree: bool = True) -> dict:
        """Recover deleted (and optionally alive) files using FS metadata."""
        from nyx.nyxfs import ext as extmod, vfat as fatmod, ntfs as ntfsmod
        from nyx.nyxfs import UnknownFilesystem, detect
        self.session = _session_dir(self.outdir, self.source)
        started = time.time()
        entries = []
        kind = None
        recovered = []
        with open(self.source, "rb", buffering=0) as fh:
            kind = detect(fh)
            fh.seek(0)
            if kind == "ext":
                sb = extmod.parse_superblock(fh)
                gds = extmod.read_group_descs(fh, sb)
                for e in extmod.walk_tree(fh, sb, gds):
                    if e["kind"] not in ("file", "dir"):
                        continue
                    if e["deleted"] or include_alive:
                        entries.append(("ext", e, {"sb": sb, "gds": gds}))
            elif kind == "fat":
                fat = fatmod.parse_bpb(fh)
                for e in fatmod.walk_root(fh, fat):
                    if e.deleted or include_alive:
                        entries.append(("fat", e, fat))
            elif kind == "ntfs":
                boot = ntfsmod.parse_boot(fh)
                for rec in ntfsmod.iter_mft(fh, boot):
                    if rec["num"] < 16:
                        continue
                    if not rec["in_use"] or include_alive:
                        entries.append(("ntfs", {
                            "path": "/" + rec["name"],
                            "deleted": not rec["in_use"],
                            "inode": rec["num"],
                            "kind": "dir" if rec["is_dir"] else "file",
                            "size": rec["size"], "_rec": rec}, boot))
            if only_paths:
                allowed = set(only_paths)
                entries = [t for t in entries
                           if (t[1].get("path") if isinstance(t[1], dict)
                               else getattr(t[1], "path", "")) in allowed]
            total = len(entries)
            for i, (kind2, e, meta) in enumerate(entries):
                if self.cancel and self.cancel.is_set():
                    break
                try:
                    if isinstance(e, dict):
                        path, deleted = e["path"], e["deleted"]
                        inode = e["inode"]
                    else:  # FAT entry object
                        path, deleted, inode = e.path, e.deleted, e.inode
                    data = self._fs_read(kind2, e, meta, fh)
                    if isinstance(e, dict):
                        is_dir = (e.get("kind") == "dir") if "kind" in e \
                            else e.get("is_dir", False)
                    else:
                        is_dir = e.is_dir
                    if not is_dir:
                        outp = self._write_recovered(path, data, deleted, kind2,
                                                     preserve_tree)
                        self.manifest.append({
                            "file": str(outp), "method": f"fs-{kind2}",
                            "source_path": path, "inode": inode,
                            "deleted": deleted, "size": len(data),
                            "sha256": _sha256_file(outp)})
                        recovered.append({"path": path, "size": len(data),
                                          "deleted": deleted, "out": str(outp)})
                    else:
                        recovered.append({"path": path + "/", "deleted": deleted})
                    self.stats["recovered"] += 1
                    self.stats["bytes"] += len(data)
                except Exception as ex:
                    self.stats["failed"] += 1
                    try:
                        p = e["path"] if isinstance(e, dict) else e.path
                    except Exception:
                        p = "?"
                    recovered.append({"path": p, "error": str(ex)})
                if progress:
                    progress(i + 1, total)
        return {"session": str(self.session), "kind": kind, "total": total,
                "count": len(recovered), "results": recovered,
                "duration_s": round(time.time() - started, 2),
                "stats": dict(self.stats)}

    def _fs_read(self, kind, e, meta, fh) -> bytes:
        from nyx.nyxfs import ext as extmod, vfat as fatmod, ntfs as ntfsmod
        if kind == "ext":
            sb, gds = meta["sb"], meta["gds"]
            node = extmod.read_inode(fh, sb, gds, e["inode"])
            return extmod.read_file_data(fh, sb, node)
        if kind == "fat":
            return fatmod.read_file(fh, meta, e)
        if kind == "ntfs":
            return ntfsmod.read_file_data(fh, meta, e["_rec"])
        raise ValueError(kind)

    def _write_recovered(self, path: str, data: bytes, deleted: bool,
                         kind: str, preserve_tree: bool) -> Path:
        rel = path.strip("/").replace("\\", "/") or "sin_nombre"
        sub = "deleted" if deleted else "alive"
        base = self.session / kind / sub
        if preserve_tree:
            outp = base / rel
        else:
            outp = base / Path(rel).name
        outp = outp.resolve()
        if not str(outp).startswith(str(self.session.resolve())):
            outp = base / "UNSAFE" / Path(rel).name
        outp.parent.mkdir(parents=True, exist_ok=True)
        i = 1
        while outp.exists():
            outp = outp.with_name(f"{outp.stem}_dup{i}{outp.suffix}")
            i += 1
        outp.write_bytes(data)
        return outp

    def write_manifest(self) -> Path:
        p = self.session / "manifest.json"
        p.write_text(json.dumps({
            "tool": "NyxRecover", "version": "1.0.0",
            "source": self.source, "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stats": self.stats, "files": self.manifest}, indent=2,
            ensure_ascii=False))
        return p
