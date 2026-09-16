"""Device enumeration and identification.

Every operation in NyxRecover resolves a device through this module, which
attaches a classification (removable / system / disk / partition) used by the
safety layer to compute risk levels before touching a single byte.
"""
from __future__ import annotations

import json
import os
import re
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

IS_WINDOWS = os.name == "nt"

if not IS_WINDOWS:
    import fcntl
    BLKGETSIZE64 = 0x80081272
else:
    import ctypes
    from ctypes import wintypes
    fcntl = None
    BLKGETSIZE64 = 0x80081272
    IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C
    GENERIC_READ = 0x80000000
    OPEN_EXISTING = 3
    FILE_SHARE_READ_WRITE = 1 | 2

SYSBLOCK = Path("/sys/block")
_UDEV_PROPS = (
    "DEVNAME", "ID_MODEL", "ID_VENDOR", "ID_SERIAL", "ID_SERIAL_SHORT",
    "ID_BUS", "ID_TYPE", "ID_FS_TYPE", "ID_FS_UUID", "ID_FS_LABEL",
    "ID_USB_DRIVER", "ID_SCSI", "ID_WWN", "ID_PART_TABLE_TYPE",
)


@dataclass
class Partition:
    name: str
    node: str
    size: int
    fstype: str = ""
    label: str = ""
    uuid: str = ""
    mountpoint: str = ""
    readonly: bool = False


@dataclass
class Device:
    name: str
    node: str
    size: int
    model: str = ""
    vendor: str = ""
    serial: str = ""
    bus: str = ""
    fstype: str = ""
    uuid: str = ""
    label: str = ""
    wwn: str = ""
    table_type: str = ""
    removable: bool = False
    ro: bool = False
    partitions: list = field(default_factory=list)
    mounts: list = field(default_factory=list)

    @property
    def size_human(self) -> str:
        return human_size(self.size)

    @property
    def kind(self) -> str:
        """removable | system | disk — coarse classification for the UI."""
        if self.node in system_roots():
            return "system"
        if self.removable:
            return "removable"
        return "disk"

    @property
    def risk_level(self) -> int:
        return {"system": 3, "disk": 2, "removable": 1}[self.kind]

    @property
    def risk_label(self) -> str:
        return {3: "CRÍTICO — dispositivo del sistema", 2: "ALTO — disco interno",
                1: "MEDIO — extraíble"}[self.risk_level]


def human_size(n: int) -> str:
    x = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if x < 1024 or unit == "TB":
            return f"{x:,.1f} {unit}" if unit != "B" else f"{int(x)} B"
        x /= 1024
    return f"{x:,.1f} TB"


def _win_device_size(path: str) -> int | None:
    """Size of \\\\.\\PhysicalDriveN or \\\\.\\X: via Win32 API."""
    if not re.match(r"^\\\\\\.\\(PHYSICALDRIVE\d+|[A-Za-z]:)$", path, re.I):
        return None
    try:
        h = ctypes.windll.kernel32.CreateFileW(path, GENERIC_READ,
                                               FILE_SHARE_READ_WRITE, None,
                                               OPEN_EXISTING, 0, None)
        if h == -1 or h == 0xFFFFFFFFFFFFFFFF:
            return None
        try:
            buf = ctypes.create_string_buffer(8)
            got = wintypes.DWORD()
            ok = ctypes.windll.kernel32.DeviceIoControl(
                h, IOCTL_DISK_GET_LENGTH_INFO, None, 0, buf, 8,
                ctypes.byref(got), None)
            return struct.unpack("q", buf.raw)[0] if ok else None
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:
        return None


def media_size(path: str) -> int:
    """True size of a file OR block/volume device (st_size is 0 for devs)."""
    import stat as statmod
    if IS_WINDOWS:
        w = _win_device_size(path)
        if w is not None:
            return w
        return os.stat(path).st_size
    st = os.stat(path)
    if statmod.S_ISBLK(st.st_mode):
        with open(path, "rb", buffering=0) as fh:
            return struct.unpack("Q", fcntl.ioctl(
                fh.fileno(), BLKGETSIZE64, b"\x00" * 8))[0]
    return st.st_size


