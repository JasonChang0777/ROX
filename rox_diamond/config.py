import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_DIR))
    DATA_DIR = Path(sys.executable).resolve().parent
else:
    RESOURCE_DIR = PROJECT_DIR
    DATA_DIR = PROJECT_DIR

DEBUG_DIR = DATA_DIR / "debug"
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "diamond_bot.log"

WINDOW_TITLE_KEYWORDS = ("ROX", "RöX", "R?X")
REFERENCE_SIZE = (1280, 720)

STOP_KEY_NAME = "Q"
STOP_VIRTUAL_KEY = 0x51

CAPTURE_MODE = "screen"
# Trading House purchase buttons do not reliably accept PostMessage background
# clicks, so use the same physical SendInput mode as the gardening bot.
CLICK_MODE = "sendinput"
RESTORE_CURSOR_AFTER_CLICK = True

# Regions are ratios of the ROX client area.
MARKET_BUY_BUTTON_SEARCH_ROI = (0.70, 0.25, 0.97, 0.52)
BUY_DIALOG_RECT = (0.160, 0.145, 0.490, 0.930)
BUY_DIALOG_CLOSE_SEARCH_ROI = (0.42, 0.10, 0.53, 0.24)
TODAY_LIMIT_ROI = (0.665, 0.615, 0.82, 0.665)

QUANTITY_FIELD_POINT = (0.735, 0.492)
PURCHASE_BUTTON_POINT = (0.490, 0.885)
KEYPAD_COLUMN_RATIOS = (0.770, 0.945, 1.120, 1.290)
KEYPAD_ROW_RATIOS = (0.373, 0.503, 0.634)
KEYPAD_LAYOUT = (
    ("1", "2", "3", "clear"),
    ("4", "5", "6", "0"),
    ("7", "8", "9", "enter"),
)

MAX_QUANTITY_DIGIT = "9"
MAX_QUANTITY_DIGIT_COUNT = 5
# Set True for normal runs. Keep False when validating the keypad/purchase flow
# after the daily limit has already reached zero.
STOP_WHEN_TODAY_LIMIT_ZERO = True

POLL_INTERVAL_SECONDS = 0.10
ACTION_INTERVAL_SECONDS = 0.50
KEYPAD_DIGIT_INTERVAL_SECONDS = 0.12
DIALOG_WAIT_SECONDS = 2.00
AFTER_PURCHASE_WAIT_SECONDS = 1.00
DIAGNOSTIC_INTERVAL_SECONDS = 2.00

BUY_BUTTON_REQUIRED_FRAMES = 2
ORANGE_BUTTON_MIN_AREA = 700
ORANGE_BUTTON_MIN_ASPECT = 2.2
ORANGE_BUTTON_MAX_ASPECT = 7.5
PINK_CLOSE_MIN_AREA = 250

DIGIT_MIN_CONFIDENCE = 0.18
TODAY_LIMIT_REQUIRED_READS = 2

FOREGROUND_SETTLE_SECONDS = 0.10
MOUSE_MOVE_SETTLE_SECONDS = 0.05
MOUSE_PRESS_SECONDS = 0.08
MOUSE_RELEASE_SETTLE_SECONDS = 0.05

SAVE_DEBUG_FRAMES = True
