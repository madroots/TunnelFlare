import subprocess
import os
import time
import re
import shutil
import socket
import sys
import psutil
from pathlib import Path
from tunnelflare_backend.config_manager import ConfigManager, tunnel_id_for

QUICK_TUNNEL_URL = re.compile(r"https://([a-zA-Z0-9-]+)\.trycloudflare\.com")
# cloudflared log lines that mark the edge connection going up and down
CONNECTED_MARKER = "Registered tunnel connection"
DISCONNECTED = re.compile(
    r"Unregistered tunnel connection|Retrying connection in|Serve tunnel error"
    r"|Connection terminated|Lost connection with the edge|failed to serve tunnel connection",
    re.IGNORECASE,
)
DEBUG_LOG_LIMIT = 1024 * 1024  # trim debug.log beyond 1 MiB ...
DEBUG_LOG_KEEP = 256 * 1024  # ... down to its last 256 KiB


class TunnelManager:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.dirs = self.config_manager.get_dirs()
        self.tunnels_dir = self.dirs["tunnels"]
        self.logs_dir = self.dirs["logs"]
        self.bin_dir = self.dirs["bin"]
        self.debug_log = self.config_manager.config_dir / "debug.log"
        self._log_scan = {}  # tunnel_id -> incremental parse state of its cloudflared log
        self._trim_debug_log()

        # Initial diagnostic entry
        self._log("--- TunnelManager initialized ---")
        self._log(f"Platform: {sys.platform}")
        self._log(f"Executable: {sys.executable}")
        self._log(f"MEIPASS: {getattr(sys, '_MEIPASS', 'None')}")
        self._log(f"APPDIR: {os.environ.get('APPDIR', 'None')}")

    def _log(self, message):
        with open(self.debug_log, 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")

    def _trim_debug_log(self):
        try:
            if self.debug_log.stat().st_size <= DEBUG_LOG_LIMIT:
                return
            with open(self.debug_log, 'rb') as f:
                f.seek(-DEBUG_LOG_KEEP, os.SEEK_END)
                tail = f.read()
            tail = tail[tail.find(b"\n") + 1:]  # drop the partial first line
            staged = self.debug_log.with_name(self.debug_log.name + ".tmp")
            staged.write_bytes(tail)
            os.replace(staged, self.debug_log)
        except OSError:
            pass

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
    def is_port_listening(port, timeout=0.3):
        """True if something accepts TCP connections on localhost:port (IPv4 or IPv6)."""
        for host in ("127.0.0.1", "::1"):
            try:
                with socket.create_connection((host, int(port)), timeout=timeout):
                    return True
            except OSError:
                continue
        return False

    def generate_tunnel_id(self, name):
        # Sanitize name
        clean_name = tunnel_id_for(name)
        # Ensure uniqueness
        if not (self.tunnels_dir / f"{clean_name}.pid").exists():
            return clean_name
        
        counter = 1
        while (self.tunnels_dir / f"{clean_name}_{counter}.pid").exists():
            counter += 1
        return f"{clean_name}_{counter}"

    def start_tunnel(self, name, port, protocol="http", rewrite_host=False):
        if not self.check_dependencies():
            raise RuntimeError("cloudflared is not installed")

        tunnel_id = self.generate_tunnel_id(name)
        log_file = self.logs_dir / f"{tunnel_id}.log"
        stderr_file = self.logs_dir / f"{tunnel_id}.stderr.log"
        pid_file = self.tunnels_dir / f"{tunnel_id}.pid"
        config_file = self.tunnels_dir / f"{tunnel_id}.config"
        protocol = "https" if protocol == "https" else "http"

        # Write config metadata
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(f"NAME={name}\n")
            f.write(f"PORT={port}\n")
            f.write(f"PROTOCOL={protocol}\n")
            f.write(f"START_TIME={time.time()}\n")

        # Every run starts with a fresh log on every OS
        self._log_scan.pop(tunnel_id, None)
        try:
            log_file.unlink(missing_ok=True)
        except OSError:
            pass

        # Start cloudflared
        output_handle = None
        try:
            # Use 127.0.0.1 instead of localhost for Windows stability
            host = "127.0.0.1" if sys.platform == "win32" else "localhost"
            url = f"{protocol}://{host}:{port}"
            cf_path = self._get_cloudflared_path()
            if not cf_path:
                raise RuntimeError("cloudflared binary not found")
            
            # Same transport on every OS: HTTP/2 over TCP to an IPv4 edge. QUIC (UDP 7844)
            # is often blocked by firewalls, and cloudflared's fallback can take minutes.
            # Global flags MUST come before the command (tunnel)
            cmd = [cf_path, "--no-autoupdate", "tunnel", "--protocol", "http2", "--edge-ip-version", "4", "--url", url]
            if rewrite_host:
                # Dev servers (Vite, webpack, Django) reject unknown Host headers
                cmd += ["--http-host-header", f"localhost:{port}"]
            if protocol == "https":
                # Local HTTPS dev servers use self-signed certificates
                cmd += ["--no-tls-verify"]

            # Platform specific subprocess flags
            if sys.platform == "win32":
                cmd += ["--logfile", str(log_file)]
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
        self._log_scan.pop(tunnel_id, None)

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

    def _scan_log(self, tunnel_id):
        """(public URL or None, connection state) parsed from the tunnel's log.

        Reads only what cloudflared appended since the last call. The state is
        "starting" until the first edge connection registers, then "connected",
        or "reconnecting" after the connection drops.
        """
        log_file = self.logs_dir / f"{tunnel_id}.log"
        scan = self._log_scan.get(tunnel_id)
        try:
            size = log_file.stat().st_size
        except OSError:
            return (scan["url"], scan["state"]) if scan else (None, "starting")
        if scan is None or size < scan["offset"]:
            scan = {"offset": 0, "partial": "", "url": None, "state": "starting"}
            self._log_scan[tunnel_id] = scan
        if size > scan["offset"]:
            try:
                # Windows: cloudflared may hold the file briefly; try again next time
                with open(log_file, 'rb') as f:
                    f.seek(scan["offset"])
                    chunk = f.read(size - scan["offset"])
            except OSError:
                return scan["url"], scan["state"]
            scan["offset"] += len(chunk)
            lines = (scan["partial"] + chunk.decode('utf-8', errors='ignore')).split("\n")
            scan["partial"] = lines.pop()  # keep an unfinished last line for later
            for line in lines:
                # Skip api.trycloudflare.com, which appears in cloudflared's error messages
                hosts = [host for host in QUICK_TUNNEL_URL.findall(line) if host != "api"]
                if hosts:
                    scan["url"] = f"https://{hosts[-1]}.trycloudflare.com"
                if CONNECTED_MARKER in line:
                    scan["state"] = "connected"
                elif scan["state"] == "connected" and DISCONNECTED.search(line):
                    scan["state"] = "reconnecting"
        return scan["url"], scan["state"]

    def get_public_url(self, tunnel_id):
        return self._scan_log(tunnel_id)[0]

    def get_logs_by_name(self, name):
        active = self.get_active_tunnels()
        target_id = None
        for t in active:
            if t['name'] == name:
                target_id = t['id']
                break
        
        # If not active, fall back to the default ID (the sanitized name)
        if not target_id:
            target_id = tunnel_id_for(name)

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
        """Running tunnels. "status" is Initializing (no URL yet), Connecting (URL
        allocated, edge connection not up yet), Running, or Reconnecting."""
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

            public_url, state = self._scan_log(tunnel_id)
            if not public_url:
                status = "Initializing"
            else:
                status = {"connected": "Running", "reconnecting": "Reconnecting"}.get(state, "Connecting")
            
            tunnels.append({
                "id": tunnel_id,
                "name": name,
                "port": port,
                "protocol": protocol,
                "pid": pid,
                "public_url": public_url,
                "status": status,
            })
            
        return tunnels

    def get_debug_log_path(self):
        return str(self.debug_log)
