"""File-signature database used by the recovery carver.

Each signature has a stable id, human name, category, magic header (hex),
optional footer and a maximum plausible size used to sanity-check carved
candidates. The ids are referenced by recovery results and reports.
"""
from __future__ import annotations

import binascii
import re
from dataclasses import dataclass

def H(s: str) -> bytes:
    return binascii.unhexlify(s.replace(" ", ""))

@dataclass(frozen=True)
class Sig:
    sid: str
    name: str
    ext: str
    cat: str
    header: bytes
    footer: bytes = b""
    max_size: int = 64 * 1024 * 1024
    min_size: int = 16

SIGS = [
    # ── Images ────────────────────────────────────────────────────────────
    Sig("jpeg", "Imagen JPEG", "jpg", "image", H("FFD8FF"),
        footer=H("FFD9"), max_size=80 * 1024 * 1024),
    Sig("png", "Imagen PNG", "png", "image", H("89504E470D0A1A0A"),
        footer=H("49454E44AE426082"), max_size=200 * 1024 * 1024),
    Sig("gif", "Imagen GIF", "gif", "image", H("474946383761"), max_size=20 * 1024 * 1024),
    Sig("gif89a", "Imagen GIF", "gif", "image", H("474946383961"), max_size=20 * 1024 * 8612),
    Sig("bmp", "Imagen BMP", "bmp", "image", H("424D"), max_size=100 * 1024 * 1024),
    Sig("webp", "Imagen WebP", "webp", "image", H("52494646"), max_size=60 * 1024 * 1024),
    Sig("tiff", "Imagen TIFF", "tif", "image", H("49492A00"), max_size=200 * 1024 * 1024),
    Sig("ico", "Icono ICO", "ico", "image", H("00000100"), max_size=1 * 1024 * 1024),

    # ── Documents ─────────────────────────────────────────────────────────
    Sig("pdf", "Documento PDF", "pdf", "doc", H("255044462D"),
        footer=H("0A2525454F46"), max_size=500 * 1024 * 1024, min_size=100),
    Sig("zip", "Archivo ZIP", "zip", "archive", H("504B0304"),
        footer=H("504B0506"), max_size=2 * 1024 * 1024 * 1024, min_size=22),
    Sig("zip_eof", "Archivo ZIP", "zip", "archive", H("504B0304"),
        footer=H("504B0506"), max_size=2 * 1024 * 1024 * 1024, min_size=22),
    Sig("rar", "Archivo RAR", "rar", "archive", H("526172211A0700"), max_size=2 * 1024 * 1024 * 1024),
    Sig("7z", "Archivo 7-Zip", "7z", "archive", H("377ABCAF271C"), max_size=2 * 1024 * 1024 * 1024),
    Sig("gzip", "Archivo GZip", "gz", "archive", H("1F8B08"), max_size=2 * 1024 * 1024 * 1024),
    Sig("xz", "Archivo XZ", "xz", "archive", H("FD377A585A00"), max_size=2 * 1024 * 1024 * 1024),
    Sig("bzip2", "Archivo BZip2", "bz2", "archive", H("425A68"), max_size=2 * 1024 * 1024 * 1024),

    # ── Office ────────────────────────────────────────────────────────────
    Sig("ole", "Doc Office (OLE)", "doc", "doc", H("D0CF11E0A1B11AE1"), max_size=512 * 1024 * 1024),
    Sig("docx", "Office Open XML", "docx", "doc", H("504B0304"), max_size=100 * 1024 * 1024),

    # ── Video / Audio ─────────────────────────────────────────────────────
    Sig("mp4", "Vídeo MP4", "mp4", "video", H("0000001866747970"), max_size=8 * 1024 * 1024 * 1024),
    Sig("avi", "Vídeo AVI", "avi", "video", H("52494646"), max_size=8 * 1024 * 1024 * 1024),
    Sig("mkv", "Vídeo Matroska", "mkv", "video", H("1A45DFA3"), max_size=8 * 1024 * 1024 * 1024),
    Sig("mpeg_ps", "Vídeo MPEG-PS", "mpg", "video", H("000001BA"), max_size=8 * 1024 * 1024 * 1024),
    Sig("mp3_id3", "Audio MP3 (ID3)", "mp3", "audio", H("494433"), max_size=80 * 1024 * 1024),
    Sig("mp3_raw", "Audio MP3 (frame)", "mp3", "audio", H("FFFB"), max_size=80 * 1024 * 1024),
    Sig("wav", "Audio WAV", "wav", "audio", H("52494646"), max_size=2 * 1024 * 1024 * 1024),
    Sig("flac", "Audio FLAC", "flac", "audio", H("664C61430000"), max_size=500 * 1024 * 1024),
    Sig("ogg", "Audio OGG", "ogg", "audio", H("4F6767530002"), max_size=500 * 1024 * 1024),

    # ── Disk / forensics containers ───────────────────────────────────────
    Sig("mbr", "Sector arranque MBR", "mbr", "disk", H("55AA") , max_size=512, min_size=512),
    Sig("ext_sb", "Superbloque ext2/3/4", "img", "disk", H("53EF"), max_size=4096, min_size=1080),
    Sig("lvm2", "Cabecera LVM2", "img", "disk", H("4C41424C4F4E4530"), max_size=4096),
    Sig("iso", "Imagen ISO-9660", "iso", "disk", H("4344303031"), max_size=17 * 1024 * 1024 * 1024),

    # ── Databases / email ─────────────────────────────────────────────────
    Sig("sqlite", "Base SQLite 3", "sqlite", "db", H("53514C69746520666F726D6174203300"), max_size=64 * 1024 * 1024 * 1024),
    Sig("pst", "Correo Outlook PST", "pst", "email", H("2142444E"), max_size=64 * 1024 * 1024 * 1024),
    Sig("dbf", "dBase DBF", "dbf", "db", H("03"), max_size=2 * 1024 * 1024 * 1024, min_size=65),

    # ── Executables / scripts ─────────────────────────────────────────────
    Sig("elf", "Binario ELF", "elf", "exe", H("7F454C46"), max_size=1 * 1024 * 1024 * 1024),
    Sig("pe", "Ejecutable Windows", "exe", "exe", H("4D5A"), max_size=1 * 1024 * 1024 * 1024),
    Sig("macho", "Binario Mach-O", "bin", "exe", H("CFFAEDFE"), max_size=512 * 1024 * 1024),
    Sig("macho64", "Binario Mach-O 64", "bin", "exe", H("CFFAEDFE"), max_size=512 * 1024 * 1024),

    # ── Crypto containers ─────────────────────────────────────────────────
    Sig("luks", "Cabecera LUKS", "img", "crypto", H("4C554B53BEBA"), max_size=8192),
    Sig("keystore", "Java Keystore", "jks", "crypto", H("FEEDFEED"), max_size=64 * 1024 * 1024),
    Sig("pgp_skey", "Clave PGP secreta", "key", "crypto", H("8C"), max_size=65536, min_size=64),

    # ── Misc ──────────────────────────────────────────────────────────────
    Sig("rtf", "Documento RTF", "rtf", "doc", H("7B5C727466"), max_size=100 * 1024 * 1024),
    Sig("lnk", "Acceso directo .lnk", "lnk", "misc", H("4C00000001140200"), max_size=4096),
    Sig("regf", "Colmena Registro Win", "dat", "misc", H("72656766"), max_size=2 * 1024 * 1024 * 1024),
]

_BY_ID = {s.sid: s for s in SIGS}

# "PK\x03\x04 + xx + word/" → docx/xlsx/pptx sub-detection
_OOXML_RE = re.compile(rb"word/|xl/|ppt/")


def by_id(sid: str) -> Sig:
    return _BY_ID.get(sid)


def all_sigs() -> list:
    return SIGS


def match_header(buf: bytes, offset: int = 0) -> list:
    """Return sigs whose header matches at buf[offset:]."""
    out = []
    for s in SIGS:
        if buf[offset:offset + len(s.header)] == s.header:
            out.append(s)
    return out


def refine_ooxml(buf: bytes) -> str:
    """For ZIP sigs decide docx/xlsx/pptx by scanning the first entries."""
    if _OOXML_RE.search(buf[:4096]):
        seg = buf[:4096]
        if b"word/" in seg:
            return "docx"
        if b"xl/" in seg:
            return "xlsx"
        if b"ppt/" in seg:
            return "pptx"
    return "zip"