def _read(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def system_roots() -> set:
    roots = set()
    if IS_WINDOWS:
        roots.add("\\\\.\\PHYSICALDRIVE0")
        sysdrv = os.environ.get("SystemDrive", "C:").rstrip("\\")
        roots.add(f"\\\\.\\{sysdrv}")
        return roots
    try:
        out = subprocess.run(["findmnt", "-rn", "-o", "SOURCE,TARGET", "/"],
                             capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            src = line.split()[0] if line.split() else ""
            m = re.match(r"^/dev/(sd[a-z]|nvme\d+n\d+p)\d+$", src)
            if m:
                roots.add(re.sub(r"\d+$", "", src))
                roots.add(src)
    except Exception:
        pass
    roots.add("/dev/sda")  # root disk of the VM image convention
    return roots


def _win_disks() -> list:
    """Best-effort Windows disk enumeration via PowerShell/CIM."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_DiskDrive | Select-Object DeviceID,Size,"
             "Model,InterfaceType,SerialNumber,MediaType | ConvertTo-Json"],
            capture_output=True, text=True, timeout=30)
        data = json.loads(out.stdout or "null")
        if isinstance(data, dict):
            data = [data]
        return data or []
    except Exception:
        return []


def _lsblk() -> list:
    if IS_WINDOWS:
        return _win_disks()
    try:
        out = subprocess.run(
            ["lsblk", "-Jb", "-o",
             "NAME,PATH,SIZE,TYPE,MODEL,VENDOR,SERIAL,RO,RM,FSTYPE,UUID,LABEL,"
             "MOUNTPOINTS,WWN,PTTYPE"],
            capture_output=True, text=True, timeout=15)
        data = json.loads(out.stdout or "{}")
        return data.get("blockdevices", [])
    except Exception:
        return []


def list_devices() -> list:
    """All physical/loop devices with their partitions."""
    devices = []
    for dev in _lsblk():
        if IS_WINDOWS:
            d = Device(
                name=str(dev.get("DeviceID") or "").replace("\\\\.\\", ""),
                node=str(dev.get("DeviceID") or ""),
                size=int(dev.get("Size") or 0),
                model=(str(dev.get("Model") or "").strip()),
                bus=str(dev.get("InterfaceType") or "unknown").lower(),
                serial=(str(dev.get("SerialNumber") or "").strip()),
            )
            d.index = dev.get("Index")
            devices.append(d)
            continue
        if dev.get("type") != "disk":
            continue
        name = dev.get("name", "")
        node = dev.get("path", f"/dev/{name}")
        d = Device(
            name=name,
            node=node,
            size=int(dev.get("size") or 0),
            model=(dev.get("model") or "").strip(),
            vendor=(dev.get("vendor") or "").strip(),
            serial=(dev.get("serial") or "").strip(),
            bus=_bus_of(name),
            fstype=dev.get("fstype") or "",
            uuid=dev.get("uuid") or "",
            label=dev.get("label") or "",
            wwn=dev.get("wwn") or "",
            table_type=dev.get("pttype") or "",
            removable=bool(int(dev.get("rm") or 0)),
            ro=bool(int(dev.get("ro") or 0)),
        )
        for part in dev.get("children") or []:
            if part.get("type") != "part":
                continue
            mps = [m for m in (part.get("mountpoints") or []) if m]
            d.partitions.append(Partition(
                name=part.get("name", ""),
                node=part.get("path", f"/dev/{part.get('name')}"),
                size=int(part.get("size") or 0),
                fstype=part.get("fstype") or "",
                label=part.get("label") or "",
                uuid=part.get("uuid") or "",
                mountpoint=mps[0] if mps else "",
                readonly=bool(int(part.get("ro") or 0)),
            ))
        devices.append(d)
    return devices


def get_device(node_or_name: str) -> Device:
    # ficheros regulares (imágenes .img/.dd/.raw) primero, con su ruta tal cual
    if node_or_name and not node_or_name.startswith("/dev/") \
            and os.path.isfile(node_or_name):
        return Device(name=Path(node_or_name).name, node=node_or_name,
                      size=media_size(node_or_name))
    node = node_or_name if node_or_name.startswith("/dev/") else f"/dev/{node_or_name}"
    for d in list_devices():
        if d.node == node or d.name == Path(node).name:
            return d
        if any(p.node == node for p in d.partitions):
            d.partitions = [p for p in d.partitions if p.node == node]
            return d
    if Path(node).exists():
        st_size = os.stat(node).st_size
        return Device(name=Path(node).name, node=node, size=st_size)
    raise FileNotFoundError(f"Dispositivo no encontrado: {node}")


def mounted_mountpoints(node: str) -> list:
    """All active mountpoints for a node (device or partition)."""
    base = Path(node).name
    # /dev/sdb -> also match /dev/sdb1...
    prefix = base if base[-1].isdigit() is False else base
    out = set()
    try:
        with open("/proc/mounts") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 2:
                    continue
                src, mp = parts[0], parts[1]
                if Path(src).name == base or Path(src).name.startswith(prefix):
                    out.add(mp)
    except OSError:
        pass
    return sorted(out)


def hwinfo(node: str) -> dict:
    """Extended SMART-ish info without external deps: kernel + sysfs + hdparm."""
    info = {"node": node, "smart": {}, "geometry": {}, "trim": None}
    base = SYSBLOCK / Path(node).name
    if not base.exists():
        return info
    info["geometry"] = {
        "sectors": _read(base / "size"),
        "sector_size": _read(base / "queue" / "hw_sector_size") or "512",
        "logical_block": _read(base / "queue" / "logical_block_size") or "512",
        "physical_block": _read(base / "queue" / "physical_block_size") or "512",
        "rotational": _read(base / "queue" / "rotational"),
        "scheduler": _read(base / "queue" / "scheduler"),
        "max_sectors_kb": _read(base / "queue" / "max_sectors_kb"),
    }
    try:
        out = subprocess.run(["hdparm", "-I", node], capture_output=True,
                             text=True, timeout=20).stdout
        for key, pat in {
            "model": r"Model Number:\s*(.+)",
            "serial": r"Serial Number:\s*(.+)",
            "firmware": r"Firmware Revision:\s*(.+)",
            "transport": r"Transport:\s*(.+)",
            "sata_version": r"SATA Version is:\s*(.+)",
        }.items():
            m = re.search(pat, out)
            if m:
                info["smart"][key] = m.group(1).strip()
    except Exception:
        pass
    try:
        out = subprocess.run(["hdparm", "-W", node], capture_output=True,
                             text=True, timeout=15).stdout
        m = re.search(r"write-caching\s*=\s*(\d)", out)
        if m:
            info["smart"]["write_cache"] = bool(int(m.group(1)))
    except Exception:
        pass
    return info


def _bus_of(name: str) -> str:
    p = SYSBLOCK / name
    try:
        real = p.resolve()
        for part in real.parts:
            if part.startswith(("usb", "ata", "scsi", "nvme", "virtio", "mmc")):
                return part.split(":")[0]
    except OSError:
        pass
    return "unknown"
