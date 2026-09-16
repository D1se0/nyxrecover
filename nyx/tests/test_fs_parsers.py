"""Filesystem parser tests on real mkfs-built images."""
import struct

import pytest

from nyx.nyxfs import ext, vfat, ntfs, UnknownFilesystem, detect, fs_summary


class TestExt:
    def test_superblock(self, ext4_img):
        with open(ext4_img, "rb") as fh:
            sb = ext.parse_superblock(fh)
        assert sb["block_size"] == 1024
        assert sb["inodes"] > 0
        assert sb["has_extents"] is True

    def test_group_descs(self, ext4_img):
        with open(ext4_img, "rb") as fh:
            sb = ext.parse_superblock(fh)
            gds = ext.read_group_descs(fh, sb)
        assert len(gds) >= 1
        assert gds[0]["inode_table"] > 0

    def test_walk_tree_finds_files(self, ext4_img):
        import os
        if os.geteuid() != 0:
            pytest.skip("población del FS requiere root (mount loop)")
        with open(ext4_img, "rb") as fh:
            sb = ext.parse_superblock(fh)
            gds = ext.read_group_descs(fh, sb)
            entries = list(ext.walk_tree(fh, sb, gds))
        paths = [e["path"] for e in entries]
        assert any("documentos" in p for p in paths)

    def test_read_inode_root(self, ext4_img):
        with open(ext4_img, "rb") as fh:
            sb = ext.parse_superblock(fh)
            gds = ext.read_group_descs(fh, sb)
            node = ext.read_inode(fh, sb, gds, 2)
        assert node.is_dir
        assert node.num == 2

    def test_wrong_magic_raises(self, tmp_path):
        img = tmp_path / "junk.img"
        img.write_bytes(b"\x00" * 4096)
        with open(img, "rb") as fh:
            with pytest.raises(ext.ExtError):
                ext.parse_superblock(fh)


class TestFat:
    def test_bpb(self, vfat_img):
        with open(vfat_img, "rb") as fh:
            fat = vfat.parse_bpb(fh)
        assert fat["type"] == 32
        assert fat["cluster_size"] >= 512
        assert fat["root_cluster"] >= 2

    def test_detect_fat(self, vfat_img):
        with open(vfat_img, "rb") as fh:
            assert detect(fh) == "fat"

    def test_chain_from(self, vfat_img):
        with open(vfat_img, "rb") as fh:
            fat = vfat.parse_bpb(fh)
            chain = vfat.chain_from(fh, fat, fat["root_cluster"])
        assert len(chain) >= 1


class TestNtfs:
    def test_boot(self, ntfs_img):
        with open(ntfs_img, "rb") as fh:
            boot = ntfs.parse_boot(fh)
        assert boot["bytes_per_sector"] == 512
        assert boot["cluster_size"] in (512, 1024, 2048, 4096)
        assert boot["mft_record_size"] in (1024,)

    def test_detect_ntfs(self, ntfs_img):
        with open(ntfs_img, "rb") as fh:
            assert detect(fh) == "ntfs"

    def test_iter_mft(self, ntfs_img):
        with open(ntfs_img, "rb") as fh:
            boot = ntfs.parse_boot(fh)
            recs = list(ntfs.iter_mft(fh, boot, max_records=64))
        assert any(r["name"] == "$MFT" for r in recs)


class TestDetect:
    def test_unknown(self, tmp_path):
        img = tmp_path / "x.img"
        img.write_bytes(b"\xee" * 8192)
        with open(img, "rb") as fh:
            with pytest.raises(UnknownFilesystem):
                detect(fh)

    def test_fs_summary_ext(self, ext4_img):
        with open(ext4_img, "rb") as fh:
            s = fs_summary(fh)
        assert "ext" in s["kind"]
