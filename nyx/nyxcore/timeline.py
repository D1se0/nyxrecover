"""Forensic timeline — chronological events from filesystem metadata."""
from __future__ import annotations

import csv
import datetime
from pathlib import Path


def _fmt(ts: int) -> str:
    try:
        return datetime.datetime.fromtimestamp(
            ts, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return ""


def build_timeline(source: str, include_alive: bool = True,
                   max_events: int = 200000) -> list:
    from nyx.nyxfs import ext as extmod, vfat as fatmod, ntfs as ntfsmod
    from nyx.nyxfs import detect
    events = []
    with open(source, "rb", buffering=0) as fh:
        kind = detect(fh)
        fh.seek(0)
        if kind == "ext":
            sb = extmod.parse_superblock(fh)
            gds = extmod.read_group_descs(fh, sb)
            for e in extmod.walk_tree(fh, sb, gds, max_entries=max_events):
                if e["kind"] == "dir" and not e["deleted"]:
                    continue
                try:
                    node = extmod.read_inode(fh, sb, gds, e["inode"])
                except extmod.ExtError:
                    continue
                path = e["path"]
                base = [
                    (node.mtime, "M", "modificado"),
                    (node.atime, "A", "accedido"),
                ]
                if e["deleted"]:
                    base.append((node.dtime, "D", "BORRADO"))
                else:
                    base.append((node.ctime, "C", "creado/cambio"))
                for ts, typ, label in base:
                    if ts <= 0:
                        continue
                    events.append({"time": ts, "iso": _fmt(ts), "type": typ,
                                   "label": label, "path": path,
                                   "size": node.size,
                                   "deleted": e["deleted"]})
        elif kind == "fat":
            fat = fatmod.parse_bpb(fh)
            for e in fatmod.walk_root(fh, fat):
                ts = None
                if e.mtime:
                    try:
                        ts = int(datetime.datetime.strptime(
                            e.mtime[:19], "%Y-%m-%d %H:%M:%S").timestamp())
                    except ValueError:
                        ts = None
                if ts:
                    events.append({"time": ts, "iso": _fmt(ts),
                                   "type": "M", "label": "modificado",
                                   "path": e.path, "size": e.size,
                                   "deleted": e.deleted})
        elif kind == "ntfs":
            boot = ntfsmod.parse_boot(fh)
            for f in ntfsmod.walk_files(fh, boot):
                events.append({"time": 0, "iso": f.mtime, "type": "M",
                               "label": "MFT", "path": f.path,
                               "size": f.size, "deleted": f.deleted})
    events.sort(key=lambda x: x["time"] if x["time"] else 0)
    return events[:max_events]


def to_csv(events: list, out_path: str) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["iso", "epoch", "tipo", "accion", "path", "bytes", "borrado"])
        for e in events:
            w.writerow([e["iso"], e["time"], e["type"], e["label"],
                        e["path"], e["size"], e["deleted"]])
    return p
