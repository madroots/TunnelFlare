from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel
from PySide6.QtCore import QTimer, Qt
import os

class LogViewerDialog(QDialog):
    def __init__(self, log_path, parent=None):
        super().__init__(parent)
        self.log_path = log_path
        self.setWindowTitle(f"Logs: {os.path.basename(log_path)}")
        self.resize(700, 500)
        self.setup_ui()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_logs)
        self.timer.start(2000) # Refresh every 2 seconds
        
        self.refresh_logs()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)
        
        btn_layout = QHBoxLayout()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def refresh_logs(self):
        if not os.path.exists(self.log_path):
            self.text_area.setText("Log file not found.")
            return

        try:
            with open(self.log_path, 'r') as f:
                content = f.read()
                # Maintain scroll position if user is reading up?
                # Simple implementation: just set text.
                # Optimized: only append new text. For now simple.
                
                # Check if we should scroll to bottom (if we were already at bottom)
                scrollbar = self.text_area.verticalScrollBar()
                was_at_bottom = scrollbar.value() == scrollbar.maximum()
                
                self.text_area.setText(content)
                
                if was_at_bottom:
                    scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            self.text_area.setText(f"Error reading logs: {str(e)}")
