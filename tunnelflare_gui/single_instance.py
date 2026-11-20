"""One TunnelFlare per user: launching it again brings the running window forward."""
import getpass

from PySide6.QtNetwork import QLocalServer, QLocalSocket


def server_name():
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    return f"TunnelFlare-{user}"


def notify_running_instance(name=None, timeout_ms=500):
    """Ask an already running instance to show its window. True if one answered."""
    socket = QLocalSocket()
    socket.connectToServer(name or server_name())
    if not socket.waitForConnected(timeout_ms):
        return False
    socket.write(b"show\n")
    socket.flush()
    socket.waitForBytesWritten(timeout_ms)
    socket.disconnectFromServer()
    return True


def listen_for_activation(on_activate, parent, name=None):
    """Call on_activate() whenever a later launch asks this instance to show itself."""
    name = name or server_name()
    server = QLocalServer(parent)
    if not server.listen(name):
        # A crashed instance can leave its socket file behind (POSIX)
        QLocalServer.removeServer(name)
        server.listen(name)

    def accept():
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            connection.disconnected.connect(connection.deleteLater)
            on_activate()

    server.newConnection.connect(accept)
    return server
