import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from window_capture import ClientBounds, WindowInfo


LAUNCHER_PATH = Path(__file__).with_name("rox_bot_launcher.pyw")
SPEC = importlib.util.spec_from_file_location("gardening_launcher", LAUNCHER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {LAUNCHER_PATH}")
launcher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = launcher
SPEC.loader.exec_module(launcher)


class GardeningLauncherTests(unittest.TestCase):
    @patch.object(launcher.ctypes.windll.shell32, "IsUserAnAdmin", return_value=1)
    def test_admin_check_reports_elevated(self, _is_admin) -> None:
        self.assertTrue(launcher.is_admin())

    def test_gardening_command_uses_selected_handle(self) -> None:
        command = launcher.bot_command(
            "園藝",
            12345,
            executable=Path("C:/ROX/.venv/Scripts/pythonw.exe"),
        )

        self.assertEqual(command[-2:], ["--hwnd", "12345"])
        self.assertTrue(command[0].endswith("pythonw.exe"))
        self.assertTrue(command[1].endswith("gardening_bot.py"))

    def test_fishing_command_uses_selected_handle(self) -> None:
        command = launcher.bot_command(
            "釣魚",
            67890,
            executable=Path("C:/ROX/.venv/Scripts/python.exe"),
        )

        self.assertEqual(command[-2:], ["--hwnd", "67890"])
        self.assertTrue(command[1].endswith("fishing_bot.py"))

    def test_packaged_command_starts_bot_executable(self) -> None:
        command = launcher.bot_command(
            "園藝",
            12345,
            executable=Path("C:/ROX Bot/ROX Bot.exe"),
            frozen=True,
        )

        self.assertEqual(
            command,
            [
                str(Path("C:/ROX Bot/ROX Gardening Bot.exe").resolve()),
                "--hwnd",
                "12345",
            ],
        )

    def test_only_exact_rox_title_is_treated_as_game(self) -> None:
        self.assertTrue(launcher.is_game_window(WindowInfo(1, "RöX", 10)))
        self.assertFalse(
            launcher.is_game_window(WindowInfo(2, "ROX Bot 啟動器", 20))
        )
        self.assertFalse(
            launcher.is_game_window(WindowInfo(3, "ROX - 檔案總管", 30))
        )

    @patch.object(
        launcher,
        "get_client_bounds",
        return_value=ClientBounds(0, 0, 1280, 720),
    )
    def test_describe_window_marks_visible_client_ready(self, _bounds) -> None:
        values = launcher.describe_window(WindowInfo(101, "ROX A", 1001))

        self.assertEqual(values, ("101", "1001", "1280x720", "可執行", "ROX A"))


if __name__ == "__main__":
    unittest.main()
