from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

import config as cfg


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        return self.left + self.width // 2, self.top + self.height // 2

    def relative_point(self, point: tuple[float, float]) -> tuple[int, int]:
        return (
            round(self.left + self.width * point[0]),
            round(self.top + self.height * point[1]),
        )

    def relative_rect(self, roi: tuple[float, float, float, float]) -> "Rect":
        left = round(self.left + self.width * roi[0])
        top = round(self.top + self.height * roi[1])
        right = round(self.left + self.width * roi[2])
        bottom = round(self.top + self.height * roi[3])
        return Rect(left, top, max(1, right - left), max(1, bottom - top))


@dataclass(frozen=True)
class ButtonMatch:
    rect: Rect
    orange_ratio: float


def crop_ratio(
    frame: np.ndarray,
    roi: tuple[float, float, float, float],
) -> tuple[np.ndarray, int, int]:
    height, width = frame.shape[:2]
    left = max(0, min(width - 1, round(width * roi[0])))
    top = max(0, min(height - 1, round(height * roi[1])))
    right = max(left + 1, min(width, round(width * roi[2])))
    bottom = max(top + 1, min(height, round(height * roi[3])))
    return np.ascontiguousarray(frame[top:bottom, left:right]), left, top


def fixed_dialog_rect(frame: np.ndarray) -> Rect:
    height, width = frame.shape[:2]
    left = round(width * cfg.BUY_DIALOG_RECT[0])
    top = round(height * cfg.BUY_DIALOG_RECT[1])
    right = round(width * cfg.BUY_DIALOG_RECT[2])
    bottom = round(height * cfg.BUY_DIALOG_RECT[3])
    return Rect(left, top, max(1, right - left), max(1, bottom - top))


