from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import time
from dataclasses import dataclass

# DPI awareness must be configured before importing MSS or PyAutoGUI. Some
# screen libraries set process DPI awareness during import, which otherwise
# locks coordinates to the primary monitor's scale.
user32 = ctypes.windll.user32
try:
    per_monitor_v2 = ctypes.c_void_p(-4)
    if not user32.SetProcessDpiAwarenessContext(per_monitor_v2):
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    user32.SetProcessDPIAware()

import cv2
import mss
import numpy as np
import pyautogui

import config as cfg


logger = logging.getLogger(__name__)
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001
PW_CLIENTONLY = 0x00000001
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


@dataclass(frozen=True)
class ClientBounds:
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str
    process_id: int


def _normalized_title(value: str) -> str:
    return value.casefold().replace("ö", "o")


def find_windows(title_keywords: tuple[str, ...]) -> list[WindowInfo]:
    matches: list[WindowInfo] = []
    normalized_keywords = tuple(_normalized_title(item) for item in title_keywords)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        normalized = _normalized_title(title)
        if any(keyword in normalized for keyword in normalized_keywords):
            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            matches.append(WindowInfo(hwnd, title, process_id.value))
        return True

    user32.EnumWindows(enum_callback, 0)
    return sorted(matches, key=lambda item: item.hwnd)


def select_window(
    matches: list[WindowInfo],
    *,
    hwnd: int | None = None,
    window_index: int | None = None,
) -> WindowInfo:
    if not matches:
        raise RuntimeError(
            "找不到 ROX 遊戲視窗。請先啟動遊戲，並確認視窗標題包含 ROX。"
        )
    if hwnd is not None:
        for match in matches:
            if match.hwnd == hwnd:
                return match
        raise RuntimeError(f"找不到 ROX 視窗 handle={hwnd}。")
    if window_index is not None:
        if not 1 <= window_index <= len(matches):
            raise RuntimeError(
                f"視窗序號必須介於 1 到 {len(matches)}。"
            )
        return matches[window_index - 1]
    if len(matches) > 1:
        raise RuntimeError(
            f"找到 {len(matches)} 個 ROX 視窗。請先使用 --list-windows，"
            "再用 --window-index 或 --hwnd 指定角色。"
        )
    return matches[0]


def find_window(
    title_keywords: tuple[str, ...],
    *,
    hwnd: int | None = None,
    window_index: int | None = None,
) -> tuple[int, str]:
    selected = select_window(
        find_windows(title_keywords),
        hwnd=hwnd,
        window_index=window_index,
    )
    return selected.hwnd, selected.title


def get_client_bounds(hwnd: int) -> ClientBounds:
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise ctypes.WinError()
    point = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
        raise ctypes.WinError()
    return ClientBounds(
        left=point.x,
        top=point.y,
        width=rect.right - rect.left,
        height=rect.bottom - rect.top,
    )


def ratio_point(
    size: tuple[int, int],
    point: tuple[float, float],
) -> tuple[int, int]:
    width, height = size
    return round(width * point[0]), round(height * point[1])


def get_monitor_bounds(hwnd: int) -> ClientBounds:
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    monitor = user32.MonitorFromWindow(hwnd, 2)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        raise ctypes.WinError()
    rect = info.rcMonitor
    return ClientBounds(
        left=rect.left,
        top=rect.top,
        width=rect.right - rect.left,
        height=rect.bottom - rect.top,
    )


def is_key_down(virtual_key: int) -> bool:
    return bool(user32.GetAsyncKeyState(virtual_key) & 0x8000)


def is_window_foreground(hwnd: int) -> bool:
    return user32.GetForegroundWindow() == hwnd


