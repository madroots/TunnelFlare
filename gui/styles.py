
class Styles:
    # Theme Configuration
    THEME = {
        "bg_dark": "#0F172A",      # Main Window
        "bg_card": "#1E293B",      # Tunnel Row/Card
        "accent_orange": "#F38020", # Primary Buttons
        "accent_blue": "#0597F2",   # Info/Active Status
        "status_live": "#10B981",   # "Tunnel Online"
        "status_dead": "#EF4444",
        "text_main": "#F8FAFC",     # Primary White
        "text_dim": "#94A3B8"       # Secondary/Muted Text
    }

    STYLESHEET = f"""
    QMainWindow {{
        background-color: {THEME["bg_dark"]};
    }}
    QWidget {{
        color: {THEME["text_main"]};
        font-family: 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
        font-size: 14px;
        background-color: transparent; /* Default transparent for custom painting */
    }}
    
    QScrollArea {{ border: none; background-color: transparent; }}
    QScrollArea > QWidget > QWidget {{ background-color: transparent; }}

    /* List Item / Row */
    QFrame#TunnelRow {{
        background-color: {THEME["bg_card"]};
        border-radius: 10px;
        border: 1px solid #334155;
    }}
    QFrame#TunnelRow:hover {{
        border: 1px solid {THEME["accent_orange"]};
    }}

    /* Buttons */
    QPushButton#PrimaryButton {{
        background-color: {THEME["accent_orange"]};
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 10px 16px;
        font-size: 14px;
        border: none;
    }}
    QPushButton#PrimaryButton:hover {{
        background-color: #ff9540;
    }}
    QPushButton#PrimaryButton:disabled {{
        background-color: #475569;
        color: {THEME["text_dim"]};
    }}

    QPushButton#IconButton {{
        background-color: {THEME["bg_card"]};
        border-radius: 6px;
        border: 1px solid #334155;
        padding: 6px;
    }}
    QPushButton#IconButton:hover {{
        border-color: {THEME["accent_blue"]};
    }}

     QPushButton#DestructiveButton {{
        background-color: transparent;
        color: {THEME["status_dead"]};
        border: 1px solid {THEME["status_dead"]};
        border-radius: 8px;
        padding: 8px;
    }}
     QPushButton#DestructiveButton:hover {{
        background-color: {THEME["status_dead"]};
        color: white;
    }}
    
    /* Inputs */
    QLineEdit {{
        background-color: {THEME["bg_card"]};
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 10px;
        color: {THEME["text_main"]};
        selection-background-color: {THEME["accent_blue"]};
    }}
    QLineEdit:focus {{
        border: 1px solid {THEME["accent_blue"]};
    }}

    /* Labels */
    QLabel#Title {{
        font-size: 24px;
        font-weight: bold;
        color: {THEME["text_main"]};
    }}
    QLabel#Subtitle {{
        font-size: 18px;
        font-weight: 600;
        color: {THEME["text_dim"]};
    }}
    QLabel#UrlDisplay {{
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        color: {THEME["accent_blue"]};
        background-color: #0F172A; /* Bit darker */
        padding: 8px;
        border-radius: 6px;
        border: 1px dashed #334155;
    }}
    
    /* Logs */
    QPlainTextEdit {{
        background-color: #0b1120;
        color: #94a3b8;
        font-family: 'Consolas', 'Monospace';
        border-radius: 8px;
        border: 1px solid #334155;
        padding: 8px;
    }}
    """
