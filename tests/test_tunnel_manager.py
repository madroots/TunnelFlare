import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

from tunnelflare_backend.tunnel_manager import DEBUG_LOG_KEEP, TunnelManager


def wait_until(predicate, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


def status_of(manager, name):
    return next((t["status"] for t in manager.get_active_tunnels() if t["name"] == name), None)


def test_start_reports_public_url_and_stop_terminates(manager, fake_cloudflared):
    tunnel_id = manager.start_tunnel("my api", 3000)

    assert wait_until(lambda: status_of(manager, "my api") == "Running")
    assert manager.get_public_url(tunnel_id) == "https://fake-tunnel-test.trycloudflare.com"
    [tunnel] = manager.get_active_tunnels()
    assert (tunnel["id"], tunnel["name"], tunnel["port"]) == ("my_api", "my api", "3000")

    assert manager.stop_tunnel(tunnel_id)
    assert not psutil.pid_exists(tunnel["pid"])
    assert manager.get_active_tunnels() == []


def test_api_host_in_cloudflared_errors_is_not_the_tunnel_url(manager, fake_cloudflared):
    fake_cloudflared(url_delay=60)
    tunnel_id = manager.start_tunnel("slow", 3000)
    log = manager.logs_dir / f"{tunnel_id}.log"

    assert wait_until(lambda: log.exists() and "api.trycloudflare.com" in log.read_text(encoding="utf-8"))
    assert manager.get_public_url(tunnel_id) is None
    assert status_of(manager, "slow") == "Initializing"


def test_dropped_edge_connection_is_reported_as_reconnecting(manager, fake_cloudflared):
    fake_cloudflared(mode="drop")
    manager.start_tunnel("flaky", 3000)

    assert wait_until(lambda: status_of(manager, "flaky") == "Reconnecting")


def test_https_origin_and_host_rewrite_reach_cloudflared(manager, fake_cloudflared):
    tunnel_id = manager.start_tunnel("secure", 8443, protocol="https", rewrite_host=True)
    log = manager.logs_dir / f"{tunnel_id}.log"

    assert wait_until(lambda: log.exists() and "Arguments:" in log.read_text(encoding="utf-8"))
    arguments = next(line for line in log.read_text(encoding="utf-8").splitlines() if "Arguments:" in line)
    assert "--url https://" in arguments and ":8443" in arguments
    assert "--http-host-header localhost:8443" in arguments
    assert "--no-tls-verify" in arguments


def test_each_start_begins_with_a_fresh_log(manager, fake_cloudflared):
    tunnel_id = manager.start_tunnel("api", 3000)
    log = manager.logs_dir / f"{tunnel_id}.log"
    assert wait_until(lambda: status_of(manager, "api") == "Running")
    with open(log, "a", encoding="utf-8") as stale:
        stale.write("INF |  https://stale-run.trycloudflare.com  |\n")
    assert manager.get_public_url(tunnel_id) == "https://stale-run.trycloudflare.com"
    manager.stop_tunnel(tunnel_id)

    tunnel_id = manager.start_tunnel("api", 3000)
    assert wait_until(lambda: status_of(manager, "api") == "Running")
    assert manager.get_public_url(tunnel_id) == "https://fake-tunnel-test.trycloudflare.com"
    assert "stale-run" not in log.read_text(encoding="utf-8")


def test_startup_failure_raises_and_leaves_no_tunnel_behind(manager, fake_cloudflared):
    fake_cloudflared(mode="fail")

    with pytest.raises(RuntimeError, match="Firewall or Antivirus"):
        manager.start_tunnel("api", 3000)
    assert list(manager.tunnels_dir.iterdir()) == []
    assert manager.get_active_tunnels() == []


def test_port_check_sees_listening_servers(listening_port):
    assert TunnelManager.is_port_listening(listening_port)

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    assert not TunnelManager.is_port_listening(free_port)


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


def test_debug_log_is_capped(tunnelflare_home):
    tunnelflare_home.mkdir(parents=True)
    lines = [f"[2026-01-01 00:00:00] old diagnostic line {number:07d}\n" for number in range(40_000)]
    (tunnelflare_home / "debug.log").write_text("".join(lines), encoding="utf-8")

    TunnelManager()

    kept = (tunnelflare_home / "debug.log").read_text(encoding="utf-8")
    assert len(kept.encode()) < DEBUG_LOG_KEEP + 4096
    assert lines[-1] in kept and lines[0] not in kept
    assert kept.startswith("[2026-01-01")  # trimmed at a line boundary


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