def activate_window(hwnd: int) -> None:
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
    if user32.GetForegroundWindow() != hwnd:
        foreground = user32.GetForegroundWindow()
        current_thread = kernel32.GetCurrentThreadId()
        foreground_thread = (
            user32.GetWindowThreadProcessId(foreground, None)
            if foreground
            else 0
        )
        attached = bool(
            foreground_thread
            and foreground_thread != current_thread
            and user32.AttachThreadInput(
                current_thread,
                foreground_thread,
                True,
            )
        )
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(
                    current_thread,
                    foreground_thread,
                    False,
                )
    time.sleep(cfg.FOREGROUND_SETTLE_SECONDS)
    if user32.GetForegroundWindow() != hwnd:
        raise RuntimeError(
            "Unable to activate the selected ROX window. Run the launcher "
            "as administrator when the game is elevated."
        )


def capture_screen(hwnd: int) -> np.ndarray:
    bounds = get_client_bounds(hwnd)
    if bounds.width <= 0 or bounds.height <= 0:
        raise RuntimeError("遊戲視窗目前最小化或大小無效。")
    with mss.mss() as sct:
        shot = sct.grab(
            {
                "left": bounds.left,
                "top": bounds.top,
                "width": bounds.width,
                "height": bounds.height,
            }
        )
    return np.ascontiguousarray(np.asarray(shot)[:, :, :3])


