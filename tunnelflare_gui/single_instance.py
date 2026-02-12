import sys
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

class SingleInstanceApp(QApplication):
    def __init__(self, argv, app_id):
        super().__init__(argv)
        self.app_id = app_id
        self.main_window = None

        # Try to connect to an existing server
        self.socket = QLocalSocket(self)
        self.socket.connectToServer(self.app_id)

        if self.socket.waitForConnected(500):
            # Another instance is running
            self.socket.write(b"show")
            self.socket.waitForBytesWritten(500)
            self.socket.disconnectFromServer()
            # Exit the new instance immediately
            sys.exit(0)

        # No other instance, start our own server
        self.server = QLocalServer(self)
        # Clean up any leftover socket file from a crash
        QLocalServer.removeServer(self.app_id)
        if not self.server.listen(self.app_id):
            # If it still fails, it might be a permissions issue or something else
            print(f"Warning: Could not start local server: {self.server.errorString()}")

        self.server.newConnection.connect(self._on_new_connection)

    def set_main_window(self, window):
        """Register the main window to be shown when a new instance starts."""
        self.main_window = window

    def _on_new_connection(self):
        socket = self.server.nextPendingConnection()
        if not socket:
            return

        if socket.waitForReadyRead(500):
            try:
                data = socket.readAll().data().decode('utf-8')
                if data == "show":
                    self._activate_window()
            except Exception as e:
                print(f"Error reading from local socket: {e}")

        socket.disconnectFromServer()

    def _activate_window(self):
        if self.main_window:
            # If minimized, restore it
            if self.main_window.isMinimized():
                self.main_window.showNormal()

            # Show the window if it's hidden (e.g., in tray)
            self.main_window.show()

            # Bring it to front
            self.main_window.activateWindow()
            self.main_window.raise_()
