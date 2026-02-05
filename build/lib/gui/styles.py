
class Styles:
    DARK_BG = "#1e1e2e"
    DARKER_BG = "#181825"
    LIGHT_TEXT = "#cdd6f4"
    ACCENT = "#89b4fa"
    ACCENT_HOVER = "#b4befe"
    SUCCESS = "#a6e3a1"
    ERROR = "#f38ba8"
    WARNING = "#f9e2af"
    SECONDARY_BG = "#313244"
    BORDER = "#45475a"

    STYLESHEET = f"""
    QMainWindow {{
        background-color: {DARK_BG};
    }}
    QWidget {{
        color: {LIGHT_TEXT};
        font-family: 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
        font-size: 14px;
    }}
    
    /* Scroll Area */
    QScrollArea {{
        border: none;
        background-color: transparent;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}
    QScrollBar:vertical {{
        border: none;
        background: {DARKER_BG};
        width: 10px;
        margin: 0px 0px 0px 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {SECONDARY_BG};
        min-height: 20px;
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        border: none;
        background: none;
    }}

    /* Buttons */
    QPushButton {{
        background-color: {SECONDARY_BG};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 8px 16px;
        color: {LIGHT_TEXT};
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {BORDER};
        border-color: {ACCENT};
    }}
    QPushButton:pressed {{
        background-color: {DARKER_BG};
    }}
    QPushButton#PrimaryButton {{
        background-color: {ACCENT};
        color: {DARKER_BG};
        font-weight: bold;
        border: 1px solid {ACCENT};
    }}
    QPushButton#PrimaryButton:hover {{
        background-color: {ACCENT_HOVER};
        border-color: {ACCENT_HOVER};
    }}
    QPushButton#DestructiveButton {{
        background-color: transparent;
        border: 1px solid {ERROR};
        color: {ERROR};
    }}
    QPushButton#DestructiveButton:hover {{
        background-color: {ERROR};
        color: {DARKER_BG};
    }}
    QPushButton#LinkButton {{
        background-color: transparent;
        border: none;
        color: {ACCENT};
        text-align: left;
        padding: 0;
    }}
    QPushButton#LinkButton:hover {{
        text-decoration: underline;
    }}

    /* Cards */
    QFrame#Card {{
        background-color: {SECONDARY_BG};
        border-radius: 12px;
        border: 1px solid {BORDER};
    }}
    QFrame#Sidebar {{
        background-color: {DARKER_BG};
        border-right: 1px solid {BORDER};
    }}
    
    /* Inputs */
    QLineEdit, QComboBox {{
        background-color: {DARKER_BG};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 8px;
        color: {LIGHT_TEXT};
        selection-background-color: {ACCENT};
        selection-color: {DARKER_BG};
    }}
    QLineEdit:focus, QComboBox:focus {{
        border: 1px solid {ACCENT};
    }}

    /* Labels */
    QLabel#Title {{
        font-size: 24px;
        font-weight: bold;
        color: {ACCENT};
    }}
    QLabel#Subtitle {{
        font-size: 18px;
        font-weight: 600;
        color: {LIGHT_TEXT};
    }}
    QLabel#StatusRunning {{
        color: {SUCCESS};
        font-weight: bold;
    }}
    QLabel#StatusInitializing {{
        color: {WARNING};
        font-weight: bold;
    }}
    QLabel#StatusStopped {{
        color: {ERROR};
        font-weight: bold;
    }}
    """
