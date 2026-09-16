"""Cipher/encryption detection — LUKS1/2, BitLocker, VeraCrypt, entropy map."""
from __future__ import annotations

import struct

from .scan import shannon


def detect(source_path: str) -> dict:
    """Inspect the first MiB of a device/image for known crypto headers."""
    out = {"encrypted": False, "kind": None, "details": {}, "entropy": None}
    with open(source_path, "rb", buffering=0) as fh:
        head = fh.read(1024 * 1024)
    if head[:6] == b"LUKS\xba\xbe" or head[:4] == b"LUKS":
        out["encrypted"] = True
        out["kind"] = "LUKS1/2"
        out["details"] = _luks(head)
        return out
    if head[3:11] == b"-FVE-FS-" or b"-FVE-FS-" in head[:64]:
        out["encrypted"] = True
        out["kind"] = "BitLocker"
        out["details"] = {"note": "Cabecera BitLocker detectada; usa dislocker para montar"}
        return out
    # VeraCrypt/TrueCrypt: no header; heuristic = entropy of first 64 KiB > 7.99
    ent = shannon(head[:65536])
    out["entropy"] = round(ent, 4)
    if ent > 7.997:
        out["encrypted"] = True
        out["kind"] = "probable VeraCrypt/TrueCrypt (heurística de entropía)"
    return out


def _luks(head: bytes) -> dict:
    d = {}
    ver = struct.unpack_from("<H", head, 6)[0]
    d["version"] = ver
    cipher = head[40:72].split(b"\x00")[0].decode("ascii", "replace")
    mode = head[72:104].split(b"\x00")[0].decode("ascii", "replace")
    hname = head[104:136].split(b"\x00")[0].decode("ascii", "replace")
    label = ""
    d.update(cipher=cipher, mode=mode, hash=hname)
    if ver == 2:
        payload = struct.unpack_from("<Q", head, 288)[0] if len(head) > 296 else 0
        d["data_offset"] = payload
        label = head[576:608].split(b"\x00")[0].decode("utf-8", "replace") if len(head) > 608 else ""
    else:
        payload = struct.unpack_from("<I", head, 184)[0]
        d["data_offset"] = payload
        d["key_slots"] = [
            {"i": i, "enabled": struct.unpack_from("<I", head, 112 + i * 48)[0] == 0xAC71F3}
            for i in range(8)]
    if label:
        d["label"] = label
    return d


def entropy_map(source_path: str, sample: int = 64 * 1024, step: int = 0,
                max_points: int = 512) -> list:
    """Downsampled entropy map for the whole medium (sparkline in UI)."""
    from nyx.nyxcore.device import media_size
    size = media_size(source_path)
    step = step or max(size // max_points, sample)
    pts = []
    with open(source_path, "rb", buffering=0) as fh:
        off = 0
        while off < size and len(pts) < max_points:
            fh.seek(off)
            b = fh.read(sample)
            if not b:
                break
            pts.append({"offset": off, "entropy": round(shannon(b), 3)})
            off += step
    return pts
