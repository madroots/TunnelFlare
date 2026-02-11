import subprocess
import os
import time
import re
import shutil
import sys
import psutil
from pathlib import Path
from tunnelflare_backend.config_manager import ConfigManager

class TunnelManager:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.dirs = self.config_manager.get_dirs()
        self.tunnels_dir = self.dirs["tunnels"]
        self.logs_dir = self.dirs["logs"]
        self.debug_log = self.config_manager.config_dir / "debug.log"

    def _log(self, message):
        with open(self.debug_log, 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")

    def _get_cloudflared_path(self):
        # 1. Check in sys._MEIPASS (Windows PyInstaller)
        if hasattr(sys, '_MEIPASS'):
            ext = ".exe" if sys.platform == "win32" else ""
            path = Path(sys._MEIPASS) / f"cloudflared{ext}"
            if path.exists(): 
                return str(path)

        # 2. Check in APPDIR (Linux AppImage)
        appdir = os.environ.get('APPDIR')
        if appdir:
            path = Path(appdir) / "usr" / "bin" / "cloudflared"
            if path.exists(): return str(path)

        # 3. Check in system PATH
        return shutil.which("cloudflared")

    def check_dependencies(self):
        path = self._get_cloudflared_path()
        self._log(f"Dependency check: cloudflared found at {path}")
        return path is not None

    def generate_tunnel_id(self, name):
        # Sanitize name
        clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        # Ensure uniqueness
        if not (self.tunnels_dir / f"{clean_name}.pid").exists():
            return clean_name
        
        counter = 1
        while (self.tunnels_dir / f"{clean_name}_{counter}.pid").exists():
            counter += 1
        return f"{clean_name}_{counter}"

    def start_tunnel(self, name, port, protocol="http"):
        if not self.check_dependencies():
            raise RuntimeError("cloudflared is not installed")

        tunnel_id = self.generate_tunnel_id(name)
        log_file = self.logs_dir / f"{tunnel_id}.log"
        pid_file = self.tunnels_dir / f"{tunnel_id}.pid"
        config_file = self.tunnels_dir / f"{tunnel_id}.config"

        url = f"{protocol}://localhost:{port}"

        # Write config metadata
        with open(config_file, 'w') as f:
            f.write(f"NAME={name}\n")
            f.write(f"PORT={port}\n")
            f.write(f"PROTOCOL={protocol}\n")
            f.write(f"START_TIME={time.time()}\n")

        # Start cloudflared
        try:
            url = f"{protocol}://localhost:{port}"
            cf_path = self._get_cloudflared_path()
            if not cf_path:
                raise RuntimeError("cloudflared binary not found")
            
            # Platform specific subprocess flags
            if sys.platform == "win32":
                # On Windows, using --logfile is much more reliable than shell redirection
                cmd = [cf_path, "tunnel", "--url", url, "--logfile", str(log_file)]
                kwargs = {
                    "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.DEVNULL,
                    "creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
                }
            else:
                log_handle = open(log_file, 'w', encoding='utf-8')
                cmd = [cf_path, "tunnel", "--url", url]
                kwargs = {
                    "stdout": log_handle,
                    "stderr": subprocess.STDOUT,
                    "start_new_session": True
                }

            self._log(f"Executing: {' '.join(cmd)}")
            process = subprocess.Popen(cmd, **kwargs)
            
            if sys.platform != "win32":
                log_handle.close()
            
            with open(pid_file, 'w') as f:
                f.write(str(process.pid))
            
            self._log(f"Started tunnel {tunnel_id} (PID: {process.pid})")
            return tunnel_id
        except Exception as e:
            self._log(f"Error starting tunnel: {str(e)}")
            # Cleanup on failure
            if pid_file.exists(): pid_file.unlink()
            if config_file.exists(): config_file.unlink()
            raise e

    def stop_tunnel(self, tunnel_id):
        pid_file = self.tunnels_dir / f"{tunnel_id}.pid"
        if not pid_file.exists():
            return False

        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                # Terminate properly cross-platform
                proc.terminate()
                
                # Wait for it to die
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    proc.kill()
            
            self._cleanup_tunnel_files(tunnel_id)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
            # Process might be already dead or no permission
            self._cleanup_tunnel_files(tunnel_id)
            return False
        except Exception:
            self._cleanup_tunnel_files(tunnel_id)
            return False

    def stop_all(self):
        tunnels = self.get_active_tunnels()
        for tunnel in tunnels:
            self.stop_tunnel(tunnel['id'])

    def _cleanup_tunnel_files(self, tunnel_id):
        pid_file = self.tunnels_dir / f"{tunnel_id}.pid"
        config_file = self.tunnels_dir / f"{tunnel_id}.config"
        if pid_file.exists(): pid_file.unlink()
        if config_file.exists(): config_file.unlink()

    def get_public_url(self, tunnel_id):
        log_file = self.logs_dir / f"{tunnel_id}.log"
        if not log_file.exists():
            return None
        
        try:
            # On Windows, use sharing-friendly read
            # We use 'r' and let Python handle encoding issues with 'ignore'
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            matches = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
            if matches:
                 return matches[-1]
        except (PermissionError, OSError):
            # Windows might lock the file while cloudflared writes to it
            return None
        except Exception:
            pass
        return None

    def get_logs_by_name(self, name):
        active = self.get_active_tunnels()
        target_id = None
        for t in active:
            if t['name'] == name:
                target_id = t['id']
                break
        
        if not target_id: return None
        
        log_file = self.logs_dir / f"{target_id}.log"
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            except (PermissionError, OSError):
                return "Loading logs (file locked or cloudflared initializing)..."
        return None

    def get_active_tunnels(self):
        tunnels = []
        for pid_file in self.tunnels_dir.glob("*.pid"):
            tunnel_id = pid_file.stem
            config_file = self.tunnels_dir / f"{tunnel_id}.config"
            
            # Check if running
            try:
                pid = int(pid_file.read_text().strip())
                if not psutil.pid_exists(pid):
                    raise psutil.NoSuchProcess(pid)
            except (psutil.NoSuchProcess, ValueError, OSError):
                # Dead tunnel cleanup
                self._cleanup_tunnel_files(tunnel_id)
                continue
                
            # Read config
            name = tunnel_id
            port = "?"
            protocol = "?"
            if config_file.exists():
                content = config_file.read_text()
                for line in content.splitlines():
                    if line.startswith("NAME="): name = line[5:]
                    if line.startswith("PORT="): port = line[5:]
                    if line.startswith("PROTOCOL="): protocol = line[9:]

            public_url = self.get_public_url(tunnel_id)
            
            tunnels.append({
                "id": tunnel_id,
                "name": name,
                "port": port,
                "protocol": protocol,
                "pid": pid,
                "public_url": public_url,
                "status": "Running" if public_url else "Initializing"
            })
            
        return tunnels
