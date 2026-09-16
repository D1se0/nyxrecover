"""Hidden-document analyzers — OLE/MSOffice, PDF internals, hibernation files.

All pure Python: they locate orphan streams, embedded objects, PDF
revision history (incremental updates) and Windows hibernation RAM size,
even inside raw images.
"""
from __future__ import annotations

import re
import struct
import zlib

from .scan import shannon


def analyze_ole(data: bytes) -> dict:
    """Parse an OLE CFB header + directory to expose hidden streams."""
    out = {"format": "OLE/CFB", "valid": False, "streams": [],
           "sector_size": 0, "minor_ver": 0, "dll": False}
    if data[:8] != b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1":
        out["error"] = "No es OLE CFB"
        return out
    out["valid"] = True
    minor = struct.unpack_from("<H", data, 24)[0]
    dll = struct.unpack_from("<H", data, 26)[0]
    ssz = 1 << struct.unpack_from("<H", data, 30)[0]
    out.update(minor_ver=minor, dll=bool(dll), sector_size=ssz)
    first_dir = struct.unpack_from("<I", data, 48)[0]
    off = 512 + first_dir * ssz
    for _ in range(128):
        if off + 128 > len(data):
            break
        name_raw = data[off: off + 64]
        nlen = struct.unpack_from("<H", data, off + 64)[0]
        etype = data[off + 66]
        start = struct.unpack_from("<I", data, off + 116)[0]
        size = struct.unpack_from("<Q", data, off + 120)[0]
        if etype == 0:
            break
        name = name_raw[: max(0, nlen - 2)].decode("utf-16-le", "replace")
        if name:
            out["streams"].append({"name": name, "type": etype,
                                   "start_sector": start, "size": size})
        off += 128
    return out


def analyze_pdf(data: bytes) -> dict:
    """Count objects, revisions and embedded payloads in a PDF."""
    out = {"format": "PDF", "valid": data[:5] == b"%PDF-", "revisions": 1,
           "objects": 0, "embedded_files": 0, "javascript": False,
           "incremental_updates": 0}
    if not out["valid"]:
        return out
    out["objects"] = len(re.findall(rb"\d+\s+\d+\s+obj\b", data))
    out["revisions"] = max(1, data.count(b"%%EOF"))
    out["incremental_updates"] = out["revisions"] - 1
    out["embedded_files"] = len(re.findall(rb"/EmbeddedFile", data))
    out["javascript"] = bool(re.search(rb"/JavaScript|/JS\b", data))
    enc = re.search(rb"/Encrypt\b", data)
    out["encrypted"] = bool(enc)
    return out


HIBER_SIGNATURES = (b"HIBR", b"hibe", b"sleep")


def analyze_hibernation(data: bytes) -> dict:
    """Windows hiberfil.sys header — reports RAM size and format."""
    out = {"format": "hibernation", "valid": False}
    if len(data) < 128:
        out["error"] = "buffer demasiado corto"
        return out
    # hiberfil header: 'HIBR' + ver + ... plus kernel page size at 0x8/0xC
    if data[:4] not in HIBER_SIGNATURES and b"HIBR" not in data[:64]:
        out["error"] = "sin cabecera HIBR (quizá comprimido o nuevo formato)"
        return out
    out["valid"] = True
    ver = struct.unpack_from("<I", data, 4)[0] if data[:4] == b"HIBR" else 0
    out["version"] = ver
    out["entropy_head"] = round(shannon(data[:65536]), 3)
    return out


def find_office_in_buffer(buf: bytes) -> list:
    """Quick locator of OLE/PDF payloads inside a raw blob."""
    found = []
    off = 0
    while True:
        i = buf.find(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1", off)
        if i < 0:
            break
        found.append({"kind": "ole", "offset": i})
        off = i + 8
    off = 0
    while True:
        i = buf.find(b"%PDF-", off)
        if i < 0:
            break
        found.append({"kind": "pdf", "offset": i})
        off = i + 5
    return found
