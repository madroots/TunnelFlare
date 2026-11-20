import subprocess
import os
import time
import re
import shutil
import sys
import psutil
from pathlib import Path
from tunnelflare_backend.config_manager import ConfigManager

QUICK_TUNNEL_URL = re.compile(r"https://([a-zA-Z0-9-]+)\.trycloudflare\.com")

class TunnelManager:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.dirs = self.config_manager.get_dirs()
        self.tunnels_dir = self.dirs["tunnels"]
        self.logs_dir = self.dirs["logs"]
        self.bin_dir = self.dirs["bin"]
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

    def _bundled_cloudflared(self):
        """cloudflared shipped inside a frozen (PyInstaller) build; None when running from source."""
        if not getattr(sys, "frozen", False):
            return None
        name = "cloudflared.exe" if sys.platform == "win32" else "cloudflared"
        return Path(sys._MEIPASS) / name

    def _get_cloudflared_path(self):
        bundled_path = self._bundled_cloudflared()
        if bundled_path is None:
            # Running from source: use the cloudflared installed on PATH
            return shutil.which("cloudflared")
        if not bundled_path.exists():
            self._log(f"Bundled cloudflared missing: {bundled_path}")
            return None

        # Run a stable copy outside the app bundle: its path survives app updates
        # (firewall rules stay valid) and running tunnels keep no app files busy.
        persistent_path = self.bin_dir / bundled_path.name
        bundled_stat = bundled_path.stat()
        if persistent_path.exists():
            persistent_stat = persistent_path.stat()
            if (persistent_stat.st_size == bundled_stat.st_size
                    and abs(persistent_stat.st_mtime - bundled_stat.st_mtime) < 2):
                return str(persistent_path)

        staged_path = persistent_path.with_name(persistent_path.name + ".new")
        try:
            self._log(f"Syncing bundled binary: {bundled_path} -> {persistent_path}")
            shutil.copy2(bundled_path, staged_path)
            if sys.platform != "win32":
                staged_path.chmod(0o755)
            # Atomic swap: a tunnel still running the old binary keeps its file
            os.replace(staged_path, persistent_path)
        except OSError as e:
            # On Windows the swap fails while a tunnel runs from the old copy
            self._log(f"Persistent binary sync skipped (possibly in use): {e}")
            staged_path.unlink(missing_ok=True)
            if not persistent_path.exists():
                return str(bundled_path)
        return str(persistent_path)

    def check_dependencies(self):
        path = self._get_cloudflared_path()
        self._log(f"Dependency check: cloudflared found at {path}")
        return path is not None

    @staticmethod
    def _sanitize(name):
        return re.sub(r'[^a-zA-Z0-9_-]', '_', name)

    def generate_tunnel_id(self, name):
        # Sanitize name
        clean_name = self._sanitize(name)
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
        stderr_file = self.logs_dir / f"{tunnel_id}.stderr.log"
        pid_file = self.tunnels_dir / f"{tunnel_id}.pid"
        config_file = self.tunnels_dir / f"{tunnel_id}.config"

        url = f"{protocol}://localhost:{port}"

        # Write config metadata
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(f"NAME={name}\n")
            f.write(f"PORT={port}\n")
            f.write(f"PROTOCOL={protocol}\n")
            f.write(f"START_TIME={time.time()}\n")

        # Start cloudflared
        output_handle = None
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
                # Force http2 and IPv4 for better compatibility through Windows firewalls
                cmd = [cf_path, "--no-autoupdate", "tunnel", "--protocol", "http2", "--edge-ip-version", "4", "--url", url, "--logfile", str(log_file)]
                # stderr goes to a file: an unread pipe fills up and stalls cloudflared
                output_file = stderr_file
                output_handle = open(output_file, 'w', encoding='utf-8')
                kwargs = {
                    "stdout": subprocess.DEVNULL,
                    "stderr": output_handle,
                    "creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
                }
            else:
                output_file = log_file
                output_handle = open(output_file, 'w', encoding='utf-8')
                cmd = [cf_path, "--no-autoupdate", "tunnel", "--url", url]
                kwargs = {
                    "stdout": output_handle,
                    "stderr": subprocess.STDOUT,
                    "start_new_session": True
                }

            self._log(f"Executing: {' '.join(cmd)}")
            process = subprocess.Popen(cmd, **kwargs)
            output_handle.close()  # the child keeps its own handle

            # Record the PID with the process start time right away: the tunnel stays
            # manageable even if the app exits now, and a reused PID is never
            # mistaken for it later.
            try:
                started = psutil.Process(process.pid).create_time()
            except psutil.NoSuchProcess:
                started = None  # exited already; reported below
            if started is not None:
                staged_pid_file = pid_file.with_name(pid_file.name + ".tmp")
                staged_pid_file.write_text(f"{process.pid} {started}")
                os.replace(staged_pid_file, pid_file)

            # Check if it died immediately (e.g. invalid flags or binary error)
            time.sleep(1.0) # Give it a bit more time to fail
            if process.poll() is not None:
                try:
                    output = output_file.read_text(encoding='utf-8', errors='ignore').strip()
                except OSError:
                    output = ""

                if "forbidden by its access permissions" in output:
                    error_msg = "Firewall or Antivirus is blocking the connection to Cloudflare. Please add an exclusion for TunnelFlare."
                else:
                    error_msg = output[-800:] if output else "Unknown startup error"
                
                raise RuntimeError(f"cloudflared exited immediately with code {process.returncode}. {error_msg}")

            self._log(f"Started tunnel {tunnel_id} (PID: {process.pid})")
            return tunnel_id
        except Exception as e:
            self._log(f"Error starting tunnel: {str(e)}")
            # Cleanup on failure
            if output_handle: output_handle.close()
            if pid_file.exists(): pid_file.unlink()
            if config_file.exists(): config_file.unlink()
            raise e

    def stop_tunnel(self, tunnel_id):
        pid_file = self.tunnels_dir / f"{tunnel_id}.pid"
        if not pid_file.exists():
            return False

        try:
            proc = self._tunnel_process(pid_file)
            if proc is not None:
                # Terminate properly cross-platform
                proc.terminate()
                
                # Wait for it to die
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            
            self._cleanup_tunnel_files(tunnel_id)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
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

    def _tunnel_process(self, pid_file):
        """The live cloudflared process recorded in pid_file, or None if it has exited.

        PID files hold "<pid> <create_time>": after a crash or reboot the PID can
        belong to an unrelated process, which must never be reported or terminated.
        """
        try:
            fields = pid_file.read_text().split()
            pid = int(fields[0])
            started = float(fields[1]) if len(fields) > 1 else None
            proc = psutil.Process(pid)
            if proc.status() == psutil.STATUS_ZOMBIE:
                self._reap(pid)
                return None
            if started is None:
                # PID file from an older version: trust only a cloudflared process
                return proc if "cloudflared" in proc.name().lower() else None
            return proc if abs(proc.create_time() - started) < 1.0 else None
        except (IndexError, ValueError, OSError, psutil.Error):
            return None

    @staticmethod
    def _reap(pid):
        # A child that exited stays a zombie until it is waited for (POSIX only)
        if os.name == "posix":
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass

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
                
            # Skip api.trycloudflare.com, which appears in cloudflared's error messages
            hosts = [host for host in QUICK_TUNNEL_URL.findall(content) if host != "api"]
            if hosts:
                 return f"https://{hosts[-1]}.trycloudflare.com"
                 
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
        
        # If not active, fall back to the default ID (the sanitized name)
        if not target_id:
            target_id = self._sanitize(name)

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
            
            # Check if running (and that the PID still belongs to our cloudflared)
            proc = self._tunnel_process(pid_file)
            if proc is None:
                # Dead tunnel cleanup
                self._cleanup_tunnel_files(tunnel_id)
                continue
            pid = proc.pid
                
            # Read config
            name = tunnel_id
            port = "?"
            protocol = "?"
            if config_file.exists():
                content = config_file.read_text(encoding='utf-8')
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
