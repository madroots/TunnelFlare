import json

import pytest

from tunnelflare_backend import config_manager
from tunnelflare_backend.config_manager import ConfigManager


def test_tunnels_persist_in_tunnelflare_home(tunnelflare_home):
    ConfigManager().add_tunnel("api", 3000)

    saved = json.loads((tunnelflare_home / "config.json").read_text(encoding="utf-8"))
    assert saved == {"tunnels": [{"name": "api", "port": 3000, "protocol": "http"}]}
    assert [t["name"] for t in ConfigManager().get_tunnels()] == ["api"]


def test_failed_save_keeps_previous_config(monkeypatch):
    manager = ConfigManager()
    manager.add_tunnel("api", 3000)

    real_dump = config_manager.json.dump

    def dump_then_crash(obj, fp, **kwargs):
        fp.write('{"tunnels": [')  # half-written file, then the disk fills up
        raise OSError("No space left on device")

    monkeypatch.setattr(config_manager.json, "dump", dump_then_crash)
    with pytest.raises(OSError):
        manager.add_tunnel("web", 8080)
    monkeypatch.setattr(config_manager.json, "dump", real_dump)

    assert [t["name"] for t in ConfigManager().get_tunnels()] == ["api"]
