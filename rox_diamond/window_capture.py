from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import logging
import time

import mss
import numpy as np

import config as cfg


logger = logging.getLogger(__name__)
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    user32.SetProcessDPIAware()

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001


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
    return value.casefold().replace("ö", "o").replace("繹", "o")


def window_info_from_handle(hwnd: int) -> WindowInfo:
    if not user32.IsWindow(hwnd):
        raise RuntimeError(f"ROX window handle {hwnd} was not found.")
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    return WindowInfo(hwnd, buffer.value, process_id.value)


def find_windows(title_keywords: tuple[str, ...]) -> list[WindowInfo]:
    matches: list[WindowInfo] = []
    keywords = tuple(_normalized_title(item) for item in title_keywords)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        normalized = _normalized_title(title)
        if any(keyword in normalized for keyword in keywords):
            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            matches.append(WindowInfo(hwnd, title, process_id.value))
        return True

    user32.EnumWindows(callback, 0)
    return sorted(matches, key=lambda item: item.hwnd)


def select_window(
    matches: list[WindowInfo],
    *,
    hwnd: int | None = None,
    window_index: int | None = None,
) -> WindowInfo:
    if not matches:
        raise RuntimeError("No ROX window found. Start ROX and keep it visible.")
    if hwnd is not None:
        for match in matches:
            if match.hwnd == hwnd:
                return match
        raise RuntimeError(f"ROX window handle {hwnd} was not found.")
    if window_index is not None:
        if not 1 <= window_index <= len(matches):
            raise RuntimeError(f"Window index must be 1..{len(matches)}.")
        return matches[window_index - 1]
    if len(matches) > 1:
        raise RuntimeError(
            f"Found {len(matches)} ROX windows. Use --list-windows and select "
            "one with --window-index or --hwnd."
        )
    return matches[0]


def find_window(
    title_keywords: tuple[str, ...],
    *,
    hwnd: int | None = None,
    window_index: int | None = None,
) -> tuple[int, str]:
    if hwnd is not None:
        selected = window_info_from_handle(hwnd)
        return selected.hwnd, selected.title

    selected = select_window(
        find_windows(title_keywords),
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
        point.x,
        point.y,
        rect.right - rect.left,
        rect.bottom - rect.top,
    )


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
            and user32.AttachThreadInput(current_thread, foreground_thread, True)
        )
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(current_thread, foreground_thread, False)
    time.sleep(cfg.FOREGROUND_SETTLE_SECONDS)
    if user32.GetForegroundWindow() != hwnd:
        raise RuntimeError(
            "Unable to activate ROX. Run the launcher as administrator when "
            "the game is elevated."
        )


def is_key_down(virtual_key: int) -> bool:
    return bool(user32.GetAsyncKeyState(virtual_key) & 0x8000)


def capture_window(hwnd: int, mode: str = "screen") -> np.ndarray:
    if mode != "screen":
        raise ValueError(f"Unsupported CAPTURE_MODE: {mode}")
    bounds = get_client_bounds(hwnd)
    if bounds.width <= 0 or bounds.height <= 0:
        raise RuntimeError("ROX client area is empty. Restore the game window.")
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


def ratio_point(
    size: tuple[int, int],
    point: tuple[float, float],
) -> tuple[int, int]:
    width, height = size
    return round(width * point[0]), round(height * point[1])


def _send_mouse_input(
    flags: int,
    *,
    absolute_x: int = 0,
    absolute_y: int = 0,
) -> None:
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


def release_mouse_buttons() -> None:
    _send_mouse_input(MOUSEEVENTF_LEFTUP)


def click_client(
    hwnd: int,
    point: tuple[int, int],
    mode: str,
    *,
    activate: bool = True,
) -> None:
    if mode == "background":
        x, y = point
        packed = (y << 16) | (x & 0xFFFF)
        logger.info("Background click: client=(%s, %s)", x, y)
        down_sent = user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, packed)
        if not down_sent:
            raise ctypes.WinError()
        try:
            time.sleep(cfg.MOUSE_PRESS_SECONDS)
        finally:
            up_sent = user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, packed)
            if not up_sent:
                raise ctypes.WinError()
        return

    if mode != "sendinput":
        raise ValueError(f"Unsupported CLICK_MODE: {mode}")

    bounds = get_client_bounds(hwnd)
    previous_cursor = wintypes.POINT()
    cursor_saved = bool(user32.GetCursorPos(ctypes.byref(previous_cursor)))
    if activate:
        activate_window(hwnd)

    screen_x = bounds.left + point[0]
    screen_y = bounds.top + point[1]
    virtual_left = user32.GetSystemMetrics(76)
    virtual_top = user32.GetSystemMetrics(77)
    virtual_width = user32.GetSystemMetrics(78)
    virtual_height = user32.GetSystemMetrics(79)
    absolute_x = round(
        (screen_x - virtual_left) * 65535 / max(1, virtual_width - 1)
    )
    absolute_y = round(
        (screen_y - virtual_top) * 65535 / max(1, virtual_height - 1)
    )

    try:
        logger.info("SendInput click: client=(%s, %s)", point[0], point[1])
        _send_mouse_input(
            MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
            absolute_x=absolute_x,
            absolute_y=absolute_y,
        )
        time.sleep(cfg.MOUSE_MOVE_SETTLE_SECONDS)
        _send_mouse_input(
            MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
            absolute_x=absolute_x,
            absolute_y=absolute_y,
        )
        try:
            time.sleep(cfg.MOUSE_PRESS_SECONDS)
        finally:
            _send_mouse_input(
                MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
                absolute_x=absolute_x,
                absolute_y=absolute_y,
            )
            time.sleep(cfg.MOUSE_RELEASE_SETTLE_SECONDS)
    finally:
        if cfg.RESTORE_CURSOR_AFTER_CLICK and cursor_saved:
            user32.SetCursorPos(previous_cursor.x, previous_cursor.y)
