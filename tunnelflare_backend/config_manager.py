import os
import re
import json
import time
from pathlib import Path


def default_config_dir():
    """Config root: $TUNNELFLARE_HOME if set (tests, self-test), else ~/.tunnelflare."""
    override = os.environ.get("TUNNELFLARE_HOME")
    return Path(override).expanduser() if override else Path.home() / ".tunnelflare"


def tunnel_id_for(name):
    """File-safe ID of a tunnel: its PID, config and log files are named after it."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)


class ConfigManager:
    def __init__(self):
        self.config_dir = default_config_dir()
        self.config_file = self.config_dir / "config.json"
        self.tunnels_dir = self.config_dir / "tunnels"
        self.logs_dir = self.config_dir / "logs"
        self.bin_dir = self.config_dir / "bin"
        self._ensure_directories()
        self.config = self._load_config()

    def _ensure_directories(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.tunnels_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.bin_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self):
        if not self.config_file.exists():
            return self._default_config()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return self._default_config()

    def _default_config(self):
        return {
            "tunnels": [] # List of {name, port, protocol, rewrite_host}
        }

    def name_conflict(self, name, ignore=None):
        """Name of an existing tunnel that `name` would clash with, or None.

        Names clash when their file-safe IDs match ignoring case ("my api" and
        "My_API" would share files on Windows and macOS)."""
        wanted = tunnel_id_for(name).lower()
        for tunnel in self.get_tunnels():
            if tunnel['name'] != ignore and tunnel_id_for(tunnel['name']).lower() == wanted:
                return tunnel['name']
        return None

    def get_tunnel(self, name):
        return next((t for t in self.get_tunnels() if t['name'] == name), None)

    def add_tunnel(self, name, port, protocol="http", rewrite_host=False):
        conflict = self.name_conflict(name)
        if conflict:
            raise ValueError(f"A tunnel named '{conflict}' already exists.")
        # name_conflict() reloaded the latest state
        self.config.setdefault("tunnels", []).append(_tunnel_entry(name, port, protocol, rewrite_host))
        self.save_config()

    def update_tunnel(self, old_name, name, port, protocol="http", rewrite_host=False):
        conflict = self.name_conflict(name, ignore=old_name)
        if conflict:
            raise ValueError(f"A tunnel named '{conflict}' already exists.")
        tunnels = self.config.get("tunnels", [])
        index = next((i for i, t in enumerate(tunnels) if t['name'] == old_name), None)
        if index is None:
            raise ValueError(f"Tunnel '{old_name}' no longer exists.")
        tunnels[index] = _tunnel_entry(name, port, protocol, rewrite_host)
        self.save_config()

    def remove_tunnel(self, name):
        # Ensure latest state before removing
        self.config = self._load_config()
        tunnels = self.config.get("tunnels", [])
        self.config["tunnels"] = [t for t in tunnels if t['name'] != name]
        self.save_config()

    
    def get_tunnels(self):
        self.config = self._load_config()
        return self.config.get("tunnels", [])

    def save_config(self):
        # Write a complete temp file, then atomically swap it in: a crash or a
        # full disk can never leave a truncated config.json behind.
        tmp_file = self.config_file.with_name(self.config_file.name + ".tmp")
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(5):
            try:
                os.replace(tmp_file, self.config_file)
                return
            except PermissionError:
                # Windows refuses the swap while another thread is reading the file.
                if attempt == 4:
                    raise
                time.sleep(0.05)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config = self._load_config()  # keep tunnels saved by other instances
        self.config[key] = value
        self.save_config()

    def get_dirs(self):
        return {
            "config": self.config_dir,
            "tunnels": self.tunnels_dir,
            "logs": self.logs_dir,
            "bin": self.bin_dir
        }


def _tunnel_entry(name, port, protocol, rewrite_host):
    return {
        "name": name,
        "port": int(port),
        "protocol": "https" if protocol == "https" else "http",
        "rewrite_host": bool(rewrite_host),
    }
