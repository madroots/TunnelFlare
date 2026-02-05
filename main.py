import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
import signal

def main():
    app = QApplication(sys.argv)
    
    # Allow headers/fonts to look better on high DPI
    # QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling) # PySide6 handles this mostly

    window = MainWindow()
    window.show()
    
    # Handle Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
