import sys
import unittest
from unittest.mock import patch

import fishing_bot


class FishingBotArgumentTests(unittest.TestCase):
    def test_count_defaults_to_ten(self) -> None:
        with patch.object(sys, "argv", ["fishing_bot.py"]):
            args = fishing_bot.parse_args()

        self.assertEqual(args.count, 10)

    def test_count_accepts_positive_integer(self) -> None:
        with patch.object(sys, "argv", ["fishing_bot.py", "--count", "25"]):
            args = fishing_bot.parse_args()

        self.assertEqual(args.count, 25)

    def test_count_rejects_zero(self) -> None:
        with self.assertRaises(SystemExit):
            with patch.object(sys, "argv", ["fishing_bot.py", "--count", "0"]):
                fishing_bot.parse_args()


class LiftReadinessTests(unittest.TestCase):
    def test_gray_lift_icon_does_not_trigger(self) -> None:
        self.assertFalse(
            fishing_bot.is_lift_ready(
                fishing_bot.cfg.BITE_CHANGE_RATIO + 0.01,
                0.0,
            )
        )

    def test_green_lift_button_triggers(self) -> None:
        self.assertTrue(
            fishing_bot.is_lift_ready(
                fishing_bot.cfg.BITE_CHANGE_RATIO,
                fishing_bot.cfg.GREEN_PIXEL_RATIO,
            )
        )

    def test_green_scenery_without_button_change_does_not_trigger(self) -> None:
        self.assertFalse(
            fishing_bot.is_lift_ready(
                0.0,
                fishing_bot.cfg.GREEN_PIXEL_RATIO + 0.01,
            )
        )


if __name__ == "__main__":
    unittest.main()
