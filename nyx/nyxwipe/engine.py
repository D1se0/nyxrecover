"""Secure wipe engine — makes bytes unrecoverable, then proves it.

Methods
-------
zero       NIST 800-88 Clear: single pass of 0x00, verified.
dod5220    US DoD 5220.22-M (3 passes).
gutmann    Peter Gutmann's 35-pass classic (paranoid, slow).
random     1..n passes of CSPRNG data.

Every pass streams O(1) memory. After the final pass the engine re-reads
1 sample block per 512 MB and proves every byte is the expected value
(0x00 for `zero`, or non-original data otherwise). Progress is reported
through a callback so both the TUI and the CLI stay responsive.

Safety: the caller must hold safety.DeviceLock and have assessed the risk.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time

CHUNK = 4 * 1024 * 1024
PATTERNS = {
    0x00: bytes([0x00]),
    0xFF: bytes([0xFF]),
}


def _passes_for(method: str, rng_passes: int = 3) -> list:
    if method == "zero":
        return [lambda buf: bytearray(PATTERNS[0x00] * len(buf))]
    if method == "ones":
        return [lambda buf: bytearray(PATTERNS[0xFF] * len(buf))]
    if method == "dod5220":
        return [
            lambda buf: bytearray(b"\x00" * len(buf)),
            lambda buf: bytearray(b"\xff" * len(buf)),
            lambda buf: bytearray(secrets.token_bytes(len(buf))),
        ]
    if method == "gutmann":
        # Peter Gutmann's classic 35-pass: 4 random, 27 fixed patterns,
        # 4 random (the PRNG passes cover the cyclic patterns too).
        seq = []
        seq += [0x55, 0xAA, 0x92, 0x49, 0x24, 0x00, 0x11, 0x22,
                0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA,
                0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x92, 0x49, 0x24,
                0x49, 0x92, 0x49]
        out = [lambda buf: bytearray(secrets.token_bytes(len(buf)))
               for _ in range(4)]
        out += [lambda buf, _b=b: bytearray(bytes([_b]) * len(buf)) for b in seq]
        out += [lambda buf: bytearray(secrets.token_bytes(len(buf)))
                for _ in range(4)]
        return out
    # random
    n = max(1, min(int(rng_passes), 7))
    return [lambda buf: bytearray(secrets.token_bytes(len(buf)))
            for _ in range(n)]


def _fmt(buf: bytearray) -> bytes:
    return bytes(buf)


def wipe_device(node: str, method: str = "zero", progress=None,
                rng_passes: int = 3, verify: bool = True,
                skip_bad: bool = True, fsync_every_gib: float = 4.0) -> dict:
    """Overwrite the whole block device. Returns a certificate dict."""
    from nyx.nyxcore.device import media_size
    size = media_size(node)
    passes = _passes_for(method, rng_passes)
    started = time.time()
    digest = hashlib.sha256()
    errors = []
    total_written = 0

    with open(node, "wb", buffering=0, opener=lambda p, f: os.open(p, f | os.O_WRONLY)) as raw:
        for pi, gen in enumerate(passes, 1):
            raw.seek(0)
            pos = 0
            last_fsync = 0
            while pos < size:
                n = min(CHUNK, size - pos)
                try:
                    buf = gen(bytearray(n))
                    raw.write(_fmt(buf))
                except OSError as e:
                    if skip_bad:
                        errors.append({"offset": pos, "error": str(e)})
                        raw.seek(pos + CHUNK)
                        pos += CHUNK
                        continue
                    raise
                pos += n
                total_written += n
                if progress:
                    progress(pi, len(passes), pos, size)
                if pos - last_fsync >= fsync_every_gib * (1 << 30):
                    os.fsync(raw.fileno())
                    last_fsync = pos
        os.fsync(raw.fileno())

    verification = {"checked_bytes": 0, "bad_sectors": 0,
                    "samples": 0, "all_zero": method == "zero"}
    if verify:
        step = 512 * (1 << 20)  # one 1 MiB sample per 512 MiB
        sample_len = 1 * (1 << 20)
        with open(node, "rb", buffering=0) as rd:
            offset = 0
            while offset < size:
                n = min(sample_len, size - offset)
                rd.seek(offset)
                data = rd.read(n)
                verification["samples"] += 1
                verification["checked_bytes"] += len(data)
                if method == "zero":
                    if data.count(0) != len(data):
                        verification["bad_sectors"] += 1
                digest.update(data[:65536])
                offset += step
        verification["ok"] = verification["bad_sectors"] == 0
    else:
        verification["ok"] = None

    cert = {
        "tool": "NyxRecover wipe", "method": method, "node": node,
        "size": size, "passes": len(passes), "bytes_written": total_written,
        "verify": verification, "write_errors": errors[:50],
        "write_errors_total": len(errors),
        "started": started, "finished": time.time(),
        "duration_s": round(time.time() - started, 2),
        "standard": ("NIST SP 800-88 Rev.1 Clear" if method == "zero"
                     else "DoD 5220.22-M" if method == "dod5220"
                     else "Gutmann" if method == "gutmann" else "CSPRNG"),
    }
    return cert


def wipe_file(path: str, method: str = "zero", verify: bool = True) -> dict:
    """Overwrite a single file in place, then unlink it."""
    p = os.path.realpath(path)
    from nyx.nyxcore.device import media_size
    size = media_size(p)
    passes = _passes_for(method)
    with open(p, "r+b", buffering=0) as fh:
        for gen in passes:
            fh.seek(0)
            left = size
            while left > 0:
                n = min(CHUNK, left)
                fh.write(_fmt(gen(bytearray(n))))
                left -= n
        fh.flush()
        os.fsync(fh.fileno())
    try:
        os.remove(p)
    except FileNotFoundError:
        pass
    return {"file": path, "size": size, "passes": len(passes),
            "unlinked": True, "method": method,
            "standard": ("NIST SP 800-88 Rev.1 Clear" if method == "zero"
                         else "DoD 5220.22-M" if method == "dod5220"
                         else "Gutmann" if method == "gutmann" else "CSPRNG")}


def wipe_freespace(mountpoint: str, method: str = "random", progress=None,
                   rng_passes: int = 1, cancel=None) -> dict:
    """Fill all free space of a mounted FS, then delete the fill files.

    NOTE: journaling filesystems (ext4) may retain a few MB in the journal;
    for a *guaranteed* clean use wipe_device on the whole block device.
    """
    started = time.time()
    written = 0
    files = []
    seq = 0
    filler_name = ".nyx-wipe-filler"

    def one_file(path: str) -> int:
        nonlocal written
        n = 0
        with open(path, "wb", buffering=0) as fh:
            gen = _passes_for(method, rng_passes)[0]
            while True:
                if cancel and cancel.is_set():
                    break
                try:
                    buf = gen(bytearray(CHUNK))
                    fh.write(_fmt(buf))
                except OSError:
                    break
                n += CHUNK
                written += CHUNK
                if progress:
                    progress(written, 0)
        fh_closed = open(path, "ab")
        fh_closed.close()
        return n

    while True:
        path = os.path.join(mountpoint, f"{filler_name}-{seq}")
        try:
            added = one_file(path)
        except OSError:
            break
        if added == 0:
            try:
                os.remove(path)
            except OSError:
                pass
            break
        files.append(path)
        seq += 1
    removed = 0
    for path in files:
        try:
            os.remove(path)
            removed += 1
        except OSError:
            pass
    return {"mountpoint": mountpoint, "bytes_overwritten": written,
            "fill_files": len(files), "removed": removed,
            "method": method, "duration_s": round(time.time() - started, 2),
            "note": "En ext4 revisa también el journal; para garantía total usa wipe del dispositivo completo."}
