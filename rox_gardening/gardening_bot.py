from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import time

import cv2

import config as cfg
from vision import (
    find_verification_dialog,
    inspect_garden_button,
    keypad_point,
    read_answer_digits,
    read_equation,
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
    ratio_point,
)


logger = logging.getLogger(__name__)


class StopRequested(Exception):
    pass


def check_stop_key() -> None:
    if is_key_down(cfg.STOP_VIRTUAL_KEY):
        raise StopRequested


def interruptible_sleep(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        check_stop_key()
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))


def wait_for_answer_text(
    hwnd: int,
    dialog,
    expected: str,
) -> bool:
    deadline = time.monotonic() + cfg.ANSWER_CHECK_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        check_stop_key()
        frame = capture_window(hwnd, cfg.CAPTURE_MODE)
        digits, confidence = read_answer_digits(frame, dialog)
        logger.info(
            "Answer field: expected=%s actual=%s confidence=%.3f",
            expected,
            digits or "<empty>",
            confidence,
        )
        if digits == expected:
            return True
        interruptible_sleep(cfg.ANSWER_CHECK_INTERVAL_SECONDS)
    return False


def enter_answer_with_retries(hwnd: int, dialog, answer: int) -> bool:
    expected_answer = str(answer)
    max_attempts = cfg.VERIFY_ANSWER_RETRY_ATTEMPTS + 1

    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            logger.warning(
                "Retrying answer input: attempt=%s/%s",
                attempt,
                max_attempts,
            )
            click_client(hwnd, keypad_point(dialog, "clear"), cfg.CLICK_MODE)
            interruptible_sleep(cfg.KEYPAD_CLICK_INTERVAL_SECONDS)
            if not wait_for_answer_text(hwnd, dialog, ""):
                logger.warning("Answer field did not clear before retry.")

        expected_text = ""
        matched = True
        for digit in expected_answer:
            expected_text += digit
            check_stop_key()
            click_client(hwnd, keypad_point(dialog, digit), cfg.CLICK_MODE)
            interruptible_sleep(cfg.KEYPAD_CLICK_INTERVAL_SECONDS)
            if wait_for_answer_text(hwnd, dialog, expected_text):
                continue

            frame = capture_window(hwnd, cfg.CAPTURE_MODE)
            save_debug("verification_answer_mismatch.png", frame)
            logger.warning(
                "Answer field did not become %s on attempt %s/%s.",
                expected_text,
                attempt,
                max_attempts,
            )
            matched = False
            break

        if not matched:
            continue

        final_frame = capture_window(hwnd, cfg.CAPTURE_MODE)
        final_digits, final_confidence = read_answer_digits(final_frame, dialog)
        if final_digits == expected_answer:
            logger.info(
                "Answer confirmed in field: %s confidence=%.3f",
                final_digits,
                final_confidence,
            )
            return True

        save_debug("verification_answer_mismatch.png", final_frame)
        logger.warning(
            "Final answer mismatch on attempt %s/%s: expected=%s actual=%s "
            "confidence=%.3f",
            attempt,
            max_attempts,
            expected_answer,
            final_digits or "<empty>",
            final_confidence,
        )

    logger.error(
        "Answer field did not become %s after %s retries.",
        expected_answer,
        cfg.VERIFY_ANSWER_RETRY_ATTEMPTS,
    )
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ROX Gardening Bot")
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


def save_debug(name: str, frame) -> None:
    if not cfg.SAVE_DEBUG_FRAMES:
        return
    cfg.DEBUG_DIR.mkdir(exist_ok=True)
    cv2.imwrite(str(cfg.DEBUG_DIR / name), frame)


def answer_verification(hwnd: int, frame, dialog) -> bool:
    deadline = time.monotonic() + cfg.VERIFY_READ_TIMEOUT_SECONDS
    equation = None
    previous_expression = None
    matching_reads = 0
    latest_frame = frame
    latest_dialog = dialog

    while time.monotonic() < deadline:
        check_stop_key()
        current = read_equation(latest_frame, latest_dialog)
        if current is not None and current.confidence >= cfg.EQUATION_MIN_CONFIDENCE:
            if current.expression == previous_expression:
                matching_reads += 1
            else:
                previous_expression = current.expression
                matching_reads = 1
            logger.info(
                "Verification read: expression=%s confidence=%.3f stable=%s/%s",
                current.expression,
                current.confidence,
                matching_reads,
                cfg.VERIFY_REQUIRED_READS,
            )
            if matching_reads >= cfg.VERIFY_REQUIRED_READS:
                equation = current
                break
        else:
            previous_expression = None
            matching_reads = 0

        interruptible_sleep(cfg.VERIFY_READ_INTERVAL_SECONDS)
        latest_frame = capture_window(hwnd, cfg.CAPTURE_MODE)
        refreshed_dialog = find_verification_dialog(latest_frame)
        if refreshed_dialog is not None:
            latest_dialog = refreshed_dialog

    if equation is None:
        logger.error(
            "Verification equation remained unreadable for %.1f seconds.",
            cfg.VERIFY_READ_TIMEOUT_SECONDS,
        )
        save_debug("verification_unreadable.png", latest_frame)
        return False

    logger.info(
        "Verification equation: %s=%s confidence=%.3f",
        equation.expression,
        equation.answer,
        equation.confidence,
    )
    click_client(
        hwnd,
        latest_dialog.relative_point(cfg.VERIFY_INPUT_POINT),
        cfg.CLICK_MODE,
    )
    interruptible_sleep(cfg.VERIFY_OPEN_DELAY_SECONDS)
    if not enter_answer_with_retries(hwnd, latest_dialog, equation.answer):
        return False

    click_client(hwnd, keypad_point(latest_dialog, "enter"), cfg.CLICK_MODE)
    interruptible_sleep(cfg.KEYPAD_CLICK_INTERVAL_SECONDS)
    click_client(
        hwnd,
        latest_dialog.relative_point(cfg.VERIFY_CONFIRM_POINT),
        cfg.CLICK_MODE,
    )
    interruptible_sleep(cfg.VERIFY_RESULT_WAIT_SECONDS)
    return True


