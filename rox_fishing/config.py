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
LOG_FILE = LOG_DIR / "fishing_bot.log"

# The game title may use either a plain O or an umlaut depending on the client.
WINDOW_TITLE_KEYWORDS = ("ROX", "RÖX")

# Fixed fishing button center as a ratio of the ROX client area.
CAST_BUTTON_POINT = (0.84921875, 0.7333333333333333)

# Global stop hotkey. Q works while the game window is focused.
STOP_KEY_NAME = "Q"
STOP_VIRTUAL_KEY = 0x51

# Regions are (left, top, right, bottom) ratios of the game client area.
BAIT_ICON_ROI = (0.65, 0.84, 0.75, 0.99)
BAIT_PANEL_SEARCH_ROI = (0.40, 0.65, 0.95, 1.00)
BAIT_PANEL_TEMPLATE_SCALES = (
    0.65,
    0.75,
    0.85,
    0.95,
    1.00,
    1.10,
    1.20,
    1.30,
    1.40,
    1.50,
    1.65,
    1.80,
)
BAIT_PANEL_MATCH_THRESHOLD = 0.32
BAIT_RELOCATE_UNKNOWN_FRAMES = 60

EMPTY_BAIT_TEMPLATE = TEMPLATE_DIR / "empty_bait.png"

# OpenCV HSV ranges. Hue is 0-179.
GREEN_HSV_LOWER = (20, 55, 80)
GREEN_HSV_UPPER = (92, 255, 255)
GREEN_PIXEL_RATIO = 0.075
GREEN_REQUIRED_FRAMES = 2
GREEN_BUTTON_SIZE_RATIO = 0.20
# Compare the active lift button with the same area captured before casting.
# This rejects scenery that was already green before the button changed.
BITE_CHANGE_RATIO = 0.10
BITE_GREEN_GAIN = 28
BITE_BRIGHTNESS_GAIN = 12

EMPTY_BAIT_WORM_THRESHOLD = 0.52
EMPTY_BAIT_INFINITY_THRESHOLD = 0.72
# Limited bait must be clearly different from both starter-bait features.
# Scores between these bands are unknown and must never trigger a cast.
LIMITED_BAIT_WORM_MAX = 0.65
LIMITED_BAIT_INFINITY_MAX = 0.55
EMPTY_BAIT_REQUIRED_FRAMES = 5
BAIT_PRESENT_REQUIRED_FRAMES = 5
# The calibrated bait image contains the starter bait on the left and the
# fishing rod on the right. Compare only the starter bait icon.
EMPTY_BAIT_ICON_CROP = (0.00, 0.00, 0.56, 0.95)
# The starter bait count is an infinity symbol at the icon's lower right.
EMPTY_BAIT_INFINITY_CROP = (0.62, 0.62, 1.00, 0.96)

POLL_INTERVAL_SECONDS = 0.010
DIAGNOSTIC_INTERVAL_SECONDS = 1.0
CAST_COOLDOWN_SECONDS = 2.0
BITE_BASELINE_DELAY_SECONDS = 1.0
LIFT_COOLDOWN_SECONDS = 1.5
RESULT_WAIT_SECONDS = 4.0

LIFT_CLICK_COUNT = 3
CLICK_INTERVAL_SECONDS = 0.010
FOREGROUND_SETTLE_SECONDS = 0.100
MOUSE_MOVE_SETTLE_SECONDS = 0.050
MOUSE_PRESS_SECONDS = 0.120
MOUSE_RELEASE_SETTLE_SECONDS = 0.100

# Reliable mode: use Windows SendInput. This briefly uses the real cursor and
# requires ROX and this process to run at the same privilege level.
CLICK_MODE = "sendinput"
RESTORE_CURSOR_AFTER_CLICK = True
# Restore the previously focused window after each click. This keeps fishing
# scans mostly in the background and only focuses ROX for the actual action.
RESTORE_FOREGROUND_AFTER_CLICK = True
FOCUS_MESSAGE_SETTLE_SECONDS = 0.050

# ROX uses DirectX and commonly returns a black frame through PrintWindow.
# Screen capture requires the game to remain visible and not be minimized.
CAPTURE_MODE = "screen"
# When disabled, screen capture keeps scanning even if ROX is not foreground.
# Use only when the target ROX window remains visible and is not covered.
PAUSE_SCREEN_CAPTURE_WHEN_BACKGROUND = False

# Screen capture must not be covered by the OpenCV preview window.
SHOW_PREVIEW = False
SAVE_DEBUG_FRAMES = True
