"""Slack-space extraction — the data that hides after the file's EOF.

ext: for every alive regular inode, the last cluster may contain bytes
beyond i_size (up to block_size-1). FAT: last cluster of the chain may
hold up to cluster_size-1 bytes past file size. This module dumps those
tails for manual inspection — deleted fragments often survive here.
"""
from __future__ import annotations

from pathlib import Path


def slack_ext(fh, sb, gds, inode) -> bytes:
    from nyx.nyxfs.ext import read_file_data
    bs = sb["block_size"]
    if not inode.blocks or inode.size % bs == 0:
        return b""
    data = read_file_data(fh, sb, inode, max_bytes=inode.size + bs)
    return data[inode.size:]


def collect(source: str, outdir: str, progress=None, min_slack: int = 8,
            max_files: int = 200000) -> dict:
    import hashlib
    import time
    from nyx.nyxfs import ext as extmod, vfat as fatmod
    from nyx.nyxfs import detect
    started = time.time()
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    count = 0
    with open(source, "rb", buffering=0) as fh:
        kind = detect(fh)
        fh.seek(0)
        if kind == "ext":
            sb = extmod.parse_superblock(fh)
            gds = extmod.read_group_descs(fh, sb)
            for e in extmod.walk_tree(fh, sb, gds, max_entries=max_files):
                if e["kind"] != "file" or e["deleted"]:
                    continue
                try:
                    node = extmod.read_inode(fh, sb, gds, e["inode"])
                except extmod.ExtError:
                    continue
                tail = slack_ext(fh, sb, gds, node)
                if len(tail) >= min_slack and any(tail):
                    count += 1
                    dest = out / f"slack_ino{node.num:08d}.bin"
                    dest.write_bytes(tail)
                    results.append({"path": e["path"], "inode": node.num,
                                    "slack_bytes": len(tail),
                                    "nonzero": sum(1 for b in tail if b),
                                    "sha256": hashlib.sha256(tail).hexdigest()})
        elif kind == "fat":
            fat = fatmod.parse_bpb(fh)
            for e in fatmod.walk_root(fh, fat):
                if e.is_dir or e.deleted or e.size == 0:
                    continue
                cs = fat["cluster_size"]
                if e.size % cs == 0:
                    continue
                chain = fatmod.chain_from(fh, fat, e.cluster)
                if len(chain) * cs < ((e.size // cs) + 1) * cs:
                    continue
                data = fatmod.read_file(fh, fat, e)
                fh.seek(0, 2)
                tail = data[e.size:]
                if len(tail) >= min_slack and any(tail):
                    count += 1
                    dest = out / f"slack_fat{e.inode:08d}.bin"
                    dest.write_bytes(tail)
                    results.append({"path": e.path, "cluster": e.inode,
                                    "slack_bytes": len(tail),
                                    "nonzero": sum(1 for b in tail if b),
                                    "sha256": hashlib.sha256(tail).hexdigest()})
        else:
            raise RuntimeError("Slack: filesystem no soportado (usa ext/FAT)")
    return {"source": source, "out": str(out), "files": count,
            "results": results[:1000],
            "duration_s": round(time.time() - started, 2)}
