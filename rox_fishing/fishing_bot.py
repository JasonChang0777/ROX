from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import time
from enum import Enum, auto

import cv2

import config as cfg
from vision import (
    bait_foreground_similarity,
    bite_change_ratio,
    classify_bait_scores,
    crop_local_ratio,
    crop_ratio,
    green_ratio,
    infinity_symbol_similarity,
    load_template,
    locate_template,
)
from window_capture import (
    activate_window,
    capture_client_region,
    capture_window,
    click_client,
    find_window,
    find_windows,
    get_client_bounds,
    get_monitor_bounds,
    is_key_down,
    is_window_foreground,
    ratio_point,
)


logger = logging.getLogger(__name__)


class BotState(Enum):
    CHECKING_BAIT = auto()
    CASTING = auto()
    WAITING_FOR_BITE = auto()
    WAITING_FOR_RESULT = auto()
    OUT_OF_BAIT = auto()


class StopRequested(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ROX Fishing Bot")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--window-index",
        type=int,
        help="使用 --list-windows 顯示的序號選擇 ROX 視窗",
    )
    selection.add_argument(
        "--hwnd",
        type=int,
        help="使用 Windows 視窗 handle 選擇 ROX 視窗",
    )
    parser.add_argument(
        "--list-windows",
        action="store_true",
        help="列出目前可見的 ROX 視窗後結束",
    )
    return parser.parse_args()


def check_stop_key() -> None:
    if is_key_down(cfg.STOP_VIRTUAL_KEY):
        raise StopRequested


def save_target(frame, region, name: str) -> None:
    if not cfg.SAVE_DEBUG_FRAMES:
        return
    output = frame.copy()
    height, width = region.image.shape[:2]
    cv2.rectangle(
        output,
        (region.left, region.top),
        (region.left + width, region.top + height),
        (0, 0, 255),
        3,
    )
    cv2.circle(output, region.center, 8, (0, 255, 255), -1)
    cv2.imwrite(str(cfg.DEBUG_DIR / name), output)


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


def locate_bait_panel(frame, template):
    match = locate_template(
        frame,
        template,
        cfg.BAIT_PANEL_SEARCH_ROI,
        cfg.BAIT_PANEL_TEMPLATE_SCALES,
    )
    if match is None or match.score < cfg.BAIT_PANEL_MATCH_THRESHOLD:
        return None
    return match


