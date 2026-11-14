"""Design tokens and QSS matching the approved mockups."""

from __future__ import annotations

TOKENS = {
    "window_bg": "#F7F4EE",
    "title_bar": "#F3EFE8",
    "hairline": "#DCD6CC",
    "text": "#2B2926",
    "muted": "#7A746C",
    "faint": "#9A948C",
    "card": "#FFFCF7",
    "mat": "#E8E2D8",
    "placeholder": "#F0ECE5",
    "accent": "#B5522A",
    "accent_hover": "#9E4623",
    "accent_press": "#8A3D1F",
    "outline": "#C9C2B6",
    "logo_teal": "#5C7A94",
    "logo_gold": "#C49646",
    "pass_bg": "#E6EEE8",
    "pass_icon": "#467A56",
    "fail_bg": "#F5E8E0",
    "review_bg": "#F3EEE6",
    "status_bg": "#ECE2D6",
    "shadow": "#C8C0B4",
    "dash": "#C9C2B6",
}

WINDOW_RADIUS = 16
CARD_RADIUS = 18
BUTTON_RADIUS = 18
PILL_RADIUS = 24
DROP_RADIUS = 22
IMAGE_RADIUS = 16

FONT_FAMILY = '"Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", "Source Han Sans SC", "Noto Sans SC", sans-serif'


def stylesheet() -> str:
    t = TOKENS
    return f"""
* {{
    font-family: {FONT_FAMILY};
    color: {t["text"]};
}}
QWidget#RootWindow, QWidget#Chrome {{
    background: transparent;
}}
QWidget#Canvas {{
    background-color: {t["window_bg"]};
    border: 1px solid {t["hairline"]};
    border-radius: {WINDOW_RADIUS}px;
}}
QWidget#TitleBar {{
    background-color: {t["title_bar"]};
    border: none;
}}
QLabel#TitleText {{
    color: {t["text"]};
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.5px;
    background: transparent;
}}
QLabel#MutedLabel, QLabel#PanelCaption {{
    color: {t["muted"]};
    font-size: 13px;
    background: transparent;
}}
QLabel#FaintLabel {{
    color: {t["faint"]};
    font-size: 12px;
    background: transparent;
}}
QLabel#FooterHint {{
    color: {t["muted"]};
    font-size: 13px;
    background: transparent;
}}
QLabel#OfflineHint {{
    color: {t["muted"]};
    font-size: 13px;
    background: transparent;
}}
QPushButton#ToolbarButton {{
    background-color: {t["card"]};
    color: {t["text"]};
    border: 1px solid {t["outline"]};
    border-radius: {BUTTON_RADIUS}px;
    padding: 6px 16px;
    font-size: 13px;
    min-height: 34px;
}}
QPushButton#ToolbarButton:hover:!disabled {{
    background-color: #FFFEFB;
    border-color: #B9B1A6;
}}
QPushButton#ToolbarButton:disabled {{
    color: {t["faint"]};
    background-color: {t["card"]};
    border-color: {t["outline"]};
}}
QPushButton#ToolbarButton[highlight="true"] {{
    border: 1.6px solid {t["accent"]};
    color: {t["accent"]};
}}
QPushButton#PrimaryButton {{
    background-color: {t["accent"]};
    color: #FFFFFF;
    border: none;
    border-radius: {PILL_RADIUS}px;
    padding: 12px 22px;
    font-size: 14px;
    font-weight: 600;
    min-width: 128px;
    min-height: 48px;
}}
QPushButton#PrimaryButton:hover:!disabled {{
    background-color: {t["accent_hover"]};
}}
QPushButton#PrimaryButton:pressed {{
    background-color: {t["accent_press"]};
}}
QPushButton#PrimaryButton:disabled {{
    background-color: {t["mat"]};
    color: {t["faint"]};
}}
QPushButton#BusyPill {{
    background-color: {t["mat"]};
    color: {t["muted"]};
    border: none;
    border-radius: {PILL_RADIUS}px;
    padding: 12px 22px;
    font-size: 14px;
    min-width: 128px;
    min-height: 48px;
}}
QPushButton#GhostButton {{
    background-color: {t["card"]};
    color: {t["text"]};
    border: 1px solid {t["outline"]};
    border-radius: {BUTTON_RADIUS}px;
    padding: 6px 18px;
    font-size: 13px;
    min-height: 34px;
    min-width: 88px;
}}
QPushButton#GhostButton:hover:!disabled {{
    border-color: #B9B1A6;
}}
QPushButton#AccentButton {{
    background-color: {t["accent"]};
    color: #FFFFFF;
    border: none;
    border-radius: {BUTTON_RADIUS}px;
    padding: 6px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 34px;
    min-width: 88px;
}}
QPushButton#AccentButton:hover {{
    background-color: {t["accent_hover"]};
}}
QPushButton#DropCta {{
    background-color: {t["accent"]};
    color: #FFFFFF;
    border: none;
    border-radius: {BUTTON_RADIUS}px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 36px;
}}
QPushButton#DropCta:hover {{
    background-color: {t["accent_hover"]};
}}
QPushButton#CaptionButton {{
    background: transparent;
    border: none;
    color: {t["muted"]};
    font-size: 11px;
    min-width: 46px;
    max-width: 46px;
    min-height: 36px;
    border-radius: 0;
    padding: 0;
}}
QPushButton#CaptionButton:hover {{
    background-color: rgba(0, 0, 0, 0.06);
}}
QPushButton#CaptionClose:hover {{
    background-color: #E81123;
    color: #FFFFFF;
}}
QLabel#Banner {{
    background-color: #F3E6DC;
    color: {t["text"]};
    border: 1px solid #E2C8B8;
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 13px;
}}
QFrame#Hairline {{
    background-color: {t["hairline"]};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}
QWidget#FooterBar {{
    background-color: {t["window_bg"]};
}}
QWidget#ReviewPane {{
    background-color: {t["review_bg"]};
}}
QWidget#StatusStrip {{
    background-color: {t["status_bg"]};
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QToolTip {{
    background-color: {t["card"]};
    color: {t["text"]};
    border: 1px solid {t["outline"]};
    padding: 4px 8px;
}}
"""
