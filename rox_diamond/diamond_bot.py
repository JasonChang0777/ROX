from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import time

import cv2

import config as cfg
from vision import (
    Rect,
    find_market_buy_button,
    find_purchase_dialog,
    keypad_point,
    read_today_limit,
)
from window_capture import (
    activate_window,
    capture_window,
    click_client,
    find_window,
    find_windows,
    get_client_bounds,
    is_key_down,
    release_mouse_buttons,
)


logger = logging.getLogger(__name__)


class StopRequested(Exception):
    pass


class DailyLimitReached(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ROX Diamond Buyer Bot")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--window-index",
        type=int,
        help="Select a ROX window by the 1-based index from --list-windows",
    )
    selection.add_argument(
        "--hwnd",
        type=int,
        help="Select a ROX window by its Windows handle",
    )
    parser.add_argument(
        "--list-windows",
        action="store_true",
        help="List visible ROX windows and exit",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Capture and analyze one frame without clicking",
    )
    return parser.parse_args()


def configure_logging() -> None:
    cfg.LOG_DIR.mkdir(exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        cfg.LOG_FILE,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logging.basicConfig(
        level=logging.INFO,
        handlers=(console, file_handler),
        force=True,
    )


def check_stop_key() -> None:
    if is_key_down(cfg.STOP_VIRTUAL_KEY):
        raise StopRequested


def interruptible_sleep(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        check_stop_key()
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))


def save_debug(name: str, frame) -> None:
    if not cfg.SAVE_DEBUG_FRAMES:
        return
    cfg.DEBUG_DIR.mkdir(exist_ok=True)
    cv2.imwrite(str(cfg.DEBUG_DIR / name), frame)


def list_windows() -> None:
    matches = find_windows(cfg.WINDOW_TITLE_KEYWORDS)
    if not matches:
        logger.info("No visible ROX windows found.")
        return
    logger.info("Visible ROX windows:")
    for index, match in enumerate(matches, start=1):
        bounds = get_client_bounds(match.hwnd)
        status = "ready" if bounds.width > 0 and bounds.height > 0 else "minimized"
        logger.info(
            "  [%s] hwnd=%s pid=%s size=%sx%s status=%s title=%s",
            index,
            match.hwnd,
            match.process_id,
            bounds.width,
            bounds.height,
            status,
            match.title,
        )


def stable_today_limit(hwnd: int, dialog: Rect) -> int | None:
    stable_value: int | None = None
    stable_reads = 0
    last_digits = ""
    last_confidence = 0.0

    for _ in range(cfg.TODAY_LIMIT_REQUIRED_READS + 2):
        check_stop_key()
        frame = capture_window(hwnd, cfg.CAPTURE_MODE)
        refreshed = find_purchase_dialog(frame)
        if refreshed is not None:
            dialog = refreshed
        value, confidence, digits = read_today_limit(frame, dialog)
        last_digits = digits
        last_confidence = confidence
        logger.info(
            "Today diamond limit read: value=%s digits=%s confidence=%.3f",
            value if value is not None else "<unreadable>",
            digits or "<none>",
            confidence,
        )
        if value is None:
            stable_value = None
            stable_reads = 0
        elif value == stable_value:
            stable_reads += 1
        else:
            stable_value = value
            stable_reads = 1

        if stable_reads >= cfg.TODAY_LIMIT_REQUIRED_READS:
            return stable_value
        interruptible_sleep(0.15)

    logger.warning(
        "Could not get a stable daily limit read; last digits=%s confidence=%.3f.",
        last_digits or "<none>",
        last_confidence,
    )
    return None


def enter_max_quantity(hwnd: int, dialog: Rect) -> None:
    click_client(hwnd, dialog.relative_point(cfg.QUANTITY_FIELD_POINT), cfg.CLICK_MODE)
    interruptible_sleep(cfg.ACTION_INTERVAL_SECONDS)

    for _ in range(cfg.MAX_QUANTITY_DIGIT_COUNT):
        click_client(
            hwnd,
            keypad_point(dialog, cfg.MAX_QUANTITY_DIGIT),
            cfg.CLICK_MODE,
        )
        interruptible_sleep(cfg.KEYPAD_DIGIT_INTERVAL_SECONDS)

    click_client(hwnd, keypad_point(dialog, "enter"), cfg.CLICK_MODE)
    interruptible_sleep(cfg.ACTION_INTERVAL_SECONDS)


def buy_from_dialog(hwnd: int, dialog: Rect) -> None:
    today_limit = stable_today_limit(hwnd, dialog)
    if today_limit == 0 and cfg.STOP_WHEN_TODAY_LIMIT_ZERO:
        raise DailyLimitReached("Today diamond purchase limit is already 0.")
    if today_limit == 0:
        logger.warning(
            "Today diamond purchase limit is 0; continuing because "
            "STOP_WHEN_TODAY_LIMIT_ZERO is disabled."
        )

    if today_limit is None:
        logger.warning(
            "Daily limit was unreadable; continuing with max quantity input."
        )
    else:
        logger.info("Today diamond purchase limit: %s", today_limit)

    enter_max_quantity(hwnd, dialog)
    click_client(hwnd, dialog.relative_point(cfg.PURCHASE_BUTTON_POINT), cfg.CLICK_MODE)
    logger.info("Purchase button clicked.")
    interruptible_sleep(cfg.AFTER_PURCHASE_WAIT_SECONDS)


