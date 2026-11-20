import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest


def wait_until(predicate, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


def test_start_reports_public_url_and_stop_terminates(manager, fake_cloudflared):
    tunnel_id = manager.start_tunnel("my api", 3000)

    assert wait_until(lambda: manager.get_public_url(tunnel_id))
    assert manager.get_public_url(tunnel_id) == "https://fake-tunnel-test.trycloudflare.com"
    [tunnel] = manager.get_active_tunnels()
    assert (tunnel["id"], tunnel["name"], tunnel["port"], tunnel["status"]) == ("my_api", "my api", "3000", "Running")

    assert manager.stop_tunnel(tunnel_id)
    assert not psutil.pid_exists(tunnel["pid"])
    assert manager.get_active_tunnels() == []


def test_api_host_in_cloudflared_errors_is_not_the_tunnel_url(manager, fake_cloudflared):
    fake_cloudflared(url_delay=60)
    tunnel_id = manager.start_tunnel("slow", 3000)
    log = manager.logs_dir / f"{tunnel_id}.log"

    assert wait_until(lambda: log.exists() and "api.trycloudflare.com" in log.read_text(encoding="utf-8"))
    assert manager.get_public_url(tunnel_id) is None
    assert manager.get_active_tunnels()[0]["status"] == "Initializing"


def test_startup_failure_raises_and_leaves_no_tunnel_behind(manager, fake_cloudflared):
    fake_cloudflared(mode="fail")

    with pytest.raises(RuntimeError, match="Firewall or Antivirus"):
        manager.start_tunnel("api", 3000)
    assert list(manager.tunnels_dir.iterdir()) == []
    assert manager.get_active_tunnels() == []


def test_reused_pid_is_never_reported_or_terminated(manager):
    bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        # The tunnel that wrote this PID file is gone and its PID now belongs to
        # an unrelated process, which started at a different time.
        record = f"{bystander.pid} {psutil.Process(bystander.pid).create_time() - 3600}"
        pid_file = manager.tunnels_dir / "ghost.pid"

        pid_file.write_text(record)
        assert manager.get_active_tunnels() == []

        pid_file.write_text(record)
        manager.stop_tunnel("ghost")
        assert bystander.poll() is None
    finally:
        bystander.kill()
        bystander.wait()


@pytest.mark.skipif(os.name != "posix", reason="only POSIX keeps exited children as zombies")
def test_exited_tunnel_process_is_not_reported_as_running(manager):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.5)"])
    (manager.tunnels_dir / "dead.pid").write_text(f"{child.pid} {psutil.Process(child.pid).create_time()}")

    assert wait_until(lambda: psutil.Process(child.pid).status() == psutil.STATUS_ZOMBIE)
    assert manager.get_active_tunnels() == []
    assert not (manager.tunnels_dir / "dead.pid").exists()


def test_stopped_tunnel_logs_are_found_by_name(manager, fake_cloudflared):
    tunnel_id = manager.start_tunnel("my api", 3000)
    assert wait_until(lambda: manager.get_public_url(tunnel_id))
    manager.stop_tunnel(tunnel_id)

    assert "fake-tunnel-test.trycloudflare.com" in manager.get_logs_by_name("my api")


def test_frozen_build_runs_refreshed_copy_of_bundled_cloudflared(manager, tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    name = "cloudflared.exe" if sys.platform == "win32" else "cloudflared"
    bundled = bundle / name
    bundled.write_bytes(b"release-1")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    path = Path(manager._get_cloudflared_path())
    assert path == manager.bin_dir / name
    assert path.read_bytes() == b"release-1"

    # The next app release ships a different binary of the same size.
    bundled.write_bytes(b"release-2")
    later = time.time() + 60
    os.utime(bundled, (later, later))
    assert Path(manager._get_cloudflared_path()).read_bytes() == b"release-2"
