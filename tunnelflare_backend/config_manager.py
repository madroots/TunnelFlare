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
            "tunnels": [] # List of {name, port, protocol='http'}
        }

    def add_tunnel(self, name, port):
        # Ensure latest state before adding
        self.config = self._load_config()
        self.remove_tunnel(name) # Replace if exists
        
        tunnels = self.config.get("tunnels", [])
        tunnels.append({
            "name": name,
            "port": port,
            "protocol": "http" # Always http as requested
        })
        self.config["tunnels"] = tunnels
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
