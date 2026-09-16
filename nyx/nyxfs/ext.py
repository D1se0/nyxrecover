"""ext2/3/4 parser — directory walking and inode recovery (pure Python).

Reads only from a device/image file handle; never writes. Understands:
superblock, group descriptors (32/64-bit), inode tables, extent trees
(ext4), classic block pointers with single/double/triple indirection,
directory entries with checksum tails, and deleted-inode detection via
dtime/link count.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

EXT2_S_MAGIC = 0xEF53
SUPERBLOCK_OFF = 1024

# incompat feature flags
F_EXTENTS = 0x40
F_64BIT = 0x80
F_META_BG = 0x10
F_FLEX_BG = 0x200
F_INLINE_DATA = 0x8000
# ro_compat
F_HUGE_FILE = 0x8
F_BIGALLOC = 0x200
F_METADATA_CSUM = 0x400


@dataclass
class ExtInode:
    num: int
    mode: int
    uid: int
    size_low: int
    atime: int
    ctime: int
    mtime: int
    dtime: int
    links: int
    blocks: list = field(default_factory=list)
    size_high: int = 0
    flags: int = 0

    @property
    def size(self) -> int:
        if (self.mode & 0xF000) == 0x8000:
            return (self.size_high << 32) | self.size_low
        return self.size_low

    @property
    def deleted(self) -> bool:
        return self.dtime > 0 or self.links == 0

    @property
    def is_dir(self) -> bool:
        return (self.mode & 0xF000) == 0x4000

    @property
    def is_regular(self) -> bool:
        return (self.mode & 0xF000) == 0x8000

    @property
    def is_symlink(self) -> bool:
        return (self.mode & 0xF000) == 0xA000

    @property
    def perm(self) -> str:
        return oct(self.mode & 0o777)


class ExtError(Exception):
    pass


def _safe_read(fh, off: int, n: int) -> bytes:
    fh.seek(off)
    data = fh.read(n)
    if len(data) != n:
        raise ExtError(f"Lectura corta en offset {off}: {len(data)}/{n}")
    return data


def parse_superblock(fh) -> dict:
    sb = _safe_read(fh, SUPERBLOCK_OFF, 1024)
    if struct.unpack_from("<H", sb, 56)[0] != EXT2_S_MAGIC:
        raise ExtError("No es un filesystem ext2/3/4 (magic 0xEF53 no encontrado)")
    inodes_count = struct.unpack_from("<I", sb, 0)[0]
    blocks_count = struct.unpack_from("<I", sb, 4)[0]
    log_bs = struct.unpack_from("<I", sb, 24)[0]
    bs = 1024 << log_bs
    blocks_per_group = struct.unpack_from("<I", sb, 32)[0]
    inodes_per_group = struct.unpack_from("<I", sb, 40)[0]
    rev = struct.unpack_from("<I", sb, 76)[0]
    first_ino = struct.unpack_from("<I", sb, 84)[0] if rev >= 1 else 11
    inode_size = struct.unpack_from("<H", sb, 88)[0] if rev >= 1 else 128
    incompat = struct.unpack_from("<I", sb, 96)[0] if rev >= 1 else 0
    ro_compat = struct.unpack_from("<I", sb, 100)[0] if rev >= 1 else 0
    desc_size = 32
    if incompat & F_64BIT:
        desc_size = struct.unpack_from("<H", sb, 254)[0] or 64
    vol_name = sb[120:136].split(b"\x00")[0].decode("utf-8", "replace")
    last_mount = sb[156:188].split(b"\x00")[0].decode("utf-8", "replace")
    mnt_count = struct.unpack_from("<H", sb, 84 - 8)[0] if rev >= 1 else 0
    uuid = sb[104:120].hex(":")
    state = struct.unpack_from("<H", sb, 58)[0]
    return {
        "inodes": inodes_count, "blocks": blocks_count, "block_size": bs,
        "blocks_per_group": blocks_per_group,
        "inodes_per_group": inodes_per_group, "rev": rev,
        "first_inode": first_ino, "inode_size": inode_size,
        "desc_size": desc_size, "incompat": incompat,
        "ro_compat": ro_compat, "label": vol_name,
        "last_mounted": last_mount, "mount_count": mnt_count,
        "uuid": uuid, "state": "limpio" if state == 1 else "con errores",
        "has_extents": bool(incompat & F_EXTENTS),
        "has_64bit": bool(incompat & F_64BIT),
        "has_meta_bg": bool(incompat & F_META_BG),
        "has_flex_bg": bool(incompat & F_FLEX_BG),
        "has_inline_data": bool(incompat & F_INLINE_DATA),
        "has_bigalloc": bool(ro_compat & F_BIGALLOC),
        "has_metadata_csum": bool(ro_compat & F_METADATA_CSUM),
        "has_huge_file": bool(ro_compat & F_HUGE_FILE),
    }


def _first_data_block(sb) -> int:
    return 1 if sb["block_size"] == 1024 else 0


def _group_count(sb) -> int:
    bpg = sb["blocks_per_group"] or 8 * sb["block_size"]
    fdb = _first_data_block(sb)
    return (sb["blocks"] - fdb + bpg - 1) // bpg


def read_group_descs(fh, sb) -> list:
    """GDT: block 2 on 1K filesystems, block 1 otherwise."""
    bs = sb["block_size"]
    gd_off = 2 * 1024 if bs == 1024 else bs
    ds = sb["desc_size"]
    ngroups = _group_count(sb)
    raw = _safe_read(fh, gd_off, ds * ngroups)
    descs = []
    for g in range(ngroups):
        d = raw[g * ds:(g + 1) * ds]
        block_bitmap = struct.unpack_from("<I", d, 0)[0]
        inode_table_lo = struct.unpack_from("<I", d, 8)[0]
        inode_table_hi = struct.unpack_from("<I", d, 40)[0] if ds >= 64 else 0
        free_blocks = struct.unpack_from("<H", d, 12)[0] if ds >= 64 else \
            struct.unpack_from("<H", d, 12)[0]
        descs.append({
            "group": g,
            "block_bitmap": block_bitmap,
            "inode_table": (inode_table_hi << 32) | inode_table_lo,
            "free_blocks": free_blocks,
        })
    return descs


def read_inode(fh, sb, gds, ino: int) -> ExtInode:
    if ino < 1 or ino > sb["inodes"]:
        raise ExtError(f"Inode {ino} fuera de rango (1..{sb['inodes']})")
    per_group = sb["inodes_per_group"]
    group = (ino - 1) // per_group
    index = (ino - 1) % per_group
    if group >= len(gds):
        raise ExtError(f"Grupo {group} inexistente")
    table_block = gds[group]["inode_table"]
    offset = table_block * sb["block_size"] + index * sb["inode_size"]
    raw = _safe_read(fh, offset, sb["inode_size"])
    (mode, uid, size_low, atime, ctime, mtime, dtime,
     gid, links, _blocks_lo) = struct.unpack_from("<HHIIIIIHHI", raw)
    node = ExtInode(num=ino, mode=mode, uid=uid, size_low=size_low,
                    atime=atime, ctime=ctime, mtime=mtime, dtime=dtime,
                    links=links)
    node.flags = struct.unpack_from("<I", raw, 32)[0]
    if (mode & 0xF000) == 0x8000 and sb["ro_compat"] & F_HUGE_FILE:
        node.size_high = struct.unpack_from("<I", raw, 108)[0]
    if node.flags & 0x80000:  # EXT4_EXTENTS_FL
        node.blocks = _parse_extent_tree(fh, sb, raw)
    else:
        node.blocks = _parse_block_pointers(fh, sb, raw)
    return node


def _parse_block_pointers(fh, sb, raw: bytes) -> list:
    """12 direct + single/double/triple indirect chains."""
    bs = sb["block_size"]
    ppg = bs // 4
    limit = sb["blocks"]
    direct = list(struct.unpack_from("<12I", raw, 40))
    ind1, ind2, ind3 = struct.unpack_from("<3I", raw, 88)
    blocks = [p for p in direct if 0 < p < limit]

    seen = set()

    def read_ptr_block(blk: int) -> list:
        if blk <= 0 or blk >= limit or blk in seen:
            return []
        seen.add(blk)
        data = _safe_read(fh, blk * bs, bs)
        return list(struct.unpack(f"<{ppg}I", data))

    def gather(ptr: int, level: int) -> list:
        if ptr <= 0 or ptr >= limit:
            return []
        if level == 0:
            return [ptr]
        out = []
        for p in read_ptr_block(ptr):
            out.extend(gather(p, level - 1))
        return out

    blocks.extend(gather(ind1, 1))
    blocks.extend(gather(ind2, 2))
    blocks.extend(gather(ind3, 3))
    return blocks


def _parse_extent_tree(fh, sb, inode_raw: bytes) -> list:
    """Walk an ext4 extent tree and return absolute block numbers."""
    blocks = []
    bs = sb["block_size"]

    def parse_node(buf: bytes, depth: int):
        if len(buf) < 12:
            return
        eh_magic, entries, _max_e, eh_depth, _gen = struct.unpack_from("<HHHHI", buf, 0)
        if eh_magic != 0xF30A:
            return
        for i in range(entries):
            off = 12 + i * 12
            if off + 12 > len(buf):
                break
            ee_block, packed, ee_start_lo = struct.unpack_from("<III", buf, off)
            ee_len = packed & 0x7FFF
            ee_start_hi = (packed >> 16) & 0xFFFF
            ee_start = (ee_start_hi << 32) | ee_start_lo
            if depth == eh_depth:
                if ee_start and ee_len:
                    blocks.extend(range(ee_start, ee_start + ee_len))
            elif ee_start:
                leaf = _safe_read(fh, ee_start * bs, bs)
                parse_node(leaf, depth + 1)

    parse_node(inode_raw[40:100], 0)
    return blocks


def read_file_data(fh, sb, inode: ExtInode, max_bytes: int = 0) -> bytes:
    bs = sb["block_size"]
    limit = inode.size if max_bytes <= 0 else min(inode.size, max_bytes)
    out = bytearray()
    for blk in inode.blocks:
        if len(out) >= limit:
            break
        fh.seek(blk * bs)
        out.extend(fh.read(bs))
    return bytes(out[:limit])


FTYPE_MAP = {0: "unknown", 1: "file", 2: "dir", 3: "chrdev", 4: "blkdev",
             5: "fifo", 6: "socket", 7: "symlink"}


def iter_dir_entries(fh, sb, inode: ExtInode):
    """Yield (inode, name, filetype, offset) for every dirent."""
    data = read_file_data(fh, sb, inode, max_bytes=64 * 1024 * 1024)
    off = 0
    while off + 8 <= len(data):
        ino, rec_len, name_len, ftype = struct.unpack_from("<IHBB", data, off)
        if rec_len < 8 or off + rec_len > len(data):
            break
        name = data[off + 8: off + 8 + name_len]
        if ino and name_len:
            yield ino, name.decode("utf-8", "surrogateescape"), \
                FTYPE_MAP.get(ftype, "unknown"), off
        off += rec_len


def walk_tree(fh, sb, gds, root_ino: int = 2, max_entries: int = 200000):
    """Full tree walk yielding every directory entry (alive or deleted)."""
    seen = set()
    count = 0

    def walk(ino: int, prefix: str, depth: int):
        nonlocal count
        if ino in seen or depth > 12 or count >= max_entries:
            return
        seen.add(ino)
        try:
            node = read_inode(fh, sb, gds, ino)
        except ExtError:
            return
        if not node.is_dir:
            return
        for child_ino, name, ftype, _off in iter_dir_entries(fh, sb, node):
            if name in (".", ".."):
                continue
            count += 1
            if count >= max_entries:
                return
            path = f"{prefix}/{name}"
            try:
                cnode = read_inode(fh, sb, gds, child_ino)
                deleted = cnode.dtime > 0 or cnode.links == 0
                kind = ("dir" if cnode.is_dir else
                        "file" if cnode.is_regular else
                        "symlink" if cnode.is_symlink else ftype)
            except ExtError:
                deleted, kind = True, ftype
            yield {"inode": child_ino, "name": name, "path": path,
                   "deleted": deleted, "kind": kind}
            if kind == "dir" and not deleted:
                yield from walk(child_ino, path, depth + 1)

    yield from walk(root_ino, "", 0)
