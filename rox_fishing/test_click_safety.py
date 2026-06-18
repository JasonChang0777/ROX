import unittest
from unittest.mock import patch

import window_capture


class SendInputClickSafetyTests(unittest.TestCase):
    @patch.object(
        window_capture.time,
        "sleep",
        side_effect=[None, None, RuntimeError("stop"), None],
    )
    @patch.object(window_capture.user32, "SetCursorPos", return_value=1)
    @patch.object(window_capture.user32, "GetCursorPos", return_value=1)
    @patch.object(window_capture.user32, "BringWindowToTop", return_value=1)
    @patch.object(window_capture.user32, "GetWindowThreadProcessId", return_value=1)
    @patch.object(window_capture.kernel32, "GetCurrentThreadId", return_value=2)
    @patch.object(window_capture.user32, "AttachThreadInput", return_value=1)
    @patch.object(window_capture.user32, "SetForegroundWindow", return_value=1)
    @patch.object(
        window_capture.user32,
        "GetForegroundWindow",
        side_effect=[202, 202, 202, 101],
    )
    @patch.object(window_capture.user32, "IsIconic", return_value=0)
    @patch.object(
        window_capture,
        "get_client_bounds",
        return_value=window_capture.ClientBounds(0, 0, 1280, 720),
    )
    @patch.object(window_capture.user32, "SendInput", return_value=1)
    def test_interrupted_click_releases_button_and_restores_cursor(
        self,
        send_input,
        _bounds,
        _is_iconic,
        _get_foreground,
        _set_foreground,
        _attach_thread_input,
        _current_thread,
        _window_thread,
        _bring_top,
        get_cursor,
        set_cursor,
        _sleep,
    ) -> None:
        original_x = 777
        original_y = 333
        sent_flags: list[int] = []

        def save_cursor(point_pointer) -> int:
            point = point_pointer._obj
            point.x = original_x
            point.y = original_y
            return 1

        def capture_input(_count, input_pointer, _size) -> int:
            sent_flags.append(input_pointer._obj.union.mi.dwFlags)
            return 1

        get_cursor.side_effect = save_cursor
        send_input.side_effect = capture_input

        with self.assertRaisesRegex(RuntimeError, "stop"):
            window_capture.click_client(
                101,
                (100, 200),
                mode="sendinput",
            )

        self.assertEqual(
            sent_flags[-1] & window_capture.MOUSEEVENTF_LEFTUP,
            window_capture.MOUSEEVENTF_LEFTUP,
        )
        set_cursor.assert_called_once_with(original_x, original_y)


if __name__ == "__main__":
    unittest.main()
