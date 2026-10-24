"""Small independent, non-activating desktop surface above games and Magpie."""
from __future__ import annotations
from collections import deque
import ctypes
from ctypes import wintypes as W
import os
import time
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QObject, Qt, QTimer, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QImageReader, QPainter, QPainterPath, QPen, QPixmap, QGuiApplication
from PySide6.QtWidgets import QWidget


@lru_cache(maxsize=64)
def _decode_icon(path, modified, size):
    reader = QImageReader(path)
    bounds = reader.size()
    if bounds.isValid(): reader.setScaledSize(bounds.scaled(QSize(120, 120), Qt.KeepAspectRatio))
    return reader.read()


def read_toast_icon(path):
    """Worker-only disk access/decoding. QPixmap creation stays on the GUI thread."""
    if path:
        try:
            stamp = Path(path).stat()
            return _decode_icon(str(path), stamp.st_mtime_ns, stamp.st_size)
        except (OSError, ValueError): pass
    return QImage()


def valid_target(target):
    if os.name != 'nt' or not target: return False
    user = ctypes.windll.user32
    user.IsWindow.argtypes = [W.HWND]; user.IsIconic.argtypes = [W.HWND]
    user.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
    pid = W.DWORD(); hwnd = target.get('hwnd', 0)
    if not user.IsWindow(hwnd) or user.IsIconic(hwnd): return False
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == target.get('pid')


def game_foreground(target):
    if not valid_target(target): return False
    from launch_ready import foreground
    hwnd, pid = foreground()
    if pid == target['pid']: return True
    # A fullscreen scaler may be foreground on some versions; accept only our
    # exact source, not an unrelated instance of Magpie on another game.
    if target.get('scaler') and hwnd == target['scaler']: return True
    return False


def target_screen(target):
    app = QGuiApplication.instance()
    if os.name == 'nt' and target:
        class MONITORINFOEX(ctypes.Structure):
            _fields_ = [('cbSize', W.DWORD), ('rcMonitor', W.RECT), ('rcWork', W.RECT), ('dwFlags', W.DWORD), ('szDevice', W.WCHAR * 32)]
        user = ctypes.windll.user32
        user.MonitorFromWindow.argtypes = [W.HWND, W.DWORD]; user.MonitorFromWindow.restype = W.HANDLE
        user.GetMonitorInfoW.argtypes = [W.HANDLE, ctypes.c_void_p]
        info = MONITORINFOEX(); info.cbSize = ctypes.sizeof(info)
        if user.GetMonitorInfoW(user.MonitorFromWindow(target['hwnd'], 2), ctypes.byref(info)):
            for screen in app.screens():
                if screen.name().casefold() == info.szDevice.casefold(): return screen
    return app.primaryScreen()


