"""Safety layer + device module tests (root not required)."""
import os
import subprocess

import pytest

from nyx.nyxcore import safety
from nyx.nyxcore.device import human_size, get_device, list_devices


class TestHumanSize:
    def test_units(self):
        assert human_size(0) == "0 B"
        assert "KB" in human_size(1500)
        assert "MB" in human_size(5 * 1024 * 1024)
        assert "GB" in human_size(3 * 1024 ** 3)


class TestDevices:
    def test_list_devices(self):
        devs = list_devices()
        assert isinstance(devs, list)
        assert all(d.node.startswith("/dev/") for d in devs)

    def test_get_device_sdb(self):
        if not os.path.exists("/dev/sdb1"):
            pytest.skip("no /dev/sdb1")
        d = get_device("/dev/sdb1")
        assert d.size > 0
        assert d.partitions[0].node == "/dev/sdb1"

    def test_get_device_missing(self):
        with pytest.raises(FileNotFoundError):
            get_device("/dev/xyzdefinitivamente_no_existe")


class TestSafety:
    def test_assess_system_blocked_for_wipe(self):
        if not os.path.exists("/dev/sda"):
            pytest.skip("no /dev/sda")
        rep = safety.assess("/dev/sda", wipe=True)
        assert rep.blocked  # system device must be blocked
        assert rep.confirm_phrase.startswith("ELIMINAR ")

    def test_phrase_validation(self):
        class FakeRep:
            device = type("D", (), {"node": "/dev/sdb"})()
            @property
            def confirm_phrase(self):
                return "ELIMINAR SDB"
        safety.require_phrase(FakeRep(), "eliminar sdb")  # case-insensitive
        with pytest.raises(safety.SafetyError):
            safety.require_phrase(FakeRep(), "otra cosa")

    def test_lock_exclusive(self, tmp_path, monkeypatch):
        monkeypatch.setattr(safety, "LOCK_DIR", tmp_path / "locks")
        import threading
        node = "test-node"
        acquired = []
        def hold():
            with safety.DeviceLock(node):
                acquired.append(1)
                import time
                time.sleep(1.2)
        t = threading.Thread(target=hold)
        t.start()
        import time
        time.sleep(0.4)  # ensure the holder owns the flock
        with pytest.raises(safety.SafetyError):
            with safety.DeviceLock(node):
                pass
        t.join(timeout=10)
        assert acquired

    def test_umount_all_no_mounts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(safety, "LOCK_DIR", tmp_path / "locks")
        res = safety.umount_all("/dev/definitivamente_no_existe")
        assert res["umounted"] == []