def capture_client_region(
    hwnd: int,
    center: tuple[int, int],
    size: tuple[int, int],
) -> np.ndarray:
    bounds = get_client_bounds(hwnd)
    width = min(size[0], bounds.width)
    height = min(size[1], bounds.height)
    left = max(0, min(bounds.width - width, center[0] - width // 2))
    top = max(0, min(bounds.height - height, center[1] - height // 2))
    with mss.mss() as sct:
        shot = sct.grab(
            {
                "left": bounds.left + left,
                "top": bounds.top + top,
                "width": width,
                "height": height,
            }
        )
    return np.ascontiguousarray(np.asarray(shot)[:, :, :3])


def capture_printwindow(hwnd: int) -> np.ndarray:
    bounds = get_client_bounds(hwnd)
    width, height = bounds.width, bounds.height
    if width <= 0 or height <= 0:
        raise RuntimeError("遊戲視窗目前最小化或大小無效。")

    window_dc = user32.GetDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    previous = gdi32.SelectObject(memory_dc, bitmap)

    try:
        user32.PrintWindow(hwnd, memory_dc, PW_CLIENTONLY)
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = BI_RGB

        buffer = ctypes.create_string_buffer(width * height * 4)
        copied = gdi32.GetDIBits(
            memory_dc,
            bitmap,
            0,
            height,
            buffer,
            ctypes.byref(info),
            DIB_RGB_COLORS,
        )
        if copied != height:
            raise RuntimeError("PrintWindow 無法讀取完整遊戲畫面。")
        bgra = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)
        frame = np.ascontiguousarray(bgra[:, :, :3])
        if frame.std() < 2.0:
            raise RuntimeError(
                "PrintWindow 得到近乎全黑畫面。請把 CAPTURE_MODE 改成 screen。"
            )
        return frame
    finally:
        gdi32.SelectObject(memory_dc, previous)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


def capture_window(hwnd: int, mode: str) -> np.ndarray:
    if mode == "printwindow":
        return capture_printwindow(hwnd)
    if mode == "screen":
        return capture_screen(hwnd)
    raise ValueError(f"未知的 CAPTURE_MODE: {mode}")


def click_client(
    hwnd: int,
    point: tuple[int, int],
    mode: str,
    count: int = 1,
    interval: float = 0.05,
) -> None:
    x, y = point
    if mode in ("background", "focus_message"):
        packed = (y << 16) | (x & 0xFFFF)
        previous_foreground = user32.GetForegroundWindow()
        if mode == "focus_message" and previous_foreground != hwnd:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            time.sleep(cfg.FOCUS_MESSAGE_SETTLE_SECONDS)
        logger.info(
            "PostMessage click: mode=%s client=(%s, %s) count=%s",
            mode,
            x,
            y,
            count,
        )
        try:
            for _ in range(count):
                down_sent = user32.PostMessageW(
                    hwnd,
                    WM_LBUTTONDOWN,
                    MK_LBUTTON,
                    packed,
                )
                time.sleep(cfg.MOUSE_PRESS_SECONDS)
                up_sent = user32.PostMessageW(
                    hwnd,
                    WM_LBUTTONUP,
                    0,
                    packed,
                )
                if not down_sent or not up_sent:
                    raise ctypes.WinError()
                time.sleep(interval)
        finally:
            if (
                mode == "focus_message"
                and previous_foreground
                and previous_foreground != hwnd
            ):
                user32.SetForegroundWindow(previous_foreground)
        return

    if mode == "foreground":
        bounds = get_client_bounds(hwnd)
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.08)
        screen_x = bounds.left + x
        screen_y = bounds.top + y
        print(
            f"點擊：client=({x}, {y}) screen=({screen_x}, {screen_y}) "
            f"count={count}"
        )
        pyautogui.moveTo(screen_x, screen_y, duration=0.04)
        for _ in range(count):
            pyautogui.mouseDown()
            time.sleep(0.06)
            pyautogui.mouseUp()
            time.sleep(interval)
        return

    if mode == "sendinput":
        bounds = get_client_bounds(hwnd)
        previous_foreground = user32.GetForegroundWindow()
        previous_cursor = wintypes.POINT()
        cursor_saved = bool(user32.GetCursorPos(ctypes.byref(previous_cursor)))
        activate_window(hwnd)

        screen_x = bounds.left + x
        screen_y = bounds.top + y
        virtual_left = user32.GetSystemMetrics(76)
        virtual_top = user32.GetSystemMetrics(77)
        virtual_width = user32.GetSystemMetrics(78)
        virtual_height = user32.GetSystemMetrics(79)
        absolute_x = round((screen_x - virtual_left) * 65535 / max(1, virtual_width - 1))
        absolute_y = round((screen_y - virtual_top) * 65535 / max(1, virtual_height - 1))

        def send(flags: int) -> None:
            item = INPUT(
                type=INPUT_MOUSE,
                union=INPUTUNION(
                    mi=MOUSEINPUT(
                        dx=absolute_x,
                        dy=absolute_y,
                        mouseData=0,
                        dwFlags=flags,
                        time=0,
                        dwExtraInfo=None,
                    )
                ),
            )
            sent = user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT))
            if sent != 1:
                raise ctypes.WinError()

        logger.info(
            f"SendInput click: client=({x}, {y}) "
            f"screen=({screen_x}, {screen_y}) count={count}"
        )
        try:
            send(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK)
            time.sleep(cfg.MOUSE_MOVE_SETTLE_SECONDS)
            for _ in range(count):
                send(
                    MOUSEEVENTF_LEFTDOWN
                    | MOUSEEVENTF_ABSOLUTE
                    | MOUSEEVENTF_VIRTUALDESK
                )
                try:
                    time.sleep(cfg.MOUSE_PRESS_SECONDS)
                finally:
                    send(
                        MOUSEEVENTF_LEFTUP
                        | MOUSEEVENTF_ABSOLUTE
                        | MOUSEEVENTF_VIRTUALDESK
                    )
                    time.sleep(cfg.MOUSE_RELEASE_SETTLE_SECONDS)
                time.sleep(interval)
        finally:
            if cfg.RESTORE_CURSOR_AFTER_CLICK and cursor_saved:
                user32.SetCursorPos(previous_cursor.x, previous_cursor.y)
            if (
                cfg.RESTORE_FOREGROUND_AFTER_CLICK
                and previous_foreground
                and previous_foreground != hwnd
                and user32.IsWindow(previous_foreground)
            ):
                user32.SetForegroundWindow(previous_foreground)
        return

    raise ValueError(f"未知的 CLICK_MODE: {mode}")


def show_frame(window_name: str, frame: np.ndarray) -> int:
    cv2.imshow(window_name, frame)
    return cv2.waitKey(1) & 0xFF