class Toast(QWidget):
    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput)
        self.setObjectName('achievementToast')
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.resize(400, 112); self.row = {}; self.icon = QPixmap()
        self.ensurePolished()
        # Create the native surface and resolve fonts before gameplay, not on
        # the first unlock. Keep it hidden and excluded from scaler capture.
        handle = int(self.winId())
        if os.name == 'nt':
            user = ctypes.windll.user32
            user.SetWindowDisplayAffinity.argtypes = [W.HWND, W.DWORD]
            user.SetWindowDisplayAffinity(handle, 0x11)
        for size in (9, 12):
            font = QFont('Microsoft YaHei UI', size); font.setBold(size == 12)
            QFontMetrics(font).horizontalAdvance('成就已解锁 Achievement')

    def present(self, row, target):
        self.row = row
        image = row.get('_toast_icon')
        self.icon = QPixmap.fromImage(image) if isinstance(image, QImage) and not image.isNull() else QPixmap()
        screen = target_screen(target); area = screen.availableGeometry()
        self.resize(min(400, area.width() - 32), 112)
        self.move(area.right() - self.width() - 20, area.bottom() - self.height() - 20)
        self.show(); self.update(); self.keep_above()

    def keep_above(self):
        if os.name == 'nt':
            user = ctypes.windll.user32
            user.SetWindowPos.argtypes = [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.UINT]
            user.SetWindowPos(int(self.winId()), -1, 0, 0, 0, 0, 0x13)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor('#575465'), 1)); p.setBrush(QColor('#24232d'))
        p.drawRoundedRect(QRectF(1, 1, self.width()-2, self.height()-2), 12, 12)
        if not self.icon.isNull(): p.drawPixmap(18, 26, 60, 60, self.icon)
        else:
            p.setBrush(QColor('#dfc07a')); p.setPen(Qt.NoPen)
            cup = QPainterPath(); cup.moveTo(34, 38); cup.lineTo(62, 38); cup.lineTo(59, 57); cup.quadTo(48, 73, 37, 57); cup.closeSubpath(); p.drawPath(cup)
            p.setPen(QPen(QColor('#dfc07a'), 3)); p.drawArc(27, 39, 14, 19, 90*16, 180*16); p.drawArc(55, 39, 14, 19, -90*16, 180*16)
            p.drawLine(48, 65, 48, 77); p.drawLine(38, 78, 58, 78)
        p.setFont(QFont('Microsoft YaHei UI', 9)); p.setPen(QColor('#dfc07a'))
        p.drawText(96, 27, '成就已解锁' if not self.row.get('preview') else '成就弹窗预览')
        p.setPen(QColor('#f4f2fa')); font = QFont('Microsoft YaHei UI', 12); font.setBold(True); p.setFont(font)
        name = p.fontMetrics().elidedText(self.row.get('name', ''), Qt.ElideRight, self.width()-114)
        p.drawText(96, 54, name)
        p.setFont(QFont('Microsoft YaHei UI', 9)); p.setPen(QColor('#bdb9cb'))
        text = self.row.get('description') or self.row.get('game_name', '')
        p.drawText(QRectF(96, 64, self.width()-114, 36), Qt.TextWordWrap, p.fontMetrics().elidedText(text.replace('\n', ' '), Qt.ElideRight, 2*(self.width()-114)))


class AchievementOverlay(QObject):
    def __init__(self, parent=None):
        super().__init__(parent); self.toast = None; self.queue = deque(maxlen=100)
        self.current = None; self.remaining = 0; self.last = 0; self.closed = False; self.enabled = True
        self.timer = QTimer(self); self.timer.setInterval(150); self.timer.timeout.connect(self.tick)

    def prepare(self):
        if not self.closed and self.enabled and self.toast is None: self.toast = Toast()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled: self.clear()

    def clear(self):
        self.timer.stop(); self.queue.clear(); self.current = None; self.remaining = 0
        if self.toast: self.toast.hide()

    def enqueue(self, row, target, preview=False):
        if self.closed or not self.enabled: return
        # Drop stale queued notifications after a session rather than show them
        # over another application or over a later game session.
        self.queue.append((dict(row, preview=preview), dict(target or {}), time.monotonic(), preview))
        if not self.timer.isActive(): self.last = time.monotonic(); self.timer.start(); self.tick()

    def tick(self):
        if self.closed or not self.enabled:
            self.clear(); return
        now = time.monotonic(); elapsed = now-self.last; self.last = now
        if self.current:
            row, target, created, preview = self.current
            if now-created > 120 or not preview and not valid_target(target):
                self.current = None
                if self.toast: self.toast.hide()
            elif preview or game_foreground(target):
                self.prepare()
                if not self.toast.isVisible(): self.toast.present(row, target)
                # Showing/resuming already establishes z-order. Reasserting it
                # every 150 ms needlessly wakes the desktop compositor.
                self.remaining -= elapsed
                if self.remaining <= 0: self.toast.hide(); self.current = None
            elif self.toast: self.toast.hide()
        if not self.current:
            while self.queue:
                item = self.queue.popleft()
                if now-item[2] <= 120 and (item[3] or valid_target(item[1])):
                    self.current = item; self.remaining = 5.0; break
            if not self.current: self.timer.stop()

    def discard(self, ident):
        self.queue = deque((item for item in self.queue if item[0].get('game_id') != ident), maxlen=100)
        if self.current and self.current[0].get('game_id') == ident:
            self.current = None
            if self.toast: self.toast.hide()

    def shutdown(self):
        self.closed = True; self.clear()
        if self.toast: self.toast.close(); self.toast.deleteLater(); self.toast = None
