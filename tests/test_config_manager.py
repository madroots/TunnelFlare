import json

import pytest

from tunnelflare_backend import config_manager
from tunnelflare_backend.config_manager import ConfigManager


def test_tunnels_persist_in_tunnelflare_home(tunnelflare_home):
    ConfigManager().add_tunnel("api", 3000, protocol="https", rewrite_host=True)

    saved = json.loads((tunnelflare_home / "config.json").read_text(encoding="utf-8"))
    assert saved == {"tunnels": [{"name": "api", "port": 3000, "protocol": "https", "rewrite_host": True}]}
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


def test_names_that_would_share_files_conflict():
    manager = ConfigManager()
    manager.add_tunnel("my api", 3000)

    # Same name, and names that map to the same files on a case-insensitive disk
    for clash in ("my api", "my_api", "My API", "MY:API"):
        assert manager.name_conflict(clash) == "my api"
    assert manager.name_conflict("my-api") is None
    assert manager.name_conflict("my api", ignore="my api") is None
    with pytest.raises(ValueError):
        manager.add_tunnel("My_Api", 4000)
    assert [t["name"] for t in manager.get_tunnels()] == ["my api"]


def test_editing_a_tunnel_keeps_its_place_and_rejects_clashes():
    manager = ConfigManager()
    for name, port in (("api", 3000), ("web", 8080), ("docs", 4000)):
        manager.add_tunnel(name, port)

    manager.update_tunnel("web", "frontend", 5173, protocol="https", rewrite_host=True)
    assert manager.get_tunnels()[1] == {"name": "frontend", "port": 5173, "protocol": "https", "rewrite_host": True}
    assert [t["name"] for t in ConfigManager().get_tunnels()] == ["api", "frontend", "docs"]

    with pytest.raises(ValueError):
        manager.update_tunnel("frontend", "API", 5173)
    assert manager.get_tunnel("frontend")["port"] == 5173


def test_settings_do_not_drop_tunnels_saved_elsewhere():
    settings = ConfigManager()
    ConfigManager().add_tunnel("api", 3000)  # another instance, e.g. the tunnel manager's

    settings.set("auto_update_check", False)

    reloaded = ConfigManager()
    assert reloaded.get("auto_update_check") is False
    assert [t["name"] for t in reloaded.get_tunnels()] == ["api"]