def region_ratio(frame, region) -> tuple[float, float, float, float]:
    frame_height, frame_width = frame.shape[:2]
    region_height, region_width = region.image.shape[:2]
    return (
        region.left / frame_width,
        region.top / frame_height,
        (region.left + region_width) / frame_width,
        (region.top + region_height) / frame_height,
    )


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

    empty_template = load_template(cfg.EMPTY_BAIT_TEMPLATE)
    if empty_template is None:
        raise RuntimeError(
            f"Missing bundled bait template: {cfg.EMPTY_BAIT_TEMPLATE}"
        )
    empty_icon_template = crop_local_ratio(
        empty_template,
        cfg.EMPTY_BAIT_ICON_CROP,
    )

    hwnd, title = find_window(
        cfg.WINDOW_TITLE_KEYWORDS,
        hwnd=args.hwnd,
        window_index=args.window_index,
    )
    activate_window(hwnd)
    logger.info("=== ROX Fishing Bot started ===")
    logger.info("Game window: %s (handle=%s)", title, hwnd)
    logger.info("Capture=%s, click=%s", cfg.CAPTURE_MODE, cfg.CLICK_MODE)
    logger.info(
        "Pause screen capture in background: %s",
        cfg.PAUSE_SCREEN_CAPTURE_WHEN_BACKGROUND,
    )
    logger.info("Press %s to stop.", cfg.STOP_KEY_NAME)
    logger.info(
        "Fixed cast point ratio: x=%.4f, y=%.4f",
        cfg.CAST_BUTTON_POINT[0],
        cfg.CAST_BUTTON_POINT[1],
    )
    initial_bounds = get_client_bounds(hwnd)
    monitor_bounds = get_monitor_bounds(hwnd)
    logger.info(
        "Client bounds: left=%s top=%s size=%sx%s",
        initial_bounds.left,
        initial_bounds.top,
        initial_bounds.width,
        initial_bounds.height,
    )
    logger.info(
        "Monitor bounds: left=%s top=%s size=%sx%s",
        monitor_bounds.left,
        monitor_bounds.top,
        monitor_bounds.width,
        monitor_bounds.height,
    )
    button_size = max(
        80,
        round(
            min(initial_bounds.width, initial_bounds.height)
            * cfg.GREEN_BUTTON_SIZE_RATIO
        ),
    )
    logger.info("Fast green ROI: %sx%s", button_size, button_size)

    startup_frame = capture_window(hwnd, cfg.CAPTURE_MODE)
    bait_match = locate_bait_panel(startup_frame, empty_template)
    if bait_match is None:
        bait_panel_roi = cfg.BAIT_ICON_ROI
        logger.warning(
            "Dynamic bait panel location failed; using fallback ROI=%s",
            bait_panel_roi,
        )
    else:
        bait_panel_roi = region_ratio(startup_frame, bait_match.region)
        logger.info(
            "Dynamic bait panel: score=%.3f roi=(%.4f, %.4f, %.4f, %.4f) "
            "size=%sx%s",
            bait_match.score,
            *bait_panel_roi,
            bait_match.region.image.shape[1],
            bait_match.region.image.shape[0],
        )
        save_target(
            startup_frame,
            bait_match.region,
            "bait_panel_target.png",
        )

    state = BotState.CHECKING_BAIT
    previous_state = state
    last_action = 0.0
    last_diagnostic = 0.0
    green_hits = 0
    green_peak = 0.0
    bite_baseline = None
    empty_hits = 0
    bait_present_hits = 0
    unknown_bait_hits = 0
    capture_paused = False

    try:
        while True:
            check_stop_key()
            if (
                cfg.CAPTURE_MODE == "screen"
                and cfg.PAUSE_SCREEN_CAPTURE_WHEN_BACKGROUND
                and not is_window_foreground(hwnd)
            ):
                if not capture_paused:
                    logger.warning(
                        "ROX is not foreground; capture paused to avoid "
                        "reading an overlapping window."
                    )
                    capture_paused = True
                time.sleep(0.1)
                continue
            if capture_paused:
                logger.info("ROX returned to foreground; capture resumed.")
                capture_paused = False

            now = time.perf_counter()
            bounds = get_client_bounds(hwnd)
            cast_point = ratio_point(
                (bounds.width, bounds.height),
                cfg.CAST_BUTTON_POINT,
            )

            if state == BotState.WAITING_FOR_BITE:
                if (
                    bite_baseline is None
                    and now - last_action >= cfg.BITE_BASELINE_DELAY_SECONDS
                ):
                    bite_baseline = capture_client_region(
                        hwnd,
                        cast_point,
                        (button_size, button_size),
                    )
                    if cfg.SAVE_DEBUG_FRAMES:
                        cv2.imwrite(
                            str(cfg.DEBUG_DIR / "bite_baseline.png"),
                            bite_baseline,
                        )
                    logger.info(
                        "Bite baseline captured %.1fs after cast.",
                        now - last_action,
                    )

                lift_image = capture_client_region(
                    hwnd,
                    cast_point,
                    (button_size, button_size),
                )
                green = green_ratio(lift_image)
                bite_change = bite_change_ratio(lift_image, bite_baseline)
                green_hits = (
                    green_hits + 1
                    if bite_change >= cfg.BITE_CHANGE_RATIO
                    else 0
                )
                if bite_change > green_peak:
                    green_peak = bite_change
                    if cfg.SAVE_DEBUG_FRAMES:
                        cv2.imwrite(
                            str(cfg.DEBUG_DIR / "green_peak.png"),
                            lift_image,
                        )

                if now - last_diagnostic >= cfg.DIAGNOSTIC_INTERVAL_SECONDS:
                    if cfg.SAVE_DEBUG_FRAMES:
                        cv2.imwrite(
                            str(cfg.DEBUG_DIR / "bite_latest.png"),
                            lift_image,
                        )
                    logger.info(
                        "Detect: state=%s bite=%.3f green=%.3f "
                        "baseline=%s button_center=%s debug=bite_latest.png",
                        state.name,
                        bite_change,
                        green,
                        bite_baseline is not None,
                        cast_point,
                    )
                    last_diagnostic = now

                if (
                    green_hits >= cfg.GREEN_REQUIRED_FRAMES
                    and now - last_action >= cfg.LIFT_COOLDOWN_SECONDS
                ):
                    click_client(
                        hwnd,
                        cast_point,
                        cfg.CLICK_MODE,
                        count=cfg.LIFT_CLICK_COUNT,
                        interval=cfg.CLICK_INTERVAL_SECONDS,
                    )
                    last_action = now
                    green_hits = 0
                    green_peak = 0.0
                    bite_baseline = None
                    state = BotState.WAITING_FOR_RESULT
                    logger.info(
                        "Lift click: bite=%.3f green=%.3f, client=%s",
                        bite_change,
                        green,
                        cast_point,
                    )

                if state != previous_state:
                    logger.info(
                        "State: %s -> %s",
                        previous_state.name,
                        state.name,
                    )
                    previous_state = state

                time.sleep(cfg.POLL_INTERVAL_SECONDS)
                continue

            if state == BotState.WAITING_FOR_RESULT:
                if now - last_diagnostic >= cfg.DIAGNOSTIC_INTERVAL_SECONDS:
                    logger.info("Detect: state=%s", state.name)
                    last_diagnostic = now
                if now - last_action >= cfg.RESULT_WAIT_SECONDS:
                    empty_hits = 0
                    bait_present_hits = 0
                    state = BotState.CHECKING_BAIT
                    logger.info(
                        "State: %s -> %s",
                        previous_state.name,
                        state.name,
                    )
                    previous_state = state
                time.sleep(cfg.POLL_INTERVAL_SECONDS)
                continue

            if state == BotState.CASTING:
                bite_baseline = None
                click_client(hwnd, cast_point, cfg.CLICK_MODE)
                last_action = now
                state = BotState.WAITING_FOR_BITE
                green_hits = 0
                green_peak = 0.0
                logger.info(
                    "Cast click: client=%s, waiting for button to settle",
                    cast_point,
                )
                logger.info(
                    "State: %s -> %s",
                    previous_state.name,
                    state.name,
                )
                previous_state = state
                time.sleep(cfg.POLL_INTERVAL_SECONDS)
                continue

            # Bait is checked only here, immediately before entering CASTING.
            frame = capture_window(hwnd, cfg.CAPTURE_MODE)

            bait_region = crop_ratio(frame, bait_panel_roi)
            bait_icon = crop_local_ratio(
                bait_region.image,
                cfg.EMPTY_BAIT_ICON_CROP,
            )
            worm_score = bait_foreground_similarity(
                bait_icon,
                empty_icon_template,
            )
            infinity_score = infinity_symbol_similarity(
                bait_icon,
                empty_icon_template,
            )
            bait_kind = classify_bait_scores(worm_score, infinity_score)
            empty_hits = (
                empty_hits + 1 if bait_kind == "starter" else 0
            )
            bait_present_hits = (
                bait_present_hits + 1 if bait_kind == "limited" else 0
            )
            if bait_kind == "unknown":
                empty_hits = 0
                bait_present_hits = 0
                unknown_bait_hits += 1
            else:
                unknown_bait_hits = 0

            if unknown_bait_hits >= cfg.BAIT_RELOCATE_UNKNOWN_FRAMES:
                relocated = locate_bait_panel(frame, empty_template)
                unknown_bait_hits = 0
                if relocated is not None:
                    bait_panel_roi = region_ratio(frame, relocated.region)
                    logger.info(
                        "Bait panel relocated: score=%.3f "
                        "roi=(%.4f, %.4f, %.4f, %.4f)",
                        relocated.score,
                        *bait_panel_roi,
                    )
                    save_target(
                        frame,
                        relocated.region,
                        "bait_panel_target.png",
                    )
                    continue
                logger.warning(
                    "Bait panel relocation failed; waiting for a clear frame."
                )

            if now - last_diagnostic >= cfg.DIAGNOSTIC_INTERVAL_SECONDS:
                logger.info(
                    f"Detect: state={state.name} button_center={cast_point} "
                    f"worm={worm_score:.3f} infinity={infinity_score:.3f} "
                    f"bait={bait_kind}"
                )
                last_diagnostic = now

            if empty_hits >= cfg.EMPTY_BAIT_REQUIRED_FRAMES:
                state = BotState.OUT_OF_BAIT

            elif (
                state == BotState.CHECKING_BAIT
                and bait_present_hits >= cfg.BAIT_PRESENT_REQUIRED_FRAMES
            ):
                empty_hits = 0
                bait_present_hits = 0
                state = BotState.CASTING
                logger.info(
                    "Limited bait confirmed: worm=%.3f infinity=%.3f",
                    worm_score,
                    infinity_score,
                )

            if state != previous_state:
                logger.info("State: %s -> %s", previous_state.name, state.name)
                previous_state = state

            if state == BotState.OUT_OF_BAIT:
                if cfg.SAVE_DEBUG_FRAMES:
                    cv2.imwrite(
                        str(cfg.DEBUG_DIR / "out_of_bait.png"),
                        bait_icon,
                    )
                logger.info(
                    "Starter bait detected. Limited bait is exhausted; stopping."
                )
                break

            time.sleep(cfg.POLL_INTERVAL_SECONDS)
    except (KeyboardInterrupt, StopRequested):
        logger.info("Stopped by user.")
    finally:
        cv2.destroyAllWindows()
        logger.info("=== ROX Fishing Bot stopped ===")


if __name__ == "__main__":
    main()
