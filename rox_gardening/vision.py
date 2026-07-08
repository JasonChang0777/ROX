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


@dataclass(frozen=True)
class EquationResult:
    expression: str
    answer: int
    confidence: float
    image: np.ndarray


@dataclass(frozen=True)
class GardenButtonResult:
    visible: bool
    gold_ratio: float
    white_ratio: float
    rect: Rect


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


def inspect_garden_button(
    frame: np.ndarray,
    center_ratio: tuple[float, float],
) -> GardenButtonResult:
    frame_height, frame_width = frame.shape[:2]
    center_x = round(frame_width * center_ratio[0])
    center_y = round(frame_height * center_ratio[1])
    side = max(
        40,
        round(min(frame_width, frame_height) * cfg.GARDEN_BUTTON_SIZE_RATIO),
    )
    left = max(0, min(frame_width - side, center_x - side // 2))
    top = max(0, min(frame_height - side, center_y - side // 2))
    image = np.ascontiguousarray(frame[top : top + side, left : left + side])

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    height, width = hsv.shape[:2]
    yy, xx = np.ogrid[:height, :width]
    radius = min(width, height) * 0.46
    circle = (xx - width / 2) ** 2 + (yy - height / 2) ** 2 <= radius**2
    gold = (
        (hsv[:, :, 0] >= 8)
        & (hsv[:, :, 0] <= 40)
        & (hsv[:, :, 1] >= 45)
        & (hsv[:, :, 2] >= 115)
        & circle
    )
    white = (
        (hsv[:, :, 1] <= 90)
        & (hsv[:, :, 2] >= 175)
        & circle
    )
    circle_pixels = max(1, int(np.count_nonzero(circle)))
    gold_ratio = float(np.count_nonzero(gold) / circle_pixels)
    white_ratio = float(np.count_nonzero(white) / circle_pixels)
    return GardenButtonResult(
        gold_ratio >= cfg.GARDEN_GOLD_PIXEL_RATIO
        and white_ratio >= cfg.GARDEN_WHITE_PIXEL_RATIO,
        gold_ratio,
        white_ratio,
        Rect(left, top, side, side),
    )


def _verification_controls_present(frame: np.ndarray, rect: Rect) -> bool:
    input_image = frame[
        round(rect.top + rect.height * 0.46) :
        round(rect.top + rect.height * 0.61),
        round(rect.left + rect.width * 0.23) :
        round(rect.left + rect.width * 0.77),
    ]
    input_hsv = cv2.cvtColor(input_image, cv2.COLOR_BGR2HSV)
    dark_ratio = float(
        np.count_nonzero(input_hsv[:, :, 2] <= 145)
        / input_hsv[:, :, 2].size
    )

    button_image = frame[
        round(rect.top + rect.height * 0.76) :
        round(rect.top + rect.height * 0.94),
        round(rect.left + rect.width * 0.32) :
        round(rect.left + rect.width * 0.68),
    ]
    button_hsv = cv2.cvtColor(button_image, cv2.COLOR_BGR2HSV)
    blue = (
        (button_hsv[:, :, 0] >= 85)
        & (button_hsv[:, :, 0] <= 125)
        & (button_hsv[:, :, 1] >= 35)
        & (button_hsv[:, :, 2] >= 130)
    )
    blue_ratio = float(np.count_nonzero(blue) / blue.size)
    return dark_ratio >= 0.35 and blue_ratio >= 0.20


def _dialog_from_confirm_button(frame: np.ndarray) -> Rect | None:
    search, offset_x, offset_y = crop_ratio(frame, cfg.VERIFY_SEARCH_ROI)
    hsv = cv2.cvtColor(search, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(
        hsv,
        np.array((85, 35, 130), dtype=np.uint8),
        np.array((125, 255, 255), dtype=np.uint8),
    )
    blue = cv2.morphologyEx(
        blue,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (9, 5)),
    )
    contours, _ = cv2.findContours(
        blue,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    frame_height, frame_width = frame.shape[:2]
    candidates: list[tuple[float, Rect]] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        aspect = width / max(1, height)
        if not 2.2 <= aspect <= 5.0:
            continue
        if not 0.08 <= width / frame_width <= 0.25:
            continue
        if not 0.04 <= height / frame_height <= 0.15:
            continue

        center_x = offset_x + x + width // 2
        center_y = offset_y + y + height // 2
        if not 0.30 <= center_x / frame_width <= 0.70:
            continue
        if not 0.55 <= center_y / frame_height <= 0.82:
            continue

        dialog_width = round(
            width / cfg.VERIFY_CONFIRM_BUTTON_WIDTH_RATIO
        )
        dialog_height = round(
            height / cfg.VERIFY_CONFIRM_BUTTON_HEIGHT_RATIO
        )
        left = max(0, center_x - dialog_width // 2)
        top = max(
            0,
            round(center_y - dialog_height * cfg.VERIFY_CONFIRM_POINT[1]),
        )
        if left + dialog_width > frame_width:
            left = frame_width - dialog_width
        if top + dialog_height > frame_height:
            top = frame_height - dialog_height
        rect = Rect(left, top, dialog_width, dialog_height)
        if not _verification_controls_present(frame, rect):
            continue

        center_distance = abs(center_x / frame_width - 0.5)
        candidates.append((width * height - center_distance * 1000.0, rect))

    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def find_verification_dialog(frame: np.ndarray) -> Rect | None:
    control_dialog = _dialog_from_confirm_button(frame)
    if control_dialog is not None:
        return control_dialog

    search, offset_x, offset_y = crop_ratio(frame, cfg.VERIFY_SEARCH_ROI)
    hsv = cv2.cvtColor(search, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array((0, 0, 155), dtype=np.uint8),
        np.array((179, 95, 255), dtype=np.uint8),
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (19, 19))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    frame_area = frame.shape[0] * frame.shape[1]
    candidates: list[tuple[float, Rect]] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area_ratio = width * height / frame_area
        aspect = width / max(1, height)
        if not (
            cfg.VERIFY_DIALOG_MIN_AREA_RATIO
            <= area_ratio
            <= cfg.VERIFY_DIALOG_MAX_AREA_RATIO
        ):
            continue
        if not (
            cfg.VERIFY_DIALOG_MIN_ASPECT
            <= aspect
            <= cfg.VERIFY_DIALOG_MAX_ASPECT
        ):
            continue
        rect = Rect(offset_x + x, offset_y + y, width, height)
        center_x, center_y = rect.center
        frame_h, frame_w = frame.shape[:2]
        if not (0.30 <= center_x / frame_w <= 0.70):
            continue
        if not (0.30 <= center_y / frame_h <= 0.68):
            continue
        if not _verification_controls_present(frame, rect):
            continue
        center_distance = abs(center_x / frame_w - 0.5) + abs(
            center_y / frame_h - 0.5
        )
        candidates.append((area_ratio - center_distance * 0.2, rect))

    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


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


def _synthetic_templates() -> dict[str, list[np.ndarray]]:
    templates: dict[str, list[np.ndarray]] = {
        char: [] for char in "0123456789+-*"
    }
    fonts = (
        cv2.FONT_HERSHEY_SIMPLEX,
        cv2.FONT_HERSHEY_DUPLEX,
        cv2.FONT_HERSHEY_COMPLEX,
    )
    for char in templates:
        for font in fonts:
            for thickness in (1, 2, 3):
                image = np.zeros((72, 56), dtype=np.uint8)
                size, _ = cv2.getTextSize(char, font, 1.5, thickness)
                origin = (
                    (image.shape[1] - size[0]) // 2,
                    (image.shape[0] + size[1]) // 2,
                )
                cv2.putText(
                    image,
                    char,
                    origin,
                    font,
                    1.5,
                    255,
                    thickness,
                    cv2.LINE_AA,
                )
                _, image = cv2.threshold(image, 80, 255, cv2.THRESH_BINARY)
                templates[char].append(_normalize_glyph(image))
    return templates


GLYPH_TEMPLATES = _synthetic_templates()


def _classify_glyph(glyph: np.ndarray) -> tuple[str, float]:
    normalized = _normalize_glyph(glyph)
    best_char = ""
    best_score = -1.0
    for char, templates in GLYPH_TEMPLATES.items():
        for template in templates:
            score = float(
                cv2.matchTemplate(
                    normalized,
                    template,
                    cv2.TM_CCOEFF_NORMED,
                )[0, 0]
            )
            if score > best_score:
                best_char = char
                best_score = score
    return best_char, max(0.0, best_score)


def _equation_region(frame: np.ndarray, dialog: Rect) -> np.ndarray:
    left = round(dialog.left + dialog.width * 0.42)
    right = round(dialog.left + dialog.width * 0.66)
    top = round(dialog.top + dialog.height * 0.32)
    bottom = round(dialog.top + dialog.height * 0.46)
    return np.ascontiguousarray(frame[top:bottom, left:right])


def read_equation(frame: np.ndarray, dialog: Rect) -> EquationResult | None:
    image = _equation_region(frame, dialog)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # The game uses a dark fill with a bright outline. At smaller window sizes,
    # opening splits outlined digits such as "8" into separate upper/lower
    # contours, so preserve the original bright mask.
    glyph_mask = cv2.inRange(gray, 235, 255)
    contours, _ = cv2.findContours(
        glyph_mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    boxes: list[tuple[int, int, int, int]] = []
    image_height, image_width = glyph_mask.shape
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        is_minus = width >= 8 and width >= height * 3
        is_regular_glyph = height >= image_height * 0.14 and width >= 2
        if not (is_minus or is_regular_glyph):
            continue
        if width * height > image_width * image_height * 0.45:
            continue
        boxes.append((x, y, width, height))
    boxes.sort(key=lambda box: box[0])

    chars: list[str] = []
    scores: list[float] = []
    for x, y, width, height in boxes:
        if width >= 8 and width >= height * 3:
            char, score = "-", 1.0
        else:
            char, score = _classify_glyph(
                glyph_mask[y : y + height, x : x + width]
            )
        chars.append(char)
        scores.append(score)

    expression = "".join(chars)
    operators = [operator for operator in "+-*" if expression.count(operator)]
    if len(operators) != 1 or expression.count(operators[0]) != 1:
        return None
    operator = operators[0]
    left_text, right_text = expression.split(operator, 1)
    if not left_text.isdigit() or not right_text.isdigit():
        return None
    left_value = int(left_text)
    right_value = int(right_text)
    if operator == "+":
        answer = left_value + right_value
    elif operator == "-":
        answer = left_value - right_value
    else:
        answer = left_value * right_value
    if answer < 0:
        return None
    confidence = min(scores, default=0.0)
    return EquationResult(
        expression,
        answer,
        confidence,
        image,
    )


def read_answer_digits(frame: np.ndarray, dialog: Rect) -> tuple[str, float]:
    left = round(dialog.left + dialog.width * cfg.VERIFY_ANSWER_ROI[0])
    top = round(dialog.top + dialog.height * cfg.VERIFY_ANSWER_ROI[1])
    right = round(dialog.left + dialog.width * cfg.VERIFY_ANSWER_ROI[2])
    bottom = round(dialog.top + dialog.height * cfg.VERIFY_ANSWER_ROI[3])
    image = np.ascontiguousarray(frame[top:bottom, left:right])
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = cv2.inRange(gray, 210, 255)
    # The game's anti-aliased answer digits can contain one-pixel gaps.
    # Closing preserves and reconnects those strokes; opening split the "5"
    # in answers such as "15" into fragments that were filtered out below.
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
        if height < image_height * 0.28 or width < 2:
            continue
        if width * height > image_width * image_height * 0.30:
            continue
        boxes.append((x, y, width, height))
    boxes.sort(key=lambda box: box[0])

    digits: list[str] = []
    scores: list[float] = []
    for x, y, width, height in boxes:
        glyph = mask[y : y + height, x : x + width]
        best_digit = ""
        best_score = -1.0
        normalized = _normalize_glyph(glyph)
        for digit in "0123456789":
            for template in GLYPH_TEMPLATES[digit]:
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
        digits.append(best_digit)
        scores.append(max(0.0, best_score))
    return "".join(digits), min(scores, default=0.0)


def is_keypad_open(frame: np.ndarray, dialog: Rect) -> bool:
    """Return whether the distinctive clear and enter keys are visible."""
    frame_height, frame_width = frame.shape[:2]

    def key_color_ratio(key: str, color: str) -> float:
        center_x, center_y = keypad_point(dialog, key)
        half_width = max(8, round(dialog.width * 0.045))
        half_height = max(8, round(dialog.height * 0.065))
        left = max(0, center_x - half_width)
        right = min(frame_width, center_x + half_width + 1)
        top = max(0, center_y - half_height)
        bottom = min(frame_height, center_y + half_height + 1)
        if left >= right or top >= bottom:
            return 0.0

        hsv = cv2.cvtColor(frame[top:bottom, left:right], cv2.COLOR_BGR2HSV)
        hue = hsv[:, :, 0]
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        if color == "red":
            mask = (hue >= 165) & (saturation >= 45) & (value >= 65)
        else:
            mask = (
                (hue >= 35)
                & (hue <= 85)
                & (saturation >= 45)
                & (value >= 65)
            )
        return float(np.count_nonzero(mask) / mask.size)

    clear_ratio = key_color_ratio("clear", "red")
    enter_ratio = key_color_ratio("enter", "green")
    return clear_ratio >= 0.20 and enter_ratio >= 0.20


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
    raise ValueError(f"數字鍵盤沒有按鍵: {key}")
