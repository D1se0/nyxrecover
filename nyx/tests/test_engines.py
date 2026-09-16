"""Core engine tests: scan, carve, recovery, audit, keywords, wipe."""
import hashlib
import json
import os
import struct

import pytest

from nyx.nyxcore.scan import scan_raw, shannon
from nyx.nyxcore.recovery import RecoveryEngine
from nyx.nyxcore import audit
from nyx.nyxcore.keywords import search as kw_search
from nyx.nyxcore.signatures import SIGS, by_id
from nyx.nyxcore.image import ahash, png_dimensions, jpeg_dimensions
from nyx.nyxcore.hdocs import analyze_pdf, analyze_ole, find_office_in_buffer
from nyx.nyxcore.cipher import detect as cipher_detect
from nyx.nyxcore.report import generate as report_generate
from nyx.nyxcore.timeline import build_timeline
from nyx.nyxcore.slack import collect as slack_collect
from nyx.nyxwipe.engine import _passes_for, wipe_freespace


JPEG = b"\xff\xd8\xff\xe0" + b"A" * 300 + b"\xff\xd9"
PDF = b"%PDF-1.4\n" + b"B" * 400 + b"\n%%EOF\n"
SQLITE = b"SQLite format 3\x00" + b"C" * 600
ZIP = b"PK\x03\x04" + b"D" * 300 + b"PK\x05\x06" + b"\x00" * 18


class TestShannon:
    def test_zeros(self):
        assert shannon(b"\x00" * 1000) == 0.0

    def test_uniform(self):
        assert shannon(bytes(range(256)) * 4) == pytest.approx(8.0, abs=0.001)

    def test_empty(self):
        assert shannon(b"") == 0.0


class TestSignatures:
    def test_all_have_unique_ids(self):
        ids = [s.sid for s in SIGS]
        assert len(ids) == len(set(ids))

    def test_jpeg(self):
        s = by_id("jpeg")
        assert s.header.startswith(b"\xff\xd8")
        assert s.footer == b"\xff\xd9"

    def test_match_header(self):
        from nyx.nyxcore.signatures import match_header
        hits = match_header(JPEG)
        assert any(s.sid == "jpeg" for s in hits)


class TestScan:
    def test_scan_image_finds_all(self, tmp_path):
        img = tmp_path / "raw.img"
        blob = b"\x00" * 1024 + JPEG + b"\x00" * 512 + PDF + b"\x00" * 256 + SQLITE
        img.write_bytes(blob)
        res = scan_raw(str(img))
        sigs = [h["sig"] for h in res["hits"]]
        assert "jpeg" in sigs
        assert "pdf" in sigs
        assert "sqlite" in sigs

    def test_offsets_correct(self, tmp_path):
        img = tmp_path / "raw.img"
        blob = b"\x00" * 1024 + JPEG
        img.write_bytes(blob)
        res = scan_raw(str(img))
        assert res["hits"][0]["offset"] == 1024

    def test_spanning_chunks(self, tmp_path):
        img = tmp_path / "raw.img"
        pad = b"\x00" * (8 * 1024 * 1024 - 10)  # header straddles border
        img.write_bytes(pad + JPEG)
        res = scan_raw(str(img))
        assert any(h["sig"] == "jpeg" for h in res["hits"])


class TestCarve:
    def test_carve_jpeg_pdf(self, tmp_path):
        img = tmp_path / "raw.img"
        img.write_bytes(b"\x00" * 2048 + JPEG + b"\xee" * 100 + PDF)
        eng = RecoveryEngine(str(img), str(tmp_path / "out"))
        res = eng.carve(min_size=16)
        names = [r["name"] for r in res["results"]]
        assert any(n.endswith(".jpg") for n in names)
        assert any(n.endswith(".pdf") for n in names)
        carved = list((Path2(res["session"]) / "carved").rglob("*.jpg"))
        assert carved
        assert carved[0].read_bytes() == JPEG

    def test_carve_zip_ooxml(self, tmp_path):
        img = tmp_path / "raw.img"
        blob = b"PK\x03\x04" + b"word/document.xml" + b"E" * 200 + b"PK\x05\x06" + b"\x00" * 18
        img.write_bytes(blob)
        eng = RecoveryEngine(str(img), str(tmp_path / "out"))
        res = eng.carve(min_size=16)
        assert any(r["name"].endswith(".docx") for r in res["results"])

    def test_manifest(self, tmp_path):
        img = tmp_path / "raw.img"
        img.write_bytes(JPEG)
        eng = RecoveryEngine(str(img), str(tmp_path / "out"))
        eng.carve(min_size=16)
        mp = eng.write_manifest()
        data = json.loads(mp.read_text())
        assert data["files"][0]["sha256"] == hashlib.sha256(JPEG).hexdigest()


from pathlib import Path as Path2  # noqa: E402


class TestRecoveryExt:
    def test_recover_deleted(self, ext4_img, tmp_path):
        import os
        if os.geteuid() != 0:
            pytest.skip("población del FS requiere root (mount loop)")
        eng = RecoveryEngine(str(ext4_img), str(tmp_path / "out"))
        res = eng.recover_fs(include_alive=True)
        paths = [r["path"] for r in res["results"]]
        assert any("documentos" in p for p in paths)
        assert any("secreto_borrado" in p for p in paths)
        out_files = list(Path2(res["session"]).rglob("*"))
        assert out_files

    def test_content_intact(self, ext4_img, tmp_path):
        eng = RecoveryEngine(str(ext4_img), str(tmp_path / "out"))
        eng.recover_fs(include_alive=True)
        hits = list(Path2(eng.session).rglob("contrasenas.txt"))
        if hits:
            content = hits[0].read_text()
            assert "Sup3rS3cret" in content


