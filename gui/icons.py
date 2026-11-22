"""浅色界面使用的线形图标，按高 DPI 渲染。"""

# Embedded Lucide icons (https://lucide.dev). See THIRD_PARTY_NOTICES.txt.

from functools import lru_cache

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QAbstractButton, QWidget

from .styles import ACCENT, DARK_ACCENT, DISABLED, WHITE

_PATHS = {
    "wave": ("M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2",),
    "chart": ("M12 16v5", "M16 14.639V21", "M20 10.656V21", "m22 3-8.646 8.646a.5.5 0 0 1-.708 0L9.354 8.354a.5.5 0 0 0-.707 0L2 15", "M4 18.463V21", "M8 14.656V21"),
    "plus": ("M5 12h14", "M12 5v14"),
    "run": ("M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z",),
    "download": ("M12 15V3", "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "m7 10 5 5 5-5"),
    "open": ("M15 3h6v6", "M10 14 21 3", "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"),
    "previous": ("m15 18-6-6 6-6",),
    "next": ("m9 18 6-6-6-6",),
}


@lru_cache(maxsize=32)
def interface_icon(name: str, size: int = 16, color: str = ACCENT) -> QIcon:
    paths = "".join(f'<path d="{path}"/>' for path in _PATHS[name])
    icon = QIcon()
    for mode, ink in ((QIcon.Mode.Normal, color), (QIcon.Mode.Disabled, DISABLED)):
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            f'fill="none" stroke="{ink}" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round">{paths}</svg>'
        )
        renderer = QSvgRenderer(QByteArray(svg.encode("ascii")))
        pixmap = QPixmap(size * 2, size * 2)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        icon.addPixmap(pixmap, mode)
    return icon


def set_button_icon(
    button: QAbstractButton,
    name: str,
    *,
    primary: bool = False,
    dark: bool = False,
) -> None:
    button.setProperty("iconName", name)
    button.setProperty("iconPrimary", primary)
    color = WHITE if primary else (DARK_ACCENT if dark else ACCENT)
    button.setIcon(interface_icon(name, color=color))


def refresh_interface_icons(root: QWidget, dark: bool) -> None:
    """主题切换后刷新已创建按钮的图标颜色。"""
    for button in root.findChildren(QAbstractButton):
        name = button.property("iconName")
        if not name:
            continue
        primary = bool(button.property("iconPrimary"))
        set_button_icon(button, str(name), primary=primary, dark=dark)
