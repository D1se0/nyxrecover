"""Filesystem layer — detect, parse and walk ext2/3/4, FAT12/16/32, NTFS."""
from __future__ import annotations

import struct

from . import ext, vfat, ntfs


class UnknownFilesystem(Exception):
    pass


def detect(fh) -> str:
    """Return 'ext' | 'fat' | 'ntfs' or raise UnknownFilesystem."""
    # ext magic lives at 0x438 (1080) on 1K-block filesystems, 1024 on >=2K
    for off in (1024, 1080):
        fh.seek(off)
        if fh.read(2) == b"\x53\xEF":
            return "ext"
    fh.seek(0)
    boot = fh.read(512)
    if len(boot) >= 87:
        if boot[3:11] == b"NTFS    ":
            return "ntfs"
        bps = struct.unpack_from("<H", boot, 11)[0]
        spc = boot[13]
        nfats = boot[16]
        if bps in (512, 1024, 2048, 4096) and spc in (1, 2, 4, 8, 16, 32, 64, 128) \
                and nfats in (1, 2, 4, 8) and boot[82:87] in (b"FAT32", b"FAT16", b"FAT12"):
            return "fat"
    raise UnknownFilesystem("Filesystem no reconocido")


def open_fs(fh) -> tuple:
    kind = detect(fh)
    if kind == "ext":
        sb = ext.parse_superblock(fh)
        return kind, sb, ext.read_group_descs(fh, sb)
    if kind == "fat":
        return kind, vfat.parse_bpb(fh), None
    if kind == "ntfs":
        return kind, ntfs.parse_boot(fh), None
    raise UnknownFilesystem(kind)


def fs_summary(fh) -> dict:
    kind, sb, gds = open_fs(fh)
    if kind == "ext":
        return {
            "kind": f"ext2/3/4 (rev {sb['rev']})", "label": sb["label"],
            "block_size": sb["block_size"], "blocks": sb["blocks"],
            "size": sb["blocks"] * sb["block_size"],
            "inodes": sb["inodes"], "inode_size": sb["inode_size"],
            "groups": len(gds),
            "features": {
                "extents": sb["has_extents"], "64bit": sb["has_64bit"],
                "flex_bg": sb["has_flex_bg"],
                "metadata_csum": sb["has_metadata_csum"],
                "inline_data": sb["has_inline_data"],
                "bigalloc": sb["has_bigalloc"]},
            "uuid": sb["uuid"], "state": sb["state"],
            "last_mounted": sb["last_mounted"],
        }
    if kind == "fat":
        return {
            "kind": f"FAT{sb['type']}", "label": sb["label"],
            "cluster_size": sb["cluster_size"], "clusters": sb["clusters"],
            "size": sb["total_sectors"] * sb["bytes_per_sector"],
            "oem": sb["oem"], "groups": 0, "features": {},
            "uuid": "", "state": "-", "last_mounted": "",
        }
    return {
        "kind": "NTFS", "label": "", "cluster_size": sb["cluster_size"],
        "size": sb["volume_size"], "serial": sb["serial"],
        "mft_record_size": sb["mft_record_size"], "groups": 0,
        "features": {}, "uuid": sb["serial"], "state": "-",
        "last_mounted": "",
    }