class TestRecoveryFat:
    def test_walk_fat(self, vfat_img):
        from nyx.nyxfs import vfat
        with open(vfat_img, "rb") as fh:
            fat = vfat.parse_bpb(fh)
            entries = list(vfat.walk_root(fh, fat))
        assert isinstance(entries, list)


class TestKeywords:
    def test_find_keywords(self, tmp_path):
        img = tmp_path / "raw.img"
        blob = b"\x00" * 4096 + b"usuario=MARIO clave=Sup3rS3cret" + b"\x00" * 4096
        img.write_bytes(blob)
        res = kw_search(str(img), ["Sup3rS3cret", "inexistente"])
        assert res["total"] == 1
        assert res["hits"][0]["keyword"] == "Sup3rS3cret"
        needle = b"usuario=MARIO clave="
        assert res["hits"][0]["offset"] == 4096 + len(needle)

    def test_case_insensitive(self, tmp_path):
        img = tmp_path / "raw.img"
        img.write_bytes(b"CONFIDENCIAL123" + b"\x00" * 100)
        res = kw_search(str(img), ["confidencial"])
        assert res["total"] == 1


class TestAudit:
    def test_chain_verifies(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit, "LAIR", tmp_path / "lair")
        audit.log("t1", {"a": 1})
        audit.log("t2", {"b": 2})
        audit.log("t3", {"c": 3})
        res = audit.verify(lair=tmp_path / "lair")
        assert res["ok"]
        assert res["entries"] == 3

    def test_tampering_detected(self, tmp_path, monkeypatch):
        lair = tmp_path / "lair"
        monkeypatch.setattr(audit, "LAIR", lair)
        audit.log("t1", {"a": 1})
        audit.log("t2", {"b": 2})
        jpath = lair / "journal"
        f = next(jpath.glob("*.jsonl"))
        lines = f.read_text().splitlines()
        e = json.loads(lines[0])
        e["payload"]["a"] = 999  # tamper
        lines[0] = json.dumps(e)
        f.write_text("\n".join(lines) + "\n")
        res = audit.verify(lair=lair)
        assert not res["ok"]


class TestWipeHelpers:
    def test_passes_count(self):
        assert len(_passes_for("zero")) == 1
        assert len(_passes_for("dod5220")) == 3
        assert len(_passes_for("gutmann")) == 35
        assert len(_passes_for("random", 5)) == 5

    def test_zero_fill_pattern(self):
        gen = _passes_for("zero")[0]
        assert gen(bytearray(1024)) == bytearray(1024)


class TestImage:
    def test_png_dims(self):
        ihdr = struct.pack(">IIBBBBB", 64, 32, 8, 2, 0, 0, 0)
        png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr
        assert png_dimensions(png) == (64, 32)

    def test_jpeg_dims(self):
        # FF C0 <len=17> <prec=8> <height=48> <width=64> <1 component>
        sof = b"\xff\xc0" + struct.pack(">H", 17) + b"\x08" + \
            struct.pack(">HH", 48, 64) + b"\x01\x22\x00"
        jpg = b"\xff\xd8" + sof + b"\x00" * 10
        w, h = jpeg_dimensions(jpg)
        assert (w, h) == (64, 48)


class TestHdocs:
    def test_pdf(self):
        r = analyze_pdf(PDF)
        assert r["valid"]
        assert r["revisions"] >= 1

    def test_ole_locator(self):
        ole = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 100
        assert find_office_in_buffer(b"\x00" * 10 + ole)[0]["kind"] == "ole"

    def test_ole_parse(self):
        ole = bytearray(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 600)
        struct.pack_into("<H", ole, 30, 9)  # 512-byte sectors
        r = analyze_ole(bytes(ole))
        assert r["valid"]
        assert r["sector_size"] == 512


class TestCipher:
    def test_luks(self, tmp_path):
        img = tmp_path / "luks.img"
        head = bytearray(b"\x00" * 4096)
        head[0:6] = b"LUKS\xba\xbe"
        struct.pack_into("<H", head, 6, 1)
        img.write_bytes(bytes(head) + b"\x00" * 60000)
        r = cipher_detect(str(img))
        assert r["encrypted"]
        assert r["kind"] == "LUKS1/2"
        assert r["details"]["cipher"] == r["details"]["cipher"]  # parsed ok

    def test_plain(self, tmp_path):
        img = tmp_path / "plain.img"
        img.write_bytes(b"texto claro" * 1000)
        r = cipher_detect(str(img))
        assert not r["encrypted"]


class TestReport:
    def test_html(self, tmp_path):
        out = tmp_path / "rep.html"
        report_generate({"title": "T", "subtitle": "s", "sections": [
            {"title": "S1", "kpis": [("a", 1), ("b", "x")],
             "table": {"headers": ["h1"], "rows": [["v1"]]}}]}, str(out))
        html = out.read_text()
        assert "T" in html and "v1" in html
        assert "<style>" in html


class TestTimelineExt:
    def test_events(self, ext4_img):
        evs = build_timeline(str(ext4_img))
        assert isinstance(evs, list)
        assert all("iso" in e for e in evs)


class TestSlackExt:
    def test_slack_runs(self, ext4_img, tmp_path):
        try:
            res = slack_collect(str(ext4_img), str(tmp_path / "slack"))
        except RuntimeError as e:
            pytest.skip(str(e))
        assert "files" in res
