import sys
from tunnelflare_gui.single_instance import SingleInstanceApp
from tunnelflare_gui.main_window import MainWindow
from tunnelflare_gui.styles import Styles
import signal

def setup_bundled_path():
    import os
    import sys
    
    # Handle PyInstaller (Windows)
    if hasattr(sys, '_MEIPASS'):
        os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ['PATH']
    
    # Handle AppImage (Linux)
    # The AppRun script usually handles this, but let's be safe.
    appdir = os.environ.get('APPDIR')
    if appdir:
        bundled_bin = os.path.join(appdir, 'usr', 'bin')
        os.environ['PATH'] = bundled_bin + os.pathsep + os.environ['PATH']

def main():
    setup_bundled_path()
    app = SingleInstanceApp(sys.argv, "TunnelFlare_Main_App")
    app.setStyleSheet(Styles.STYLESHEET)
    # Allow headers/fonts to look better on high DPI
    # QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling) # PySide6 handles this mostly

    window = MainWindow()
    app.set_main_window(window)
    window.show()
    
    # Handle Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
