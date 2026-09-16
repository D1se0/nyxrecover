"""NTFS parser — MFT walking and deleted-file discovery (pure Python).

Reads $MFT, applies update-sequence fixups, walks FILE records and
attributes ($FILE_NAME, $DATA), and can extract resident and non-resident
streams. Deleted files are records with the in-use flag cleared.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

MFT_RECORD_SIZE = 1024


class NtfsError(Exception):
    pass


@dataclass
class NtfsFile:
    record: int
    name: str
    size: int
    is_dir: bool
    deleted: bool
    resident: bool
    path: str = ""
    mtime: str = ""


def parse_boot(fh) -> dict:
    fh.seek(0)
    bs = fh.read(512)
    if bs[3:11] != b"NTFS    ":
        raise NtfsError("No es NTFS (OEM no coincide)")
    bps = struct.unpack_from("<H", bs, 11)[0]
    spc = bs[13]
    total = struct.unpack_from("<Q", bs, 40)[0]
    mft_clus = struct.unpack_from("<Q", bs, 48)[0]
    mftmirr = struct.unpack_from("<Q", bs, 56)[0]
    def _signed(b: int) -> int:
        return b if b < 0x80 else b - 256
    raw = bs[64]
    mft_rec = 1 << (-_signed(raw)) if raw >= 0x80 else raw * spc
    raw_i = bs[68]
    idx_rec = 1 << (-_signed(raw_i)) if raw_i >= 0x80 else raw_i * spc
    serial = bs[72:80]
    return {"bytes_per_sector": bps, "sectors_per_cluster": spc,
            "cluster_size": bps * spc, "total_sectors": total,
            "mft_cluster": mft_clus, "mftmirr_cluster": mftmirr,
            "mft_record_size": mft_rec or MFT_RECORD_SIZE,
            "index_record_size": idx_rec or 4096,
            "serial": serial.hex(":"), "volume_size": total * bps * spc}


def _apply_fixups(rec: bytes) -> bytes:
    """Apply update sequence array so the last bytes of each sector are right."""
    if rec[:4] not in (b"FILE", b"INDX"):
        return rec
    usa_off, usa_cnt = struct.unpack_from("<HH", rec, 4)
    if usa_off < 32 or usa_cnt < 1:
        return rec
    check = rec[usa_off:usa_off + 2]
    buf = bytearray(rec)
    for i in range(1, usa_cnt):
        val = rec[usa_off + i * 2: usa_off + i * 2 + 2]
        pos = i * 512 - 2
        if pos + 2 <= len(buf):
            buf[pos:pos + 2] = val
    return bytes(buf)


def _iter_attributes(rec: bytes, first_off: int):
    off = first_off
    while off + 4 <= len(rec):
        atype = struct.unpack_from("<I", rec, off)[0]
        if atype == 0xFFFFFFFF or atype == 0:
            break
        alen = struct.unpack_from("<I", rec, off + 4)[0]
        if alen < 16 or off + alen > len(rec):
            break
        yield off, rec[off:off + alen]
        off += alen


def _parse_runs(buf: bytes):
    """Yield (vcn, lcn, len) triples from a non-resident run list."""
    i, lcn = 0, 0
    vcn = 0
    while i < len(buf):
        h = buf[i]
        if h == 0:
            break
        len_len = h & 0xF
        off_len = (h >> 4) & 0xF
        i += 1
        if len_len == 0 or i + len_len > len(buf):
            break
        length = int.from_bytes(buf[i:i + len_len], "little")
        i += len_len
        if off_len:
            if i + off_len > len(buf):
                break
            offset = int.from_bytes(buf[i:i + off_len], "little", signed=True)
            i += off_len
            lcn += offset
        yield vcn, lcn, length
        vcn += length


def _resident_value(attr: bytes) -> bytes | None:
    """Resident attribute payload, given the attribute slice."""
    if len(attr) < 24:
        return None
    vlen = struct.unpack_from("<I", attr, 16)[0]
    voff = struct.unpack_from("<H", attr, 20)[0]
    if voff >= len(attr):
        return None
    return attr[voff: voff + vlen]


def read_mft_record(fh, boot: dict, n: int) -> bytes:
    off = boot["mft_cluster"] * boot["cluster_size"] + n * boot["mft_record_size"]
    fh.seek(off)
    rec = fh.read(boot["mft_record_size"])
    if len(rec) < boot["mft_record_size"]:
        raise NtfsError(f"MFT #{n} ilegible")
    return _apply_fixups(rec)


def parse_record(rec: bytes) -> dict | None:
    """Parse a FILE record → {num, flags, name, size, runs, resident_data}."""
    if rec[:4] != b"FILE":
        return None
    attr_off = struct.unpack_from("<H", rec, 20)[0]
    flags = struct.unpack_from("<H", rec, 22)[0]
    recnum = struct.unpack_from("<I", rec, 44)[0]
    out = {"num": recnum, "in_use": bool(flags & 1), "is_dir": bool(flags & 2),
           "name": None, "size": 0, "runs": [], "resident": None,
           "non_resident": False, "parent_ref": None}
    for off, attr in _iter_attributes(rec, attr_off):
        atype = struct.unpack_from("<I", attr, 0)[0]
        non_res = attr[8] != 0
        if atype == 0x30 and out["name"] is None:  # $FILE_NAME
            val = _resident_value(attr)
            if val and len(val) > 66:
                nlen = val[64]
                ns = val[65]
                raw = val[66:66 + nlen * (2 if ns != 2 else 1)]
                name = raw.decode("latin-1", "replace") if ns == 2 \
                    else raw.decode("utf-16-le", "replace")
                out["name"] = name
                out["parent_ref"] = struct.unpack_from("<Q", val, 0)[0] & 0xFFFFFFFFFFFF
        elif atype == 0x80:  # $DATA
            if non_res:
                out["non_resident"] = True
                runs_off = struct.unpack_from("<H", attr, 32)[0]
                real = struct.unpack_from("<Q", attr, 48)[0]
                out["size"] = real
                out["runs"] = list(_parse_runs(attr[runs_off:]))
            else:
                val = _resident_value(attr)
                out["resident"] = val or b""
                out["size"] = len(val or b"")
    return out


def read_file_data(fh, boot: dict, rec: dict, max_bytes: int = 0) -> bytes:
    if rec["resident"] is not None:
        data = rec["resident"]
        return data[:max_bytes] if max_bytes else data
    cs = boot["cluster_size"]
    limit = rec["size"] if max_bytes <= 0 else min(rec["size"], max_bytes)
    out = bytearray()
    for _vcn, lcn, length in rec["runs"]:
        if lcn == 0:  # sparse
            out.extend(b"\x00" * length * cs)
            continue
        fh.seek(lcn * cs)
        out.extend(fh.read(length * cs))
        if len(out) >= limit:
            break
    return bytes(out[:limit])


def iter_mft(fh, boot: dict, max_records: int = 500000):
    """Yield parsed records for the whole $MFT (used and deleted)."""
    mft_off = boot["mft_cluster"] * boot["cluster_size"]
    rs = boot["mft_record_size"]
    fh.seek(0, 2)
    fsize = fh.tell()
    max_bytes = min(fsize - mft_off, max_records * rs)
    fh.seek(mft_off)
    n = 0
    while n * rs < max_bytes:
        rec = fh.read(rs)
        if len(rec) < rs:
            break
        parsed = parse_record(_apply_fixups(rec))
        if parsed and parsed["name"]:
            yield parsed
        n += 1


def walk_files(fh, boot: dict, max_records: int = 500000):
    for rec in iter_mft(fh, boot, max_records):
        if rec["num"] < 16:
            continue  # system metafiles
        yield NtfsFile(
            record=rec["num"], name=rec["name"], size=rec["size"],
            is_dir=rec["is_dir"], deleted=not rec["in_use"],
            resident=rec["resident"] is not None, path="/" + rec["name"])
