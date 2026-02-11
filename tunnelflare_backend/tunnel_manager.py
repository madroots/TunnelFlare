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
        
        # Initial diagnostic entry
        self._log("--- TunnelManager initialized ---")
        self._log(f"Platform: {sys.platform}")
        self._log(f"Executable: {sys.executable}")
        self._log(f"MEIPASS: {getattr(sys, '_MEIPASS', 'None')}")
        self._log(f"APPDIR: {os.environ.get('APPDIR', 'None')}")

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
            # If we're on Windows, check if it's in the root of the MEIPASS or the current dir
            if sys.platform == "win32":
                p2 = Path(sys.executable).parent / "cloudflared.exe"
                if p2.exists(): return str(p2)

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
            # Use 127.0.0.1 instead of localhost for Windows stability
            host = "127.0.0.1" if sys.platform == "win32" else "localhost"
            url = f"{protocol}://{host}:{port}"
            cf_path = self._get_cloudflared_path()
            if not cf_path:
                raise RuntimeError("cloudflared binary not found")
            
            # Platform specific subprocess flags
            if sys.platform == "win32":
                # Global flags MUST come before the command (tunnel)
                # On Windows, using --logfile is much more reliable than shell redirection
                cmd = [cf_path, "--loglevel", "info", "--no-autoupdate", "tunnel", "--url", url, "--logfile", str(log_file)]
                kwargs = {
                    "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.PIPE, # Capture stderr for the startup check
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
            
            # Check if it died immediately (e.g. invalid flags or binary error)
            time.sleep(1.0) # Give it a bit more time to fail
            if process.poll() is not None:
                stderr_data = ""
                if sys.platform == "win32" and process.stderr:
                    try:
                        stderr_data = process.stderr.read().decode('utf-8', errors='ignore')
                    except:
                        stderr_data = "Could not read stderr"
                
                if "forbidden by its access permissions" in stderr_data:
                    error_msg = "Firewall or Antivirus is blocking the connection to Cloudflare. Please add an exclusion for TunnelFlare."
                else:
                    error_msg = stderr_data if stderr_data else "Unknown startup error"
                
                raise RuntimeError(f"cloudflared exited immediately with code {process.returncode}. {error_msg}")

            if sys.platform != "win32":
                log_handle.close()
            elif process.stderr:
                # On Windows, we need to handle the pipe if we're keeping it running
                # Actually, if we use PIPE we must read it or it fills up.
                # Better: for Windows successfully started processes, we don't need stderr anymore.
                # But we can't easily "close" the pipe from here if the process is alive without potentially hanging.
                # However, since we used CREATE_NO_WINDOW and redirected to --logfile, stderr shouldn't be noisy.
                pass
            
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
            
            if not content:
                return None
                
            matches = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
            if matches:
                 return matches[-1]
                 
            # If no match but we have content, log a snippet for debugging if it's been a while
            if len(content) > 0 and len(content) < 500:
                self._log(f"Log content for {tunnel_id} ({len(content)} bytes): {content[:100]}...")
        except (PermissionError, OSError) as e:
            # Windows might lock the file while cloudflared writes to it
            self._log(f"Log read lock for {tunnel_id}: {str(e)}")
            return None
        except Exception as e:
            self._log(f"Log read error for {tunnel_id}: {str(e)}")
        return None

    def get_logs_by_name(self, name):
        active = self.get_active_tunnels()
        target_id = None
        for t in active:
            if t['name'] == name:
                target_id = t['id']
                break
        
        # If not active, but we have a config, use the name as ID (default)
        if not target_id:
            target_id = name

        # 1. Get Tunnel Logs
        tunnel_logs = ""
        log_file = self.logs_dir / f"{target_id}.log"
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    tunnel_logs = f.read()
            except (PermissionError, OSError):
                tunnel_logs = "(Tunnel log file is currently locked by cloudflared...)\n"

        # 2. Get Internal Debug Logs (last 20 lines)
        debug_header = "\n" + "="*40 + "\n   INTERNAL SYSTEM LOGS (DIAGNOSTICS)\n" + "="*40 + "\n"
        debug_logs = ""
        if self.debug_log.exists():
             try:
                 with open(self.debug_log, 'r', encoding='utf-8', errors='ignore') as f:
                     lines = f.readlines()
                     # Filter for relevant logs (containing tunnel_id or name)
                     relevant = [l for l in lines if target_id in l or name in l or "---" in l]
                     debug_logs = "".join(relevant[-20:])
             except:
                 pass
        
        if not tunnel_logs and not debug_logs:
            return "No logs found for this tunnel yet."
            
        return f"{tunnel_logs}{debug_header}{debug_logs}"

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
    def get_debug_log_path(self):
        return str(self.debug_log)
