import os
import json
from pathlib import Path

class ConfigManager:
    def __init__(self):
        self.config_dir = Path.home() / ".tunnelflare"
        self.config_file = self.config_dir / "config.json"
        self.tunnels_dir = self.config_dir / "tunnels"
        self.logs_dir = self.config_dir / "logs"
        self._ensure_directories()
        self.config = self._load_config()

    def _ensure_directories(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.tunnels_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self):
        if not self.config_file.exists():
            return self._default_config()
        
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return self._default_config()

    def _default_config(self):
        return {
            "default_port": 3000,
            "default_protocol": "http",
            "dark_mode": True
        }

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def get_dirs(self):
        return {
            "config": self.config_dir,
            "tunnels": self.tunnels_dir,
            "logs": self.logs_dir
        }
