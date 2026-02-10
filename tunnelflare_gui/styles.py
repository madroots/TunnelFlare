
class Styles:
    # Theme Configuration
    THEME = {
        "bg": "#141414",
        "card": "#1f1f1f",
        "card_inner": "#191919",
        "text_main": "#ffffff",
        "text_sub": "#9aa0a6",
        "accent": "#ff8a00",
        "online": "#19c37d",
        "starting": "#f1c40f",
        "offline": "#3a3a3a",
        "port": "#7d8691"
    }

    STYLESHEET = f"""
    /* Base Windows and Dialogs */
    QMainWindow, QDialog, QStackedWidget {{
        background-color: {THEME["bg"]};
        color: {THEME["text_main"]};
    }}

    QWidget {{
        color: {THEME["text_main"]};
        font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    
    QScrollArea {{ 
        border: none; 
        background-color: transparent; 
    }}
    QScrollArea > QWidget > QWidget {{ 
        background-color: transparent; 
    }}

    /* Header Styling */
    QLabel#AppTitle {{
        font-size: 34px;
        font-weight: 700;
        letter-spacing: -1px;
        color: {THEME["text_main"]};
        background: transparent;
        padding: 0;
        margin: 0;
    }}
    QLabel#AppSubtitle {{
        font-size: 16px;
        color: {THEME["text_sub"]};
        background: transparent;
        padding: 0;
        margin: 0;
    }}

    /* Back Button (iOS Style) */
    QPushButton#BackButton {{
        background: transparent;
        border: none;
        color: {THEME["accent"]};
        font-size: 18px;
        font-weight: 500;
        padding: 0;
    }}
    QPushButton#BackButton:hover {{
        color: #ff9d26;
    }}

    /* Add Button */
    QPushButton#AddButton {{
        background-color: {THEME["accent"]};
        color: white;
        font-size: 32px; /* Bigger + */
        font-weight: 400;
        border-radius: 23px;
        border: none;
    }}
    QPushButton#AddButton:hover {{
        background-color: #ff9d26;
    }}

    /* Premium Action Buttons */
    QPushButton {{
        background-color: {THEME["card"]};
        color: {THEME["text_main"]};
        border-radius: 12px;
        padding: 12px 20px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: #2a2a2a;
        border-color: rgba(255, 255, 255, 0.15);
    }}
    
    QPushButton#PrimaryAction {{
        background-color: {THEME["accent"]};
        color: white;
        border: none;
    }}
    QPushButton#PrimaryAction:hover {{
        background-color: #ff9d26;
    }}

    /* Card Styling */
    QFrame#TunnelCard {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #232323, stop:1 #1c1c1c);
        border-radius: 22px;
        border: 1px solid rgba(255, 255, 255, 0.04);
    }}
    
    QFrame#TunnelCard[offline="true"] {{
        opacity: 0.5;
    }}

    QLabel#CardTitle {{
        font-size: 21px;
        font-weight: 600;
        color: {THEME["text_main"]};
        background: transparent;
    }}

    QLabel#PortLabel {{
        font-size: 13px;
        letter-spacing: 0.8px;
        color: {THEME["port"]};
        font-weight: 700;
        background: transparent;
    }}

    /* Badges */
    QLabel#BadgeOnline {{
        background: rgba(25, 195, 125, 30);
        color: {THEME["online"]};
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 800;
    }}
    QLabel#BadgeStarting {{
        background: rgba(241, 196, 15, 30);
        color: {THEME["starting"]};
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 800;
    }}
    QLabel#BadgeOffline {{
        background: #2a2a2a;
        color: #777777;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 800;
    }}

    /* Status Dot */
    QLabel#StatusDot, QLabel#StatusDotOffline, QLabel#StatusDotStarting {{
        min-width: 10px;
        max-width: 10px;
        min-height: 10px;
        max-height: 10px;
        border-radius: 5px;
    }}
    QLabel#StatusDot {{
        background: {THEME["online"]};
    }}
    QLabel#StatusDotStarting {{
        background: {THEME["starting"]};
    }}
    QLabel#StatusDotOffline {{
        background: #333333;
        border: 1px solid rgba(255,255,255,0.05);
    }}

    /* Buttons (Destructive) */
    QPushButton#DestructiveButton {{
        background-color: rgba(255, 45, 85, 0.08); /* Muted red background */
        color: #ff453a; /* Subtle red text */
        border: 1px solid rgba(255, 69, 58, 0.15);
    }}
    QPushButton#DestructiveButton:hover {{
        background-color: rgba(255, 45, 85, 0.15);
        border-color: rgba(255, 69, 58, 0.3);
    }}

    /* URL Section */
    QLabel#SectionLabel {{
        font-size: 11px;
        font-weight: 800;
        color: {THEME["text_sub"]};
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: -4px;
    }}

    QFrame#UrlInner {{
        background-color: {THEME["card_inner"]};
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }}
    
    QLabel#UrlText {{
        font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 13px;
        color: {THEME["accent"]};
        background: transparent;
    }}

    /* Inputs */
    QLineEdit {{
        background-color: #1a1a1a;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 14px 18px;
        color: {THEME["text_main"]};
        selection-background-color: {THEME["accent"]};
    }}
    QLineEdit:focus {{
        border: 1px solid {THEME["accent"]};
        background-color: #1e1e1e;
    }}

    /* Logs Area */
    QPlainTextEdit {{
        background-color: #0d0d0d;
        color: #cccccc;
        font-family: 'JetBrains Mono', Consolas, monospace;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        padding: 14px;
        font-size: 12px;
    }}
    """
