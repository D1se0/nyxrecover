"""Fixtures — build tiny real filesystems with mkfs and populate them."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

PROJECT = Path(__file__).resolve().parents[2]


def _mkfs_img(tmp_path: Path, kind: str, size_mb: int = 24) -> Path:
    # FAT32 requires >= ~33 MB of clusters to be chosen by mkfs.vfat
    size = 256 if kind == "vfat" else 24
    img = tmp_path / f"test_{kind}.img"
    with open(img, "wb") as fh:
        fh.truncate(size * 1024 * 1024)
    if kind == "ext4":
        cmd = ["mkfs.ext4", "-F", "-q", "-b", "1024", "-I", "256", str(img)]
    elif kind == "vfat":
        cmd = ["mkfs.vfat", "-F", "32", "-n", "NYXTEST", str(img)]
    elif kind == "ntfs":
        cmd = ["mkfs.ntfs", "--quiet", "--quick", "--force", "-L", "NYXNT", str(img)]
    else:
        raise ValueError(kind)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip(f"mkfs {kind} no disponible: {r.stderr}")
    return img


def _populate_mounted(img: Path, kind: str, tmp_path: Path) -> Path:
    """Mount loopback, write files incl. deletions, unmount. Needs root."""
    mnt = tmp_path / "mnt"
    mnt.mkdir()
    subprocess.run(["mount", "-o", "loop", str(img), str(mnt)], check=True)
    try:
        d = mnt / "documentos"
        d.mkdir()
        (d / "contrasenas.txt").write_text(
            "banco: usuario=MARIO clave=Sup3rS3cret\nwifi=CASA-NET pass=W1f1P4ss\n")
        (d / "informe.txt").write_text("Informe confidencial NYX " * 20)
        (mnt / "foto.jpg").write_bytes(
            b"\xff\xd8\xff\xe0" + os.urandom(2048) + b"\xff\xd9")
        (mnt / "base.sqlite").write_bytes(
            b"SQLite format 3\x00" + os.urandom(4096))
        (mnt / "doc.pdf").write_bytes(
            b"%PDF-1.7\n" + os.urandom(1500) + b"\n%%EOF\n")
        # files that will be deleted (recoverable evidence)
        (mnt / "secreto_borrado.txt").write_text(
            "ESTE-SECRETO-DEBE-SOBREVIVIR " * 30)
        (mnt / "borrado.jpg").write_bytes(
            b"\xff\xd8\xff\xe0" + os.urandom(4096) + b"\xff\xd9")
        (mnt / "borrado.sqlite").write_bytes(
            b"SQLite format 3\x00" + os.urandom(8192))
        if kind == "ext4":
            os.sync()
        subprocess.run(["sync"], check=False)
    finally:
        subprocess.run(["umount", str(mnt)], check=True)
    return mnt


@pytest.fixture(scope="session")
def ext4_img(tmp_path_factory):
    tp = tmp_path_factory.mktemp("ext4")
    img = _mkfs_img(tp, "ext4")
    if os.geteuid() == 0:
        try:
            _populate_mounted(img, "ext4", tp)
        except subprocess.CalledProcessError:
            pass
    return img


@pytest.fixture(scope="session")
def vfat_img(tmp_path_factory):
    tp = tmp_path_factory.mktemp("vfat")
    img = _mkfs_img(tp, "vfat")
    if os.geteuid() == 0:
        try:
            _populate_mounted(img, "vfat", tp)
        except subprocess.CalledProcessError:
            pass
    return img


@pytest.fixture(scope="session")
def ntfs_img(tmp_path_factory):
    tp = tmp_path_factory.mktemp("ntfs")
    img = _mkfs_img(tp, "ntfs")
    return img
