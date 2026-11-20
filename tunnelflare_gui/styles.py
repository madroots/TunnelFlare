from .resources import RESOURCE_DIR

# Checkbox tick, referenced by absolute path (works in source and frozen builds)
CHECK_ICON = (RESOURCE_DIR / "check.svg").as_posix()


class Styles:
    THEME = {
        "bg": "#141414",
        "card": "#1c1c1c",
        "card_hover": "#212121",
        "card_inner": "#171717",
        "text_main": "#f5f5f7",
        "text_sub": "#9aa0a6",
        "text_dim": "#6e747b",
        "accent": "#ff8a00",
        "accent_hover": "#ff9d26",
        "accent_pressed": "#e67c00",
        "online": "#19c37d",
        "starting": "#f5a524",
        "danger": "#ff453a",
        "offline": "#4a4a4c",
        "port": "#7d8691",
    }
    T = THEME

    # Focus rings follow the keyboard only: widgets get focusVisible=true when focus
    # arrives by Tab or a shortcut (see focus.py), never from a mouse click.
    STYLESHEET = f"""
    QMainWindow, QDialog, QStackedWidget {{
        background-color: {T["bg"]};
        color: {T["text_main"]};
    }}
    QWidget {{
        color: {T["text_main"]};
        font-family: "Inter";
    }}
    QLabel {{
        background: transparent;
    }}
    QToolTip {{
        background-color: #262626;
        color: {T["text_main"]};
        border: 1px solid rgba(255, 255, 255, 0.10);
        padding: 5px 8px;
        font-size: 12px;
    }}

    QScrollArea {{
        border: none;
        background-color: transparent;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}
    /* Slim scrollbars: a thin rounded thumb, no track, no arrow buttons */
    QScrollBar:vertical {{
        background: transparent;
        border: none;
        width: 10px;
        margin: 0;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        border: none;
        height: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(255, 255, 255, 0.16);
        border-radius: 3px;
        min-height: 40px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: rgba(255, 255, 255, 0.16);
        border-radius: 3px;
        min-width: 40px;
        margin: 2px;
    }}
    QScrollBar::handle:hover {{
        background: rgba(255, 255, 255, 0.28);
    }}
    QScrollBar::handle:pressed {{
        background: rgba(255, 255, 255, 0.40);
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        width: 0;
        height: 0;
        border: none;
        background: none;
    }}
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: none;
    }}

    /* Page headers */
    QLabel#AppTitle {{
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.6px;
    }}
    QLabel#AppSubtitle {{
        font-size: 13px;
        color: {T["text_sub"]};
    }}
    QLabel#DetailTitle {{
        font-size: 24px;
        font-weight: 700;
        letter-spacing: -0.4px;
    }}

    /* Buttons */
    QPushButton {{
        background-color: #202020;
        color: {T["text_main"]};
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 10px 16px;
        font-size: 13px;
        font-weight: 600;
        outline: none;
    }}
    QPushButton:hover {{
        background-color: #272727;
        border-color: rgba(255, 255, 255, 0.14);
    }}
    QPushButton:pressed {{
        background-color: #1a1a1a;
    }}
    QPushButton:disabled {{
        background-color: #1a1a1a;
        color: rgba(255, 255, 255, 0.26);
        border-color: rgba(255, 255, 255, 0.04);
    }}
    QPushButton[focusVisible="true"] {{
        border: 1px solid rgba(255, 138, 0, 0.85);
    }}

    QPushButton#PrimaryAction {{
        background-color: {T["accent"]};
        color: #ffffff;
        border: 1px solid {T["accent"]};
    }}
    QPushButton#PrimaryAction:hover {{
        background-color: {T["accent_hover"]};
        border-color: {T["accent_hover"]};
    }}
    QPushButton#PrimaryAction:pressed {{
        background-color: {T["accent_pressed"]};
        border-color: {T["accent_pressed"]};
    }}
    QPushButton#PrimaryAction:disabled {{
        background-color: rgba(255, 138, 0, 0.30);
        border-color: rgba(255, 138, 0, 0.0);
        color: rgba(255, 255, 255, 0.70);
    }}
    QPushButton#PrimaryAction[focusVisible="true"] {{
        border: 1px solid #ffffff;
    }}

    QPushButton#DestructiveButton {{
        background-color: rgba(255, 69, 58, 0.10);
        color: {T["danger"]};
        border: 1px solid rgba(255, 69, 58, 0.22);
    }}
    QPushButton#DestructiveButton:hover {{
        background-color: rgba(255, 69, 58, 0.17);
        border-color: rgba(255, 69, 58, 0.38);
    }}
    QPushButton#DestructiveButton:pressed {{
        background-color: rgba(255, 69, 58, 0.24);
    }}
    QPushButton#DestructiveButton:disabled {{
        background-color: rgba(255, 69, 58, 0.05);
        color: rgba(255, 69, 58, 0.45);
        border-color: rgba(255, 69, 58, 0.10);
    }}
    QPushButton#DestructiveButton[focusVisible="true"] {{
        border: 1px solid {T["danger"]};
    }}

    /* Text-only accent button ("‹ Tunnels", "Copy") */
    QPushButton#GhostButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        color: {T["accent"]};
        font-size: 14px;
        font-weight: 600;
        padding: 4px 6px;
    }}
    QPushButton#GhostButton:hover {{
        color: {T["accent_hover"]};
        background-color: rgba(255, 138, 0, 0.08);
    }}
    QPushButton#GhostButton:pressed {{
        background-color: rgba(255, 138, 0, 0.14);
    }}
    QPushButton#GhostButton:disabled {{
        color: rgba(255, 255, 255, 0.26);
        background: transparent;
    }}
    QPushButton#GhostButton[focusVisible="true"] {{
        border: 1px solid rgba(255, 138, 0, 0.85);
    }}
    QPushButton#SmallGhostButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 7px;
        color: {T["text_sub"]};
        font-size: 12px;
        font-weight: 600;
        padding: 2px 8px;
    }}
    QPushButton#SmallGhostButton:hover {{
        color: {T["text_main"]};
        background-color: rgba(255, 255, 255, 0.07);
    }}
    QPushButton#SmallGhostButton[focusVisible="true"] {{
        border: 1px solid rgba(255, 138, 0, 0.85);
    }}

    /* Round icon buttons (edit, delete, dismiss) */
    QPushButton#IconButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 17px;
        padding: 0;
    }}
    QPushButton#IconButton:hover {{
        background-color: rgba(255, 255, 255, 0.08);
    }}
    QPushButton#IconButton:pressed {{
        background-color: rgba(255, 255, 255, 0.13);
    }}
    QPushButton#IconButton:disabled {{
        background: transparent;
    }}
    QPushButton#IconButton[focusVisible="true"] {{
        border: 1px solid rgba(255, 138, 0, 0.85);
    }}

    QPushButton#AddButton {{
        background-color: {T["accent"]};
        border: 1px solid {T["accent"]};
        border-radius: 20px;
        padding: 0;
    }}
    QPushButton#AddButton:hover {{
        background-color: {T["accent_hover"]};
        border-color: {T["accent_hover"]};
    }}
    QPushButton#AddButton:pressed {{
        background-color: {T["accent_pressed"]};
        border-color: {T["accent_pressed"]};
    }}
    QPushButton#AddButton[focusVisible="true"] {{
        border: 1px solid #ffffff;
    }}

    /* Tunnel cards */
    QFrame#TunnelCard {{
        background-color: {T["card"]};
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 18px;
        outline: none;
    }}
    QFrame#TunnelCard:hover {{
        background-color: {T["card_hover"]};
        border-color: rgba(255, 255, 255, 0.10);
    }}
    QFrame#TunnelCard[focusVisible="true"] {{
        border: 1px solid rgba(255, 138, 0, 0.85);
    }}
    QLabel#CardTitle {{
        font-size: 16px;
        font-weight: 600;
    }}
    QLabel#MetaText {{
        font-size: 12px;
        color: {T["text_sub"]};
    }}
    QLabel#StatusOnline, QLabel#StatusStarting, QLabel#StatusStopped {{
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#StatusOnline {{
        color: {T["online"]};
    }}
    QLabel#StatusStarting {{
        color: {T["starting"]};
    }}
    QLabel#StatusStopped {{
        color: {T["text_dim"]};
    }}
    QLabel#Chip {{
        background-color: rgba(255, 255, 255, 0.07);
        color: {T["text_sub"]};
        border-radius: 5px;
        padding: 1px 6px;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.4px;
    }}

    /* Public link: pill on cards, panel on the details page */
    QFrame#LinkPill, QFrame#LinkPanel {{
        background-color: {T["card_inner"]};
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 10px;
    }}
    QFrame#LinkPanel {{
        border-radius: 14px;
    }}
    QFrame#LinkPill:hover, QFrame#LinkPanel[copyable="true"]:hover {{
        border-color: rgba(255, 138, 0, 0.45);
        background-color: #1a1612;
    }}
    QLabel#LinkText {{
        font-family: "JetBrains Mono";
        font-size: 12px;
        color: {T["accent"]};
    }}
    QLabel#LinkTextLarge {{
        font-family: "JetBrains Mono";
        font-size: 13px;
        color: {T["accent"]};
    }}
    QLabel#LinkPlaceholder {{
        font-size: 13px;
        color: {T["text_dim"]};
    }}
    QLabel#SectionLabel {{
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        color: {T["text_dim"]};
    }}

    /* Inputs */
    QLineEdit {{
        background-color: #1a1a1a;
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 12px;
        padding: 11px 14px;
        font-size: 14px;
        color: {T["text_main"]};
        selection-background-color: {T["accent"]};
    }}
    QLineEdit:hover {{
        border-color: rgba(255, 255, 255, 0.16);
    }}
    QLineEdit:focus {{
        border: 1px solid {T["accent"]};
        background-color: #1d1d1d;
    }}
    QLineEdit[invalid="true"] {{
        border: 1px solid rgba(255, 69, 58, 0.85);
    }}
    QLabel#FieldLabel {{
        font-size: 12px;
        font-weight: 600;
        color: {T["text_sub"]};
    }}
    QLabel#FieldError {{
        font-size: 12px;
        color: {T["danger"]};
    }}
    QLabel#FieldHint {{
        font-size: 12px;
        color: {T["text_dim"]};
    }}
    QLabel#FieldHintOk {{
        font-size: 12px;
        color: {T["online"]};
    }}

    QCheckBox {{
        spacing: 10px;
        font-size: 13px;
        color: {T["text_main"]};
        outline: none;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 5px;
        border: 1px solid rgba(255, 255, 255, 0.28);
        background-color: #1a1a1a;
    }}
    QCheckBox::indicator:hover {{
        border-color: {T["accent"]};
    }}
    QCheckBox::indicator:checked {{
        background-color: {T["accent"]};
        border-color: {T["accent"]};
        image: url("{CHECK_ICON}");
    }}
    QCheckBox[focusVisible="true"]::indicator {{
        border: 1px solid #ffffff;
    }}
    QLabel#HintLabel {{
        color: {T["text_dim"]};
        font-size: 12px;
    }}

    /* Logs */
    QPlainTextEdit {{
        background-color: #0f0f0f;
        color: #c9c9c9;
        font-family: "JetBrains Mono";
        font-size: 12px;
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.06);
        padding: 10px 12px;
        selection-background-color: rgba(255, 138, 0, 0.45);
    }}

    /* Empty state */
    QLabel#EmptyTitle {{
        font-size: 18px;
        font-weight: 600;
    }}
    QLabel#EmptyText {{
        font-size: 13px;
        color: {T["text_sub"]};
    }}

    /* Dialogs */
    QLabel#DialogTitle {{
        font-size: 19px;
        font-weight: 700;
        letter-spacing: -0.2px;
    }}
    QLabel#DialogText {{
        font-size: 13px;
        color: {T["text_sub"]};
    }}
    QLabel#IconBadge_warning {{
        background-color: rgba(245, 165, 36, 0.14);
        border-radius: 22px;
    }}
    QLabel#IconBadge_error, QLabel#IconBadge_danger {{
        background-color: rgba(255, 69, 58, 0.14);
        border-radius: 22px;
    }}
    QLabel#IconBadge_update, QLabel#IconBadge_info {{
        background-color: rgba(255, 138, 0, 0.14);
        border-radius: 22px;
    }}
    QFrame#QrTile {{
        background-color: #ffffff;
        border-radius: 18px;
    }}
    QLabel#QrCaption {{
        font-family: "JetBrains Mono";
        font-size: 12px;
        color: {T["text_sub"]};
    }}
    QProgressBar#UpdateProgress {{
        background-color: rgba(255, 255, 255, 0.08);
        border: none;
        border-radius: 3px;
        min-height: 6px;
        max-height: 6px;
    }}
    QProgressBar#UpdateProgress::chunk {{
        background-color: {T["accent"]};
        border-radius: 3px;
    }}

    /* Confirmation toast */
    QLabel#Toast {{
        background-color: #2c2c2e;
        color: {T["text_main"]};
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 16px;
        padding: 7px 16px;
        font-size: 13px;
        font-weight: 600;
    }}

    /* Update banner */
    QFrame#UpdateBanner {{
        background-color: rgba(255, 138, 0, 0.09);
        border: 1px solid rgba(255, 138, 0, 0.30);
        border-radius: 14px;
    }}
    QLabel#UpdateText {{
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton#BannerAction {{
        background-color: {T["accent"]};
        color: #ffffff;
        border: 1px solid {T["accent"]};
        border-radius: 9px;
        padding: 5px 12px;
        font-size: 12px;
    }}
    QPushButton#BannerAction:hover {{
        background-color: {T["accent_hover"]};
        border-color: {T["accent_hover"]};
    }}
    QPushButton#BannerAction[focusVisible="true"] {{
        border: 1px solid #ffffff;
    }}
    QLabel#IconBadge_success {{
        background-color: rgba(25, 195, 125, 0.14);
        border-radius: 22px;
    }}

    /* Tray menu (Windows and Linux; macOS draws its own) */
    QMenu {{
        background-color: #1e1e1e;
        color: {T["text_main"]};
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 7px 22px;
        border-radius: 6px;
        margin: 1px 4px;
    }}
    QMenu::item:selected {{
        background-color: {T["accent"]};
        color: #ffffff;
    }}
    QMenu::item:disabled {{
        color: {T["text_dim"]};
    }}
    QMenu::separator {{
        height: 1px;
        background: rgba(255, 255, 255, 0.10);
        margin: 4px 8px;
    }}
    """
