#!/usr/bin/env python3

"""
CF Tunnel Manager - Python Qt WebEngine Application
A modern GUI for managing Cloudflare tunnels
"""

import sys
import os
import subprocess
import json
from pathlib import Path
from threading import Thread

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QTextEdit, QLabel, QSystemTrayIcon, QMenu,
    QInputDialog, QLineEdit, QTabWidget, QSplitter, QMessageBox, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtGui import QAction, QKeySequence, QIcon, QPixmap, QPalette, QColor
from PySide6.QtCore import QUrl, QTimer, QProcess, Signal, QObject


class TunnelManager(QObject):
    """Handles interaction with the original bash script"""
    
    # Signals for communication with UI
    tunnels_updated = Signal(list)
    log_message = Signal(str)
    
    def __init__(self, script_path="../source_script.sh"):
        super().__init__()
        self.script_path = os.path.expanduser(script_path)
        # Create .cf-tunnels directory if it doesn't exist
        os.makedirs(os.path.expanduser("~/.cf-tunnels"), exist_ok=True)
        os.makedirs(os.path.expanduser("~/.cf-tunnels/logs"), exist_ok=True)
        
    def run_command(self, command):
        """Execute a command and return output"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                executable='/bin/bash'
            )
            return result.stdout, result.stderr, result.returncode
        except Exception as e:
            return "", str(e), 1
    
    def get_running_tunnels(self):
        """Get a list of running tunnels by parsing the files"""
        tunnels_dir = os.path.expanduser("~/.cf-tunnels")
        if not os.path.exists(tunnels_dir):
            os.makedirs(tunnels_dir)

        logs_dir = os.path.expanduser("~/.cf-tunnels/logs")
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)

        # Get all .pid files
        pid_files = []
        for f in os.listdir(tunnels_dir):
            if f.endswith('.pid'):
                pid_files.append(f)

        tunnels = []
        for pid_file in pid_files:
            tunnel_id = pid_file.replace('.pid', '')

            # Read PID
            pid_path = os.path.join(tunnels_dir, pid_file)
            try:
                with open(pid_path, 'r') as f:
                    pid_content = f.read().strip()

                # Check if PID is valid
                try:
                    pid = int(pid_content)
                except ValueError:
                    print(f"Invalid PID in file {pid_file}: {pid_content}")
                    # Clean up invalid PID file
                    os.remove(pid_path)
                    config_file = os.path.join(tunnels_dir, f"{tunnel_id}.config")
                    if os.path.exists(config_file):
                        os.remove(config_file)
                    continue

                # Check if process is still running
                process_running = self.is_process_running(pid)
                if not process_running:
                    # Cleanup dead PID file
                    os.remove(pid_path)
                    config_file = os.path.join(tunnels_dir, f"{tunnel_id}.config")
                    if os.path.exists(config_file):
                        os.remove(config_file)
                    continue

                # Read config
                config = {
                    'name': tunnel_id,
                    'port': '3000',
                    'protocol': 'http',
                    'pid': pid
                }

                config_path = os.path.join(tunnels_dir, f"{tunnel_id}.config")
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('NAME='):
                                config['name'] = line[5:]
                            elif line.startswith('PORT='):
                                config['port'] = line[5:]
                            elif line.startswith('PROTOCOL='):
                                config['protocol'] = line[9:]

                # Extract public URL from log
                log_path = os.path.join(logs_dir, f"{tunnel_id}.log")
                public_url = ""
                if os.path.exists(log_path):
                    with open(log_path, 'r') as f:
                        content = f.read()
                        # Extract URL pattern - look for the actual cloudflare domain
                        import re
                        matches = re.findall(r'https://[a-zA-Z0-9-]*\.trycloudflare\.com', content)
                        if matches:
                            public_url = matches[-1]  # Get the last found URL

                tunnel_info = {
                    'id': tunnel_id,
                    'name': config['name'],
                    'port': config['port'],
                    'protocol': config['protocol'],
                    'pid': str(pid),  # Keep as string to match UI expectations
                    'public_url': public_url,
                    'is_running': process_running
                }

                tunnels.append(tunnel_info)
            except FileNotFoundError:
                # File was deleted between list and read
                continue
            except Exception as e:
                print(f"Error reading tunnel {pid_file}: {e}")
                # Don't continue here, just skip the problematic tunnel

        return tunnels
    
    def is_process_running(self, pid):
        """Check if a process with given PID is running"""
        try:
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
            return True
        except OSError:
            return False
    
    def start_tunnel(self, name, port, protocol="http"):
        """Start a new tunnel"""
        # Validate inputs
        try:
            port_int = int(port)
            if port_int < 1 or port_int > 65535:
                raise ValueError("Port must be between 1 and 65535")
        except ValueError:
            self.log_message.emit(f"Invalid port: {port}")
            return False

        if protocol not in ['http', 'https']:
            self.log_message.emit(f"Invalid protocol: {protocol}. Must be http or https")
            return False

        # Sanitize name
        import re
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        if not sanitized_name:
            import uuid
            sanitized_name = f"app_{str(uuid.uuid4())[:8]}"

        # Check for duplicate names and increment if needed
        tunnels_dir = os.path.expanduser("~/.cf-tunnels")
        counter = 1
        final_name = sanitized_name
        full_path = os.path.join(tunnels_dir, f"{final_name}.pid")
        while os.path.exists(full_path):
            final_name = f"{sanitized_name}_{counter}"
            full_path = os.path.join(tunnels_dir, f"{final_name}.pid")
            if not self.is_process_running_for_pid_file(full_path):  # Check if process is actually running
                # Dead PID file, can reuse the name
                break
            counter += 1

        # Create config file
        config_path = os.path.join(tunnels_dir, f"{final_name}.config")
        with open(config_path, 'w') as f:
            f.write(f"NAME={final_name}\n")
            f.write(f"PORT={port}\n")
            f.write(f"PROTOCOL={protocol}\n")
            f.write(f"START_TIME={self.get_timestamp()}\n")

        # Start the tunnel process
        url = f"{protocol}://localhost:{port}"
        logs_dir = os.path.expanduser("~/.cf-tunnels/logs")

        # Make sure logs directory exists
        os.makedirs(logs_dir, exist_ok=True)

        log_path = os.path.join(logs_dir, f"{final_name}.log")

        # Start cloudflared using a more reliable subprocess approach with proper PID management
        try:
            import subprocess
            import time
            import os

            # Start cloudflared in background - remove nohup since Popen handles background execution
            # Just use cloudflared directly
            process = subprocess.Popen(
                ['cloudflared', 'tunnel', '--url', url],
                stdout=open(log_path, 'a'),
                stderr=open(log_path, 'a'),
                stdin=subprocess.DEVNULL,
                preexec_fn=os.setsid  # Create new session so child processes don't get killed with parent
            )

            # Wait briefly for process to start
            time.sleep(0.5)

            # If process died immediately, return error
            if process.poll() is not None:
                self.log_message.emit(f"Failed to start tunnel '{final_name}', cloudflared exited early")
                return False

            # Get the PID of the subprocess
            pid = process.pid

            # Save the PID to file
            pid_path = os.path.join(tunnels_dir, f"{final_name}.pid")
            with open(pid_path, 'w') as f:
                f.write(str(pid))

            # Verify that the process is actually running with this PID
            if self.is_process_running(pid):
                self.log_message.emit(f"Successfully started tunnel '{final_name}' with PID {pid}")
                self.tunnels_updated.emit(self.get_running_tunnels())
                return True
            else:
                # Clean up if process isn't running
                os.remove(pid_path)
                self.log_message.emit(f"Failed to start tunnel '{final_name}', process is not running")
                return False
        except FileNotFoundError:
            self.log_message.emit("cloudflared is not installed or not found in system PATH")
            # Clean up config file if start failed
            config_path = os.path.join(tunnels_dir, f"{final_name}.config")
            if os.path.exists(config_path):
                os.remove(config_path)
            return False
        except Exception as e:
            self.log_message.emit(f"Error starting tunnel: {str(e)}")
            # Clean up config file if start failed
            config_path = os.path.join(tunnels_dir, f"{final_name}.config")
            if os.path.exists(config_path):
                os.remove(config_path)
            return False

    def is_process_running_for_pid_file(self, pid_file):
        """Check if the process in a PID file is still running"""
        if not os.path.exists(pid_file):
            return False
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            return self.is_process_running(pid)
        except (ValueError, OSError):
            return False
    
    def stop_tunnel(self, tunnel_id):
        """Stop a specific tunnel"""
        tunnels_dir = os.path.expanduser("~/.cf-tunnels")
        pid_file = os.path.join(tunnels_dir, f"{tunnel_id}.pid")

        if not os.path.exists(pid_file):
            self.log_message.emit(f"Tunnel {tunnel_id} not found")
            return False

        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())

            # Check if process is still running
            if not self.is_process_running(pid):
                self.log_message.emit(f"Tunnel {tunnel_id} (PID: {pid}) is not running")
                # Clean up files
                os.remove(pid_file)
                config_file = os.path.join(tunnels_dir, f"{tunnel_id}.config")
                if os.path.exists(config_file):
                    os.remove(config_file)
                return True

            # Terminate the process gracefully first
            import signal
            try:
                os.kill(pid, signal.SIGTERM)  # Terminate gracefully first
            except ProcessLookupError:
                # Process doesn't exist anymore
                pass
            except PermissionError:
                self.log_message.emit(f"Permission denied to terminate process {pid}")
                return False

            # Wait a bit for graceful shutdown (up to 5 seconds)
            import time
            for _ in range(10):  # Check every 0.5 seconds for 5 seconds total
                if not self.is_process_running(pid):
                    break
                time.sleep(0.5)

            # Force kill if still running
            if self.is_process_running(pid):
                try:
                    os.kill(pid, signal.SIGKILL)  # Force kill if still running
                except ProcessLookupError:
                    # Process was terminated in the meantime
                    pass
                except PermissionError:
                    self.log_message.emit(f"Permission denied to kill process {pid}")
                    return False

            # Clean up files
            os.remove(pid_file)
            config_file = os.path.join(tunnels_dir, f"{tunnel_id}.config")
            if os.path.exists(config_file):
                os.remove(config_file)

            self.log_message.emit(f"Successfully stopped tunnel {tunnel_id}")
            self.tunnels_updated.emit(self.get_running_tunnels())
            return True

        except ValueError:
            # Invalid PID in file
            self.log_message.emit(f"Invalid PID in file for tunnel {tunnel_id}")
            os.remove(pid_file)
            return False
        except Exception as e:
            self.log_message.emit(f"Error stopping tunnel {tunnel_id}: {e}")
            return False
    
    def get_tunnel_logs(self, tunnel_id, lines=50):
        """Get logs for a specific tunnel"""
        logs_dir = os.path.expanduser("~/.cf-tunnels/logs")
        log_path = os.path.join(logs_dir, f"{tunnel_id}.log")
        
        if not os.path.exists(log_path):
            return f"Log file for tunnel {tunnel_id} does not exist"
        
        try:
            with open(log_path, 'r') as f:
                all_lines = f.readlines()
                # Get the last 'lines' lines
                last_lines = all_lines[-lines:] if len(all_lines) >= lines else all_lines
                return ''.join(last_lines)
        except Exception as e:
            return f"Error reading logs: {e}"
    
    def get_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class TunnelsTab(QWidget):
    def __init__(self, tunnel_manager):
        super().__init__()
        self.tunnel_manager = tunnel_manager
        self.init_ui()
        self.refresh_tunnels()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh Tunnels")
        self.refresh_btn.clicked.connect(self.refresh_tunnels)
        
        self.start_tunnel_btn = QPushButton("Start New Tunnel")
        self.start_tunnel_btn.clicked.connect(self.start_tunnel_dialog)
        
        self.stop_all_btn = QPushButton("Stop All Tunnels")
        self.stop_all_btn.clicked.connect(self.stop_all_tunnels)
        
        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addWidget(self.start_tunnel_btn)
        toolbar_layout.addWidget(self.stop_all_btn)
        toolbar_layout.addStretch()
        
        # Tunnels list
        self.tunnels_tree = QTreeWidget()
        self.tunnels_tree.setHeaderLabels(["Name", "Port", "Protocol", "PID", "Public URL", "Actions"])
        # Set context menu policy to CustomContextMenu for right-click menus
        from PySide6.QtCore import Qt
        self.tunnels_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Add to main layout
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.tunnels_tree)
        
    def refresh_tunnels(self):
        """Refresh the tunnels list"""
        tunnels = self.tunnel_manager.get_running_tunnels()

        # Clear the tree
        self.tunnels_tree.clear()

        # Add tunnels to the tree
        for tunnel in tunnels:
            item = QTreeWidgetItem([
                tunnel['name'],
                tunnel['port'],
                tunnel['protocol'],
                tunnel['pid'],
                tunnel['public_url'] if tunnel['public_url'] else "Initializing...",
                "STOP"  # Make the action more obvious
            ])
            item.setData(0, 50, tunnel['id'])  # Store tunnel ID in the item

            # Change the appearance of the STOP button to make it more obvious
            item.setBackground(5, QColor(220, 20, 60))  # Red background for STOP
            item.setForeground(5, QColor(255, 255, 255))  # White text

            # Make URL cell selectable for easy copying
            item.setFlags(item.flags() | 2)  # Make all cells selectable

            self.tunnels_tree.addTopLevelItem(item)
        # Only update content, don't re-register signals which were already set up in init

    def show_tunnel_context_menu(self, position):
        """Show context menu for tunnel items with copy URL option"""
        item = self.tunnels_tree.itemAt(position)
        if not item:
            return

        menu = QMenu()

        # Copy URL option
        tunnel_id = item.data(0, 50)
        if tunnel_id:
            # Find the tunnel to get its URL
            tunnels = self.tunnel_manager.get_running_tunnels()
            selected_tunnel = next((t for t in tunnels if t['id'] == tunnel_id), None)
            if selected_tunnel and selected_tunnel['public_url']:
                copy_url_action = QAction("Copy URL to Clipboard", self)
                copy_url_action.triggered.connect(lambda: QApplication.clipboard().setText(selected_tunnel['public_url']))
                menu.addAction(copy_url_action)

            # Stop tunnel option
            stop_action = QAction("Stop Tunnel", self)
            stop_action.triggered.connect(lambda: self.confirm_and_stop_tunnel(tunnel_id))
            menu.addAction(stop_action)

        # Show the menu
        menu.exec_(self.tunnels_tree.viewport().mapToGlobal(position))

    def confirm_and_stop_tunnel(self, tunnel_id):
        """Confirm and stop a tunnel from the context menu"""
        reply = QMessageBox.question(
            self, "Confirm Stop",
            f"Are you sure you want to stop tunnel '{tunnel_id}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success = self.tunnel_manager.stop_tunnel(tunnel_id)
            if success:
                QMessageBox.information(self, "Success", f"Stopped tunnel '{tunnel_id}'")
                self.refresh_tunnels()  # Refresh the view
            else:
                QMessageBox.critical(self, "Error", f"Failed to stop tunnel '{tunnel_id}'")

    def handle_tunnel_item_click(self, item, column):
        """Handle clicks on tunnel items, especially the 'Stop' button column"""
        if column == 5:  # The "Actions" column
            action_text = item.text(column)
            if action_text.upper() == "STOP":
                tunnel_id = item.data(0, 50)  # Get stored tunnel ID
                if tunnel_id:
                    reply = QMessageBox.question(
                        self, "Confirm Stop",
                        f"Are you sure you want to stop tunnel '{tunnel_id}'?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        success = self.tunnel_manager.stop_tunnel(tunnel_id)
                        if success:
                            QMessageBox.information(self, "Success", f"Stopped tunnel '{tunnel_id}'")
                            self.refresh_tunnels()  # Refresh the view
                        else:
                            QMessageBox.critical(self, "Error", f"Failed to stop tunnel '{tunnel_id}'")
    
    def start_tunnel_dialog(self):
        """Show dialog to start a new tunnel"""
        name, ok1 = QInputDialog.getText(self, "Start Tunnel", "Tunnel Name:", QLineEdit.Normal, "my-tunnel")
        if not ok1 or not name:
            return
            
        port, ok2 = QInputDialog.getInt(self, "Start Tunnel", "Port:", 3000, 1, 65535)
        if not ok2:
            return
            
        protocol, ok3 = QInputDialog.getItem(self, "Start Tunnel", "Protocol:", ["http", "https"], 0, False)
        if not ok3:
            return
        
        success = self.tunnel_manager.start_tunnel(name, port, protocol)
        if success:
            QMessageBox.information(self, "Success", f"Successfully started tunnel '{name}'")
            self.refresh_tunnels()
        else:
            QMessageBox.critical(self, "Error", f"Failed to start tunnel '{name}'")
    
    def stop_all_tunnels(self):
        """Stop all running tunnels"""
        tunnels = self.tunnel_manager.get_running_tunnels()
        stopped = 0
        for tunnel in tunnels:
            if self.tunnel_manager.stop_tunnel(tunnel['id']):
                stopped += 1

        QMessageBox.information(self, "Stop All", f"Stopped {stopped} tunnels")
        # Refresh the tunnels view after stopping all
        self.refresh_tunnels()


class LogsTab(QWidget):
    def __init__(self, tunnel_manager):
        super().__init__()
        self.tunnel_manager = tunnel_manager
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Log display area
        self.logs_display = QTextEdit()
        self.logs_display.setReadOnly(True)
        
        layout.addWidget(self.logs_display)


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Settings content
        settings_label = QLabel("Settings will be implemented here...")
        layout.addWidget(settings_label)


class TunnelManagerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.tunnel_manager = TunnelManager()
        
        # Connect signals
        self.tunnel_manager.tunnels_updated.connect(self.on_tunnels_updated)
        self.tunnel_manager.log_message.connect(self.on_log_message)
        
        self.init_ui()
        self.setup_system_tray()
        
    def init_ui(self):
        self.setWindowTitle("CF Tunnel Manager")
        self.setGeometry(100, 100, 1000, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create tabs
        self.tabs = QTabWidget()
        
        # Create widgets for each tab
        self.tunnels_tab = TunnelsTab(self.tunnel_manager)
        self.logs_tab = LogsTab(self.tunnel_manager)
        self.settings_tab = SettingsTab()
        
        # Add tabs
        self.tabs.addTab(self.tunnels_tab, "Tunnels")
        self.tabs.addTab(self.logs_tab, "Logs")  # This will be replaced with actual logs view
        self.tabs.addTab(self.settings_tab, "Settings")
        
        # Add to main layout
        main_layout.addWidget(self.tabs)
        
    def on_tunnels_updated(self, tunnels):
        """Called when tunnels list is updated"""
        # Update the tunnels tab
        self.tunnels_tab.refresh_tunnels()
    
    def on_log_message(self, message):
        """Called when a log message is received"""
        # Add to logs tab
        self.logs_tab.logs_display.append(f"[{self.get_timestamp()}] {message}")
    
    def get_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime('%H:%M:%S')
    
    def setup_system_tray(self):
        """Setup system tray icon and menu"""
        if QSystemTrayIcon.isSystemTrayAvailable():
            from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon

            # Create a simple icon programmatically
            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor(0, 100, 200))  # Blue background

            # Draw a simple tunnel-like shape
            painter = QPainter(pixmap)
            painter.setPen(QColor(255, 255, 255))
            painter.setBrush(QColor(255, 255, 255))
            # Draw a simple shape (rectangle for tunnel)
            painter.drawRect(8, 12, 16, 8)
            painter.end()

            tray_icon = QIcon(pixmap)
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setIcon(tray_icon)

            # Create the tray menu dynamically to show active tunnels
            self.update_tray_menu()

            # Update tray periodically
            self.tray_timer = QTimer()
            self.tray_timer.timeout.connect(self.update_tray_menu)
            self.tray_timer.start(10000)  # Update every 10 seconds

            # Show the tray icon
            self.tray_icon.show()

    def update_tray_menu(self):
        """Update the system tray menu with active tunnels"""
        # Create a new menu
        tray_menu = QMenu()

        # Add main actions
        show_action = QAction("Show CF Tunnel Manager", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        hide_action = QAction("Hide", self)
        hide_action.triggered.connect(self.hide_window)
        tray_menu.addAction(hide_action)

        tray_menu.addSeparator()

        start_action = QAction("Start New Tunnel", self)
        start_action.triggered.connect(self.start_new_tunnel)
        tray_menu.addAction(start_action)

        refresh_action = QAction("Refresh Tunnels", self)
        refresh_action.triggered.connect(self.refresh_tunnels_from_tray)
        tray_menu.addAction(refresh_action)

        # Show active tunnels with stop options
        tunnels = self.tunnel_manager.get_running_tunnels()
        if tunnels:
            tray_menu.addSeparator()
            tray_menu.addAction("Active Tunnels:").setEnabled(False)  # Header

            for tunnel in tunnels:
                tunnel_menu = tray_menu.addMenu(f"{tunnel['name']} ({tunnel['port']})")

                # Copy URL submenu item if URL is available
                if tunnel['public_url']:
                    copy_url_action = tunnel_menu.addAction("Copy URL")
                    copy_url_action.triggered.connect(
                        lambda url=tunnel['public_url']: QApplication.clipboard().setText(url)
                    )

                # Stop tunnel submenu item
                stop_action = tunnel_menu.addAction("Stop")
                stop_action.triggered.connect(
                    lambda checked=False, tid=tunnel['id']: self.confirm_and_stop_tunnel_from_tray(tid)
                )

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)

        # Update the tray icon menu
        if hasattr(self, 'tray_icon'):
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self.tray_icon_activated)

    def confirm_and_stop_tunnel_from_tray(self, tunnel_id):
        """Confirm and stop tunnel from tray menu"""
        reply = QMessageBox.question(
            self, "Confirm Stop",
            f"Are you sure you want to stop tunnel '{tunnel_id}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success = self.tunnel_manager.stop_tunnel(tunnel_id)
            if success:
                self.refresh_tunnels_from_tray()
            else:
                QMessageBox.critical(self, "Error", f"Failed to stop tunnel '{tunnel_id}'")

    def tray_icon_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def show_window(self):
        """Show the main window"""
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_window(self):
        """Hide the main window"""
        self.hide()

    def start_new_tunnel(self):
        """Start a new tunnel via tray"""
        self.show()
        self.tunnels_tab.start_tunnel_dialog()

    def refresh_tunnels_from_tray(self):
        """Refresh tunnels via tray"""
        self.tunnels_tab.refresh_tunnels()

    def quit_application(self):
        """Quit the application"""
        QApplication.quit()
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Optionally hide to tray instead of quitting
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CF Tunnel Manager")
    app.setApplicationVersion("1.0")
    
    window = TunnelManagerGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()