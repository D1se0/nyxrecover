"""Safety layer — locks, risk assessment and confirmations.

Nothing in NyxRecover touches a device without passing through here:
1. The device is resolved and classified (system / disk / removable).
2. An exclusive flock is taken to prevent concurrent writers.
3. Destructive operations must be re-confirmed with a typed phrase.
"""
from __future__ import annotations

import errno
import fcntl
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .device import Device, get_device, mounted_mountpoints

LOCK_DIR = Path.home() / ".nyxrecover" / "locks"


class SafetyError(RuntimeError):
    pass


@dataclass
class RiskReport:
    device: Device
    level: int
    label: str
    blockers: list
    warnings: list

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    @property
    def confirm_phrase(self) -> str:
        return f"ELIMINAR {Path(self.device.node).name.upper()}"


def assess(node: str, wipe: bool = False) -> RiskReport:
    dev = get_device(node)
    blockers, warnings = [], []
    mps = mounted_mountpoints(dev.node)
    for p in dev.partitions:
        mps.extend(mounted_mountpoints(p.node))
    mps = sorted(set(mps))
    if mps:
        (blockers if wipe else warnings).append("Desmonta " + ", ".join(mps))
    if dev.kind == "system":
        blockers.append("Es un dispositivo del sistema (raíz del SO)")
    if dev.ro:
        blockers.append("El kernel lo marca como solo-lectura")
    for p in dev.partitions:
        if p.fstype == "swap":
            (blockers if wipe else warnings).append(f"{p.node} es swap activo")
    warnings.append(f"Modelo: {dev.model or 'desconocido'} · Serie: {dev.serial or 'n/d'}")
    warnings.append(f"Tamaño: {dev.size_human} · Bus: {dev.bus}")
    return RiskReport(dev, dev.risk_level, dev.risk_label, blockers, warnings)


def require_phrase(report: RiskReport, typed: str) -> None:
    expected = report.confirm_phrase
    if typed.strip().upper() != expected:
        raise SafetyError(
            f"Confirmación incorrecta. Escribe exactamente: {expected}")


def umount_all(node: str) -> dict:
    base = Path(node).name
    targets = set(mounted_mountpoints(node))
    try:
        dev = get_device(node)
        for part in dev.partitions:
            targets.update(mounted_mountpoints(part.node))
    except FileNotFoundError:
        pass
    umounted, failed = [], []
    for mp in sorted(targets):
        r = subprocess.run(["umount", mp], capture_output=True, text=True)
        if r.returncode == 0:
            umounted.append(mp)
            continue
        r2 = subprocess.run(["umount", "-l", mp], capture_output=True, text=True)
        if r2.returncode == 0:
            umounted.append(mp)
        else:
            failed.append(f"{mp}: {(r2.stderr or r.stderr).strip()}")
    return {"umounted": umounted, "failed": failed}


class DeviceLock:
    """Exclusive advisory lock so two NyxRecover processes never fight."""

    def __init__(self, node: str):
        self.node = node
        self._fh = None

    def __enter__(self):
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        name = "lock-" + self.node.replace("/", "_")
        self._fh = open(LOCK_DIR / name, "w")
        try:
            fcntl.flock(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            self._fh.close()
            if e.errno in (errno.EACCES, errno.EAGAIN):
                raise SafetyError(f"Otro proceso ya está usando {self.node}")
            raise
        return self

    def __exit__(self, *exc):
        try:
            fcntl.flock(self._fh, fcntl.LOCK_UN)
        finally:
            self._fh.close()
        return False
