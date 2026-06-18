import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_DIR))
    DATA_DIR = Path(sys.executable).resolve().parent
else:
    RESOURCE_DIR = PROJECT_DIR
    DATA_DIR = PROJECT_DIR

TEMPLATE_DIR = RESOURCE_DIR / "templates"
DEBUG_DIR = DATA_DIR / "debug"
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "gardening_bot.log"

# The game title can contain either a plain O or an umlaut.
WINDOW_TITLE_KEYWORDS = ("ROX", "RÖX")

# ROX is most reliable when the client stays visible at 1280x720. Coordinates
# below are ratios, so small window-size differences remain supported.
REFERENCE_SIZE = (1280, 720)
CAPTURE_MODE = "screen"
# ROX ignores PostMessage background clicks, so physical SendInput is required.
# Restore the cursor immediately after each click to minimize interruption.
CLICK_MODE = "sendinput"
RESTORE_CURSOR_AFTER_CLICK = True

# Global stop hotkey. Q works while the game window is focused.
STOP_KEY_NAME = "Q"
STOP_VIRTUAL_KEY = 0x51

# Gardening button center in the client area.
GARDEN_BUTTON_POINT = (0.627, 0.402)
GARDEN_BUTTON_SIZE_RATIO = 0.105
GARDEN_GOLD_PIXEL_RATIO = 0.16
GARDEN_WHITE_PIXEL_RATIO = 0.035
GARDEN_REQUIRED_FRAMES = 2
GARDEN_CLICK_COOLDOWN_SECONDS = 1.5

VERIFY_SEARCH_ROI = (0.12, 0.15, 0.88, 0.88)
VERIFY_DIALOG_MIN_AREA_RATIO = 0.10
VERIFY_DIALOG_MAX_AREA_RATIO = 0.55
VERIFY_DIALOG_MIN_ASPECT = 1.20
VERIFY_DIALOG_MAX_ASPECT = 2.20

# Points are relative to the detected verification dialog. The keypad opens
# to the right and can extend beyond the dialog bounds.
VERIFY_INPUT_POINT = (0.50, 0.53)
VERIFY_CONFIRM_POINT = (0.50, 0.85)
VERIFY_ANSWER_ROI = (0.50, 0.48, 0.66, 0.60)
# Calibrated from the visible in-game keypad at a 1280x720 client size.
KEYPAD_COLUMN_RATIOS = (0.912, 1.036, 1.160, 1.286)
KEYPAD_ROW_RATIOS = (0.55, 0.78, 1.01)
KEYPAD_LAYOUT = (
    ("1", "2", "3", "clear"),
    ("4", "5", "6", "0"),
    ("7", "8", "9", "enter"),
)

POLL_INTERVAL_SECONDS = 0.10
VERIFY_OPEN_DELAY_SECONDS = 0.50
KEYPAD_CLICK_INTERVAL_SECONDS = 0.30
ANSWER_CHECK_TIMEOUT_SECONDS = 1.0
ANSWER_CHECK_INTERVAL_SECONDS = 0.10
VERIFY_ANSWER_RETRY_ATTEMPTS = 2
VERIFY_RESULT_WAIT_SECONDS = 1.0
VERIFY_READ_TIMEOUT_SECONDS = 4.0
VERIFY_READ_INTERVAL_SECONDS = 0.20
VERIFY_REQUIRED_READS = 2
DIAGNOSTIC_INTERVAL_SECONDS = 2.0

EQUATION_MIN_CONFIDENCE = 0.42
SAVE_DEBUG_FRAMES = True

FOREGROUND_SETTLE_SECONDS = 0.10
MOUSE_MOVE_SETTLE_SECONDS = 0.05
MOUSE_PRESS_SECONDS = 0.12
MOUSE_RELEASE_SETTLE_SECONDS = 0.10