def inspect_frame(hwnd: int) -> None:
    activate_window(hwnd)
    frame = capture_window(hwnd, cfg.CAPTURE_MODE)
    garden = inspect_garden_button(frame, cfg.GARDEN_BUTTON_POINT)
    output = frame.copy()
    color = (0, 255, 0) if garden.visible else (0, 0, 255)
    cv2.rectangle(
        output,
        (garden.rect.left, garden.rect.top),
        (
            garden.rect.left + garden.rect.width,
            garden.rect.top + garden.rect.height,
        ),
        color,
        3,
    )
    logger.info(
        "Garden button: visible=%s gold=%.3f white=%.3f",
        garden.visible,
        garden.gold_ratio,
        garden.white_ratio,
    )

    dialog = find_verification_dialog(frame)
    if dialog is None:
        logger.info("No verification dialog detected.")
    else:
        cv2.rectangle(
            output,
            (dialog.left, dialog.top),
            (dialog.left + dialog.width, dialog.top + dialog.height),
            (0, 0, 255),
            3,
        )
        equation = read_equation(frame, dialog)
        if equation is None:
            logger.warning("Verification dialog found, equation unreadable.")
        else:
            logger.info(
                "Equation: %s=%s confidence=%.3f",
                equation.expression,
                equation.answer,
                equation.confidence,
            )
    save_debug("inspect.png", output)
    logger.info("Inspection saved to %s", cfg.DEBUG_DIR / "inspect.png")


def main() -> None:
    args = parse_args()
    configure_logging()
    cfg.DEBUG_DIR.mkdir(exist_ok=True)
    if args.list_windows:
        matches = find_windows(cfg.WINDOW_TITLE_KEYWORDS)
        if not matches:
            logger.info("No visible ROX windows found.")
            return
        logger.info("Visible ROX windows:")
        for index, match in enumerate(matches, start=1):
            bounds = get_client_bounds(match.hwnd)
            status = (
                "ready"
                if bounds.width > 0 and bounds.height > 0
                else "minimized"
            )
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
        return

    hwnd, title = find_window(
        cfg.WINDOW_TITLE_KEYWORDS,
        hwnd=args.hwnd,
        window_index=args.window_index,
    )
    if cfg.CLICK_MODE == "sendinput":
        activate_window(hwnd)
    bounds = get_client_bounds(hwnd)
    logger.info("=== ROX Gardening Bot started ===")
    logger.info("Game window: %s (handle=%s)", title, hwnd)
    logger.info("Client size: %sx%s", bounds.width, bounds.height)
    logger.info("Capture=%s, click=%s", cfg.CAPTURE_MODE, cfg.CLICK_MODE)
    logger.info("Press %s to stop.", cfg.STOP_KEY_NAME)
    if args.inspect:
        inspect_frame(hwnd)
        return

    garden_point = ratio_point(
        (bounds.width, bounds.height),
        cfg.GARDEN_BUTTON_POINT,
    )
    next_click_at = 0.0
    garden_visible_frames = 0
    last_diagnostic = 0.0

    try:
        while True:
            check_stop_key()
            now = time.monotonic()
            frame = capture_window(hwnd, cfg.CAPTURE_MODE)

            dialog = find_verification_dialog(frame)
            if dialog is not None:
                logger.warning(
                    "Verification dialog detected: x=%s y=%s w=%s h=%s",
                    dialog.left,
                    dialog.top,
                    dialog.width,
                    dialog.height,
                )
                save_debug("verification_detected.png", frame)
                if not answer_verification(hwnd, frame, dialog):
                    logger.error(
                        "Stopped to avoid submitting an uncertain answer."
                    )
                    return
                next_click_at = 0.0
                garden_visible_frames = 0
                continue

            garden = inspect_garden_button(frame, cfg.GARDEN_BUTTON_POINT)
            if garden.visible:
                garden_visible_frames += 1
            else:
                garden_visible_frames = 0

            if (
                garden_visible_frames >= cfg.GARDEN_REQUIRED_FRAMES
                and now >= next_click_at
            ):
                logger.info(
                    "Garden button detected: gold=%.3f white=%.3f",
                    garden.gold_ratio,
                    garden.white_ratio,
                )
                click_client(hwnd, garden_point, cfg.CLICK_MODE)
                next_click_at = now + cfg.GARDEN_CLICK_COOLDOWN_SECONDS
                garden_visible_frames = 0

            if now - last_diagnostic >= cfg.DIAGNOSTIC_INTERVAL_SECONDS:
                logger.info(
                    "Garden scan: visible=%s gold=%.3f white=%.3f",
                    garden.visible,
                    garden.gold_ratio,
                    garden.white_ratio,
                )
                last_diagnostic = now
            interruptible_sleep(cfg.POLL_INTERVAL_SECONDS)
    except (KeyboardInterrupt, StopRequested):
        logger.info("Stopped by user.")
    finally:
        release_mouse_buttons()


if __name__ == "__main__":
    main()
