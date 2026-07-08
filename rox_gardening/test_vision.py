import unittest

import cv2
import numpy as np

from vision import (
    Rect,
    find_verification_dialog,
    inspect_garden_button,
    is_keypad_open,
    keypad_point,
    read_answer_digits,
    read_equation,
)


class VisionTests(unittest.TestCase):
    def test_rejects_plain_bright_rectangle_as_verification(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.rectangle(frame, (300, 170), (980, 570), (220, 220, 220), -1)
        self.assertIsNone(find_verification_dialog(frame))

    def test_finds_verification_with_expected_controls(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.rectangle(frame, (300, 170), (980, 570), (220, 220, 220), -1)
        cv2.rectangle(frame, (456, 354), (824, 414), (90, 80, 80), -1)
        cv2.rectangle(frame, (518, 474), (762, 546), (240, 170, 90), -1)
        self.assertIsNotNone(find_verification_dialog(frame))

    def test_confirm_button_refines_dialog_around_center_controls(self) -> None:
        frame = np.zeros((642, 1277, 3), dtype=np.uint8)
        cv2.rectangle(frame, (421, 199), (855, 488), (225, 225, 225), -1)
        cv2.circle(frame, (420, 350), 95, (225, 225, 225), -1)
        cv2.rectangle(frame, (526, 334), (751, 371), (90, 80, 80), -1)
        cv2.rectangle(frame, (565, 421), (714, 466), (240, 170, 90), -1)

        dialog = find_verification_dialog(frame)

        self.assertIsNotNone(dialog)
        assert dialog is not None
        self.assertGreater(dialog.left, 400)
        self.assertLess(dialog.width, 460)
        self.assertAlmostEqual(dialog.center[0], 639, delta=5)

    def test_detects_garden_button_colors(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        center = (round(1280 * 0.627), round(720 * 0.402))
        cv2.circle(frame, center, 35, (80, 180, 225), -1)
        cv2.rectangle(
            frame,
            (center[0] - 8, center[1] - 18),
            (center[0] + 8, center[1] + 18),
            (245, 245, 245),
            -1,
        )
        self.assertTrue(
            inspect_garden_button(frame, (0.627, 0.402)).visible
        )

    def test_keypad_point_uses_dialog_relative_layout(self) -> None:
        dialog = Rect(100, 80, 600, 400)
        self.assertEqual(keypad_point(dialog, "1"), (647, 300))
        self.assertEqual(keypad_point(dialog, "0"), (924, 392))
        self.assertEqual(keypad_point(dialog, "enter"), (924, 484))

    def test_detects_open_keypad_from_clear_and_enter_keys(self) -> None:
        frame = np.zeros((651, 1278, 3), dtype=np.uint8)
        dialog = Rect(429, 210, 422, 281)
        for key, color in (
            ("clear", (75, 65, 130)),
            ("enter", (65, 130, 80)),
        ):
            center_x, center_y = keypad_point(dialog, key)
            cv2.rectangle(
                frame,
                (center_x - 25, center_y - 25),
                (center_x + 25, center_y + 25),
                color,
                -1,
            )

        self.assertTrue(is_keypad_open(frame, dialog))

    def test_rejects_keypad_when_clear_key_is_missing(self) -> None:
        frame = np.zeros((651, 1278, 3), dtype=np.uint8)
        dialog = Rect(429, 210, 422, 281)
        center_x, center_y = keypad_point(dialog, "enter")
        cv2.rectangle(
            frame,
            (center_x - 25, center_y - 25),
            (center_x + 25, center_y + 25),
            (65, 130, 80),
            -1,
        )

        self.assertFalse(is_keypad_open(frame, dialog))

    def test_reads_synthetic_addition(self) -> None:
        frame = np.full((720, 1280, 3), 230, dtype=np.uint8)
        dialog = Rect(320, 150, 640, 420)
        cv2.putText(
            frame,
            "9+7",
            (590, 320),
            cv2.FONT_HERSHEY_DUPLEX,
            1.4,
            (55, 55, 55),
            5,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            "9+7",
            (590, 320),
            cv2.FONT_HERSHEY_DUPLEX,
            1.4,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        result = read_equation(frame, dialog)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.expression, "9+7")
        self.assertEqual(result.answer, 16)

    def test_reads_synthetic_multiplication(self) -> None:
        frame = np.full((720, 1280, 3), 230, dtype=np.uint8)
        dialog = Rect(320, 150, 640, 420)
        cv2.putText(
            frame,
            "1*5",
            (590, 320),
            cv2.FONT_HERSHEY_DUPLEX,
            1.4,
            (55, 55, 55),
            5,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            "1*5",
            (590, 320),
            cv2.FONT_HERSHEY_DUPLEX,
            1.4,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        result = read_equation(frame, dialog)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.expression, "1*5")
        self.assertEqual(result.answer, 5)

    def test_reads_game_style_subtraction(self) -> None:
        frame = np.full((720, 1280, 3), 230, dtype=np.uint8)
        dialog = Rect(320, 150, 640, 420)
        cv2.putText(
            frame,
            "9",
            (590, 320),
            cv2.FONT_HERSHEY_DUPLEX,
            1.4,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.line(frame, (622, 303), (638, 303), (255, 255, 255), 3)
        cv2.putText(
            frame,
            "4",
            (642, 320),
            cv2.FONT_HERSHEY_DUPLEX,
            1.4,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        result = read_equation(frame, dialog)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.expression, "9-4")
        self.assertEqual(result.answer, 5)

    def test_reads_small_outlined_subtraction(self) -> None:
        frame = np.full((642, 1277, 3), 230, dtype=np.uint8)
        dialog = Rect(432, 205, 414, 281)
        region_left = round(dialog.left + dialog.width * 0.42)
        region_top = round(dialog.top + dialog.height * 0.32)
        baseline = region_top + 30
        cv2.putText(
            frame,
            "8-7",
            (region_left + 12, baseline),
            cv2.FONT_HERSHEY_DUPLEX,
            0.72,
            (70, 70, 70),
            4,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            "8-7",
            (region_left + 12, baseline),
            cv2.FONT_HERSHEY_DUPLEX,
            0.72,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        result = read_equation(frame, dialog)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.expression, "8-7")
        self.assertEqual(result.answer, 1)

    def test_reads_answer_field_digits(self) -> None:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        dialog = Rect(320, 150, 640, 420)
        cv2.putText(
            frame,
            "10",
            (665, 390),
            cv2.FONT_HERSHEY_DUPLEX,
            1.2,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        digits, confidence = read_answer_digits(frame, dialog)
        self.assertEqual(digits, "10")
        self.assertGreater(confidence, 0.4)

    def test_reads_game_sized_answer_15(self) -> None:
        frame = np.zeros((900, 1600, 3), dtype=np.uint8)
        dialog = Rect(377, 280, 727, 406)
        cv2.putText(
            frame,
            "15",
            (786, 505),
            cv2.FONT_HERSHEY_DUPLEX,
            0.9,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        digits, confidence = read_answer_digits(frame, dialog)
        self.assertEqual(digits, "15")
        self.assertGreater(confidence, 0.4)

    def test_reads_centered_multi_digit_answer_without_clipping(self) -> None:
        frame = np.zeros((651, 1278, 3), dtype=np.uint8)
        dialog = Rect(429, 210, 422, 281)
        cv2.putText(
            frame,
            "939",
            (624, 365),
            cv2.FONT_HERSHEY_DUPLEX,
            0.65,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        digits, confidence = read_answer_digits(frame, dialog)

        self.assertEqual(digits, "939")
        self.assertGreater(confidence, 0.4)


if __name__ == "__main__":
    unittest.main()