def find_market_buy_button(frame: np.ndarray) -> ButtonMatch | None:
    search, offset_x, offset_y = crop_ratio(frame, cfg.MARKET_BUY_BUTTON_SEARCH_ROI)
    hsv = cv2.cvtColor(search, cv2.COLOR_BGR2HSV)
    orange = cv2.inRange(
        hsv,
        np.array((5, 55, 135), dtype=np.uint8),
        np.array((35, 255, 255), dtype=np.uint8),
    )
    orange = cv2.morphologyEx(
        orange,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (13, 7)),
        iterations=2,
    )
    contours, _ = cv2.findContours(
        orange,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    best: tuple[float, ButtonMatch] | None = None
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = width * height
        if area < cfg.ORANGE_BUTTON_MIN_AREA:
            continue
        aspect = width / max(1, height)
        if not cfg.ORANGE_BUTTON_MIN_ASPECT <= aspect <= cfg.ORANGE_BUTTON_MAX_ASPECT:
            continue
        image = orange[y : y + height, x : x + width]
        ratio = float(np.count_nonzero(image) / max(1, image.size))
        rect = Rect(offset_x + x, offset_y + y, width, height)
        score = area * ratio
        candidate = ButtonMatch(rect, ratio)
        if best is None or score > best[0]:
            best = (score, candidate)
    return best[1] if best is not None else None


def find_purchase_dialog(frame: np.ndarray) -> Rect | None:
    search, offset_x, offset_y = crop_ratio(frame, cfg.BUY_DIALOG_CLOSE_SEARCH_ROI)
    hsv = cv2.cvtColor(search, cv2.COLOR_BGR2HSV)
    pink_low = cv2.inRange(
        hsv,
        np.array((160, 65, 135), dtype=np.uint8),
        np.array((179, 255, 255), dtype=np.uint8),
    )
    pink_high = cv2.inRange(
        hsv,
        np.array((0, 65, 135), dtype=np.uint8),
        np.array((8, 255, 255), dtype=np.uint8),
    )
    mask = cv2.bitwise_or(pink_low, pink_high)
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
        iterations=2,
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < cfg.PINK_CLOSE_MIN_AREA:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        aspect = width / max(1, height)
        if 0.65 <= aspect <= 1.45:
            return fixed_dialog_rect(frame)
    return None


def _normalize_glyph(mask: np.ndarray) -> np.ndarray:
    points = cv2.findNonZero(mask)
    canvas = np.zeros((48, 32), dtype=np.uint8)
    if points is None:
        return canvas
    x, y, width, height = cv2.boundingRect(points)
    glyph = mask[y : y + height, x : x + width]
    scale = min(26 / max(1, width), 42 / max(1, height))
    resized = cv2.resize(
        glyph,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    top = (canvas.shape[0] - resized.shape[0]) // 2
    left = (canvas.shape[1] - resized.shape[1]) // 2
    canvas[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
    return canvas


def _synthetic_digit_templates() -> dict[str, list[np.ndarray]]:
    templates: dict[str, list[np.ndarray]] = {digit: [] for digit in "0123456789"}
    fonts = (
        cv2.FONT_HERSHEY_SIMPLEX,
        cv2.FONT_HERSHEY_DUPLEX,
        cv2.FONT_HERSHEY_COMPLEX,
    )
    for digit in templates:
        for font in fonts:
            for thickness in (1, 2, 3):
                image = np.zeros((72, 56), dtype=np.uint8)
                size, _ = cv2.getTextSize(digit, font, 1.5, thickness)
                origin = (
                    (image.shape[1] - size[0]) // 2,
                    (image.shape[0] + size[1]) // 2,
                )
                cv2.putText(
                    image,
                    digit,
                    origin,
                    font,
                    1.5,
                    255,
                    thickness,
                    cv2.LINE_AA,
                )
                _, image = cv2.threshold(image, 80, 255, cv2.THRESH_BINARY)
                templates[digit].append(_normalize_glyph(image))
    return templates


DIGIT_TEMPLATES = _synthetic_digit_templates()


def _classify_digit(glyph: np.ndarray) -> tuple[str, float]:
    normalized = _normalize_glyph(glyph)
    best_digit = ""
    best_score = -1.0
    for digit, templates in DIGIT_TEMPLATES.items():
        for template in templates:
            score = float(
                cv2.matchTemplate(
                    normalized,
                    template,
                    cv2.TM_CCOEFF_NORMED,
                )[0, 0]
            )
            if score > best_score:
                best_digit = digit
                best_score = score
    return best_digit, max(0.0, best_score)


def read_dark_digits(image: np.ndarray) -> tuple[str | None, float]:
    if image.size == 0:
        return None, 0.0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = cv2.inRange(gray, 0, 145)
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        np.ones((2, 2), dtype=np.uint8),
    )
    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    boxes: list[tuple[int, int, int, int]] = []
    image_height, image_width = mask.shape
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if height < image_height * 0.22 or width < 2:
            continue
        if height > image_height * 0.95 or width > image_width * 0.45:
            continue
        boxes.append((x, y, width, height))
    boxes.sort(key=lambda box: box[0])

    digits: list[str] = []
    scores: list[float] = []
    for x, y, width, height in boxes:
        digit, score = _classify_digit(mask[y : y + height, x : x + width])
        if score < cfg.DIGIT_MIN_CONFIDENCE:
            continue
        digits.append(digit)
        scores.append(score)
    if not digits:
        return None, 0.0
    return "".join(digits), min(scores)


def read_today_limit(frame: np.ndarray, dialog: Rect) -> tuple[int | None, float, str]:
    roi = dialog.relative_rect(cfg.TODAY_LIMIT_ROI)
    image = np.ascontiguousarray(
        frame[roi.top : roi.top + roi.height, roi.left : roi.left + roi.width]
    )
    digits, confidence = read_dark_digits(image)
    if digits is None:
        return None, confidence, ""
    return int(digits), confidence, digits


def keypad_point(dialog: Rect, key: str) -> tuple[int, int]:
    for row_index, row in enumerate(cfg.KEYPAD_LAYOUT):
        if key not in row:
            continue
        column_index = row.index(key)
        return dialog.relative_point(
            (
                cfg.KEYPAD_COLUMN_RATIOS[column_index],
                cfg.KEYPAD_ROW_RATIOS[row_index],
            )
        )
    raise ValueError(f"Unknown keypad key: {key}")
