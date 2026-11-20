import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FAKE_CLOUDFLARED = Path(__file__).with_name("fake_cloudflared.py")


@pytest.fixture(autouse=True)
def tunnelflare_home(tmp_path, monkeypatch):
    """Each test gets its own config dir instead of ~/.tunnelflare."""
    home = tmp_path / "tunnelflare-home"
    monkeypatch.setenv("TUNNELFLARE_HOME", str(home))
    return home


@pytest.fixture
def listening_port():
    """A localhost port with something listening on it, like a running dev server."""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        yield server.getsockname()[1]


@pytest.fixture
def fake_cloudflared(monkeypatch):
    """Launch tests/fake_cloudflared.py wherever the app would launch cloudflared.

    Returns a function to switch the fake's behaviour: mode "ok" or "fail", and
    how long it waits before logging its quick-tunnel URL.
    """
    from tunnelflare_backend import tunnel_manager

    marker = "fake-cloudflared"
    real_popen = subprocess.Popen

    def popen(cmd, *args, **kwargs):
        if cmd and cmd[0] == marker:
            cmd = [sys.executable, str(FAKE_CLOUDFLARED), *cmd[1:]]
        return real_popen(cmd, *args, **kwargs)

    monkeypatch.setattr(tunnel_manager.subprocess, "Popen", popen)
    monkeypatch.setattr(tunnel_manager.TunnelManager, "_get_cloudflared_path", lambda self: marker)

    def configure(mode="ok", url_delay=0.0):
        monkeypatch.setenv("FAKE_CLOUDFLARED_MODE", mode)
        monkeypatch.setenv("FAKE_CLOUDFLARED_URL_DELAY", str(url_delay))

    configure()
    return configure


@pytest.fixture
def manager():
    from tunnelflare_backend.tunnel_manager import TunnelManager

    tunnel_manager = TunnelManager()
    yield tunnel_manager
    tunnel_manager.stop_all()
