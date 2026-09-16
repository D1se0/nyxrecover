"""FAT12/16/32 parser — directory walk, LFN and deleted-entry recovery.

Deleted FAT entries lose their first name character (0xE5) but keep the
start cluster and size, so files are recoverable assuming contiguous
allocation — exactly what PhotoRec-era tools do for short chains.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

FAT12, FAT16, FAT32 = 12, 16, 32
ATTR_LFN = 0x0F
ENTRY_END = 0x00
ENTRY_DELETED = 0xE5


@dataclass
class FatEntry:
    name: str
    short_name: str
    inode: int          # start cluster (kept for API symmetry)
    size: int
    is_dir: bool
    deleted: bool
    cluster: int
    path: str = ""
    attr: int = 0


class FatError(Exception):
    pass


def parse_bpb(fh) -> dict:
    fh.seek(0)
    bs = fh.read(512)
    if len(bs) < 512:
        raise FatError("Sector de arranque ilegible")
    bps = struct.unpack_from("<H", bs, 11)[0]
    spc = bs[13]
    reserved = struct.unpack_from("<H", bs, 14)[0]
    nfats = bs[16]
    root_entries = struct.unpack_from("<H", bs, 17)[0]
    tot16 = struct.unpack_from("<H", bs, 19)[0]
    fatsz16 = struct.unpack_from("<H", bs, 22)[0]
    tot32 = struct.unpack_from("<I", bs, 32)[0]
    fatsz32 = struct.unpack_from("<I", bs, 36)[0]
    root_cluster = struct.unpack_from("<I", bs, 44)[0]
    total = tot16 or tot32
    fatsz = fatsz16 or fatsz32
    if bps == 0 or spc == 0 or fatsz == 0 or nfats == 0:
        raise FatError("BPB inválido (no parece FAT)")
    root_dir_sectors = ((root_entries * 32) + (bps - 1)) // bps
    first_data_sector = reserved + (nfats * fatsz) + root_dir_sectors
    data_sectors = total - first_data_sector
    clusters = data_sectors // spc
    fstype = FAT32 if clusters >= 65525 else (FAT16 if clusters >= 4085 else FAT12)
    label = bs[71:82].decode("ascii", "replace").strip() if fstype == FAT32 \
        else bs[43:54].decode("ascii", "replace").strip()
    oem = bs[3:11]
    return {
        "bytes_per_sector": bps, "sectors_per_cluster": spc,
        "cluster_size": bps * spc, "reserved": reserved, "nfats": nfats,
        "root_entries": root_entries, "fat_size": fatsz,
        "total_sectors": total, "root_cluster": root_cluster,
        "first_data_sector": first_data_sector, "clusters": clusters,
        "type": fstype, "label": label, "oem": oem.decode("ascii", "replace"),
        "fsinfo": struct.unpack_from("<H", bs, 48)[0] if fstype == FAT32 else 0,
        "backup_boot": struct.unpack_from("<H", bs, 50)[0] if fstype == FAT32 else 0,
    }


def cluster_offset(fat: dict, cluster: int) -> int:
    return ((cluster - 2) * fat["cluster_size"]) + \
        fat["first_data_sector"] * fat["bytes_per_sector"]


def read_fat_entry(fh, fat: dict, cluster: int) -> int:
    t = fat["type"]
    fat_off = fat["reserved"] * fat["bytes_per_sector"]
    if t == FAT32:
        fh.seek(fat_off + cluster * 4)
        return struct.unpack("<I", fh.read(4))[0] & 0x0FFFFFFF
    if t == FAT16:
        fh.seek(fat_off + cluster * 2)
        return struct.unpack("<H", fh.read(2))[0]
    # FAT12
    fat_off += (cluster // 2) * 3 // 2
    fh.seek(fat_off)
    v = struct.unpack("<H", fh.read(2))[0]
    return (v >> 4) if cluster & 1 else (v & 0xFFF)


def chain_from(fh, fat: dict, start: int, max_len: int = 4_000_000) -> list:
    """Follow the FAT chain from start (best-effort, loop-safe)."""
    out, seen = [], set()
    c = start
    eoc = {0xFF8, 0xFFF8}
    while 2 <= c < fat["clusters"] + 2 and c not in seen and len(out) < max_len:
        seen.add(c)
        out.append(c)
        c = read_fat_entry(fh, fat, c)
        if c >= min(eoc):
            break
    return out


def _lfn_merge(lfn_parts: list, short: str) -> str:
    if not lfn_parts:
        return short
    raw = b"".join(reversed(lfn_parts))
    name = raw.split(b"\x00\x00")[0].decode("utf-16-le", "replace")
    return name or short


def parse_dir_entry(raw: bytes) -> dict | None:
    if len(raw) < 32:
        return None
    first = raw[0]
    if first == ENTRY_END:
        return {"end": True}
    attr = raw[11]
    if attr == ATTR_LFN:
        seq = first & 0x3F
        part = raw[1:11] + raw[14:26] + raw[28:32]
        return {"lfn": part, "seq": seq, "last": bool(first & 0x40)}
    if first == 0x05:  # KANJI lead byte escaped
        raw = b"\xE5" + raw[1:]
        first = 0xE5
    ntres = raw[13]
    def decode_name(b: bytes) -> str:
        s = b.decode("ascii", "replace")
        if ntres & 0x08:  # lowercase base
            s = s[:8].lower() + s[8:]
        if ntres & 0x10:
            s = s[:8].lower() + s[8:].lower()
        return s
    base = decode_name(raw[0:8]).rstrip()
    ext = raw[8:11].decode("ascii", "replace").rstrip()
    short = f"{base}.{ext}" if ext else base
    clus = struct.unpack_from("<H", raw, 26)[0]
    clus_hi = struct.unpack_from("<H", raw, 20)[0]
    size = struct.unpack_from("<I", raw, 28)[0]
    wtime = struct.unpack_from("<H", raw, 22)[0]
    wdate = struct.unpack_from("<H", raw, 24)[0]
    import datetime
    try:
        mtime = datetime.datetime(
            1980 + (wdate >> 9), (wdate >> 5) & 0xF, wdate & 0x1F,
            wtime >> 11, (wtime >> 5) & 0x3F, (wtime & 0x1F) * 2).isoformat(sep=" ")
    except ValueError:
        mtime = ""
    return {
        "deleted": first == ENTRY_DELETED,
        "short": ("?" if first == ENTRY_DELETED else "") + short,
        "attr": attr, "is_dir": bool(attr & 0x10),
        "cluster": (clus_hi << 16) | clus, "size": size, "mtime": mtime,
    }


def _iter_cluster_data(fh, fat: dict, clusters: list) -> bytes:
    out = bytearray()
    for c in clusters:
        fh.seek(cluster_offset(fat, c))
        out.extend(fh.read(fat["cluster_size"]))
    return bytes(out)


def read_chain(fh, fat: dict, start: int, size: int) -> bytes:
    clusters = chain_from(fh, fat, start)
    data = _iter_cluster_data(fh, fat, clusters)
    return data[:size] if size else data


def walk_root(fh, fat: dict, max_entries: int = 200000):
    """Yield FatEntry for every root-level entry (incl. deleted)."""
    if fat["type"] == FAT32:
        clusters = chain_from(fh, fat, fat["root_cluster"])
        data = _iter_cluster_data(fh, fat, clusters)
    else:
        root_off = fat["reserved"] * fat["bytes_per_sector"] + \
            fat["nfats"] * fat["fat_size"] * fat["bytes_per_sector"]
        fh.seek(root_off)
        data = fh.read(fat["root_entries"] * 32)
    yield from _parse_dir_chain(fh, fat, data, "", max_entries)


def _parse_dir_chain(fh, fat: dict, data: bytes, prefix: str,
                     max_entries: int):
    count = 0
    lfn_parts = []
    i = 0
    while i + 32 <= len(data) and count < max_entries:
        ent = parse_dir_entry(data[i:i + 32])
        i += 32
        if ent is None:
            continue
        if ent.get("end"):
            # keep scanning: deleted files may live after gaps in fat32 dirs
            if fat["type"] != FAT32:
                break
            continue
        if "lfn" in ent:
            lfn_parts.append(ent["lfn"])
            continue
        lfn_parts_current = lfn_parts
        lfn_parts = []
        short = ent["short"]
        name = _lfn_merge(lfn_parts_current, short) or short
        deleted = ent.get("deleted", False)
        entry = FatEntry(
            name=name, short_name=short, inode=ent["cluster"],
            size=ent["size"], is_dir=ent["is_dir"], deleted=deleted,
            cluster=ent["cluster"], path=f"{prefix}/{name}",
            attr=ent.get("attr", 0))
        entry.mtime = ent.get("mtime", "")
        count += 1
        yield entry


def read_file(fh, fat: dict, entry: FatEntry) -> bytes:
    return read_chain(fh, fat, entry.cluster, entry.size)


def read_dir_raw(fh, fat: dict, entry: FatEntry) -> bytes:
    return read_chain(fh, fat, entry.cluster, 0)