def wait_for_dialog(hwnd: int) -> Rect | None:
    deadline = time.monotonic() + cfg.DIALOG_WAIT_SECONDS
    while time.monotonic() < deadline:
        check_stop_key()
        frame = capture_window(hwnd, cfg.CAPTURE_MODE)
        dialog = find_purchase_dialog(frame)
        if dialog is not None:
            save_debug("diamond_dialog_detected.png", frame)
            return dialog
        interruptible_sleep(cfg.POLL_INTERVAL_SECONDS)
    return None


def inspect_frame(hwnd: int) -> None:
    frame = capture_window(hwnd, cfg.CAPTURE_MODE)
    output = frame.copy()
    button = find_market_buy_button(frame)
    if button is None:
        logger.info("Market buy button: not found.")
    else:
        cv2.rectangle(
            output,
            (button.rect.left, button.rect.top),
            (button.rect.left + button.rect.width, button.rect.top + button.rect.height),
            (0, 165, 255),
            3,
        )
        logger.info(
            "Market buy button: center=%s orange=%.3f",
            button.rect.center,
            button.orange_ratio,
        )

    dialog = find_purchase_dialog(frame)
    if dialog is None:
        logger.info("Purchase dialog: not found.")
    else:
        cv2.rectangle(
            output,
            (dialog.left, dialog.top),
            (dialog.left + dialog.width, dialog.top + dialog.height),
            (0, 0, 255),
            3,
        )
        today_limit, confidence, digits = read_today_limit(frame, dialog)
        logger.info(
            "Purchase dialog: today_limit=%s digits=%s confidence=%.3f",
            today_limit if today_limit is not None else "<unreadable>",
            digits or "<none>",
            confidence,
        )
    save_debug("diamond_inspect.png", output)
    logger.info("Inspection saved to %s", cfg.DEBUG_DIR / "diamond_inspect.png")


def main() -> None:
    args = parse_args()
    configure_logging()
    cfg.DEBUG_DIR.mkdir(exist_ok=True)

    if args.list_windows:
        list_windows()
        return

    hwnd, title = find_window(
        cfg.WINDOW_TITLE_KEYWORDS,
        hwnd=args.hwnd,
        window_index=args.window_index,
    )
    if cfg.CLICK_MODE == "sendinput":
        activate_window(hwnd)
    bounds = get_client_bounds(hwnd)
    logger.info("=== ROX Diamond Buyer Bot started ===")
    logger.info("Game window: %s (handle=%s)", title, hwnd)
    logger.info("Client size: %sx%s", bounds.width, bounds.height)
    logger.info("Capture=%s, click=%s", cfg.CAPTURE_MODE, cfg.CLICK_MODE)
    logger.info("Press %s to stop.", cfg.STOP_KEY_NAME)
    logger.info("Start with ROX already on Trading House > Diamond.")

    if args.inspect:
        inspect_frame(hwnd)
        return

    buy_button_frames = 0
    last_diagnostic = 0.0

    try:
        while True:
            check_stop_key()
            now = time.monotonic()
            frame = capture_window(hwnd, cfg.CAPTURE_MODE)

            dialog = find_purchase_dialog(frame)
            if dialog is not None:
                buy_from_dialog(hwnd, dialog)
                buy_button_frames = 0
                continue

            button = find_market_buy_button(frame)
            if button is None:
                buy_button_frames = 0
            else:
                buy_button_frames += 1

            if buy_button_frames >= cfg.BUY_BUTTON_REQUIRED_FRAMES and button is not None:
                logger.info(
                    "Diamond buy button detected: center=%s orange=%.3f",
                    button.rect.center,
                    button.orange_ratio,
                )
                save_debug("diamond_buy_button_detected.png", frame)
                click_client(hwnd, button.rect.center, cfg.CLICK_MODE)
                interruptible_sleep(cfg.ACTION_INTERVAL_SECONDS)
                dialog = wait_for_dialog(hwnd)
                if dialog is None:
                    logger.warning("Purchase dialog did not appear after click.")
                else:
                    buy_from_dialog(hwnd, dialog)
                buy_button_frames = 0
                continue

            if now - last_diagnostic >= cfg.DIAGNOSTIC_INTERVAL_SECONDS:
                logger.info(
                    "Diamond scan: buy_button=%s stable_frames=%s",
                    button is not None,
                    buy_button_frames,
                )
                last_diagnostic = now
            interruptible_sleep(cfg.POLL_INTERVAL_SECONDS)
    except DailyLimitReached as exc:
        logger.info("%s Task complete.", exc)
    except (KeyboardInterrupt, StopRequested):
        logger.info("Stopped by user.")
    finally:
        release_mouse_buttons()
        logger.info("=== ROX Diamond Buyer Bot stopped ===")


if __name__ == "__main__":
    main()
