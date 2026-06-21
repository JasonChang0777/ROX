from __future__ import annotations

import ctypes
from dataclasses import dataclass
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import config as cfg
from window_capture import (
    WindowInfo,
    find_windows,
    get_client_bounds,
    release_mouse_buttons,
)


PROJECT_DIR = Path(__file__).resolve().parent
ROOT_DIR = PROJECT_DIR.parent
BOT_SCRIPT_PATHS = {
    "園藝": PROJECT_DIR / "gardening_bot.py",
    "釣魚": ROOT_DIR / "rox_fishing" / "fishing_bot.py",
    "鑽石": ROOT_DIR / "rox_diamond" / "diamond_bot.py",
}
PACKAGED_BOT_NAMES = {
    "園藝": "ROX Gardening Bot.exe",
    "釣魚": "ROX Fishing Bot.exe",
    "鑽石": "ROX Diamond Buyer Bot.exe",
}
CREATE_NEW_CONSOLE = 0x00000010
SW_SHOWNORMAL = 1


@dataclass
class BotSession:
    bot_name: str
    process: subprocess.Popen[str]
    title: str


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def relaunch_as_admin() -> bool:
    executable = str(Path(sys.executable).resolve())
    if getattr(sys, "frozen", False):
        parameters = None
        working_dir = str(Path(executable).parent)
    else:
        script = str(Path(__file__).resolve())
        parameters = subprocess.list2cmdline([script])
        working_dir = str(PROJECT_DIR)
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        parameters,
        working_dir,
        SW_SHOWNORMAL,
    )
    return result > 32


def console_python(executable: str | Path = sys.executable) -> Path:
    path = Path(executable)
    if path.name.casefold() == "pythonw.exe":
        candidate = path.with_name("python.exe")
        if candidate.exists():
            return candidate
    return path


def bot_command(
    bot_name: str,
    hwnd: int,
    executable: str | Path = sys.executable,
    frozen: bool | None = None,
) -> list[str]:
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))

    try:
        if frozen:
            bot_path = (
                Path(executable).resolve().parent / PACKAGED_BOT_NAMES[bot_name]
            )
        else:
            bot_path = BOT_SCRIPT_PATHS[bot_name]
    except KeyError as exc:
        raise ValueError(f"Unknown bot: {bot_name}") from exc

    if frozen:
        return [str(bot_path), "--hwnd", str(hwnd)]

    return [
        str(console_python(executable)),
        str(bot_path),
        "--hwnd",
        str(hwnd),
    ]


def normalized_window_title(title: str) -> str:
    return title.strip().casefold().replace("ö", "o")


def is_game_window(window: WindowInfo) -> bool:
    return normalized_window_title(window.title) == "rox"


def describe_window(window: WindowInfo) -> tuple[str, str, str, str, str]:
    bounds = get_client_bounds(window.hwnd)
    size = f"{bounds.width}x{bounds.height}"
    status = "可執行" if bounds.width > 0 and bounds.height > 0 else "已最小化"
    return str(window.hwnd), str(window.process_id), size, status, window.title


class GardeningLauncher:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.windows: dict[str, WindowInfo] = {}
        self.bot_sessions: dict[int, BotSession] = {}

        root.title("ROX Bot 啟動器")
        root.geometry("820x430")
        root.minsize(680, 360)
        root.protocol("WM_DELETE_WINDOW", self.close)

        heading = ttk.Label(
            root,
            text="選擇要執行 Bot 的 ROX 遊戲視窗",
            font=("", 14, "bold"),
        )
        heading.pack(anchor="w", padx=16, pady=(16, 8))

        columns = ("hwnd", "pid", "size", "status", "bot", "title")
        self.tree = ttk.Treeview(
            root,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        headings = {
            "hwnd": "視窗 Handle",
            "pid": "PID",
            "size": "大小",
            "status": "狀態",
            "bot": "Bot",
            "title": "視窗標題",
        }
        widths = {
            "hwnd": 110,
            "pid": 80,
            "size": 90,
            "status": 90,
            "bot": 110,
            "title": 320,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                minwidth=60,
                stretch=column == "title",
            )
        self.tree.pack(fill="both", expand=True, padx=16)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.update_controls())

        controls = ttk.Frame(root)
        controls.pack(fill="x", padx=16, pady=12)
        ttk.Button(
            controls,
            text="重新整理",
            command=self.refresh_windows,
        ).pack(side="left")
        self.gardening_button = ttk.Button(
            controls,
            text="啟動園藝",
            command=lambda: self.start_bot("園藝"),
        )
        self.gardening_button.pack(side="left", padx=(8, 0))
        self.fishing_button = ttk.Button(
            controls,
            text="啟動釣魚",
            command=lambda: self.start_bot("釣魚"),
        )
        self.fishing_button.pack(side="left", padx=(8, 0))
        self.diamond_button = ttk.Button(
            controls,
            text="啟動鑽石",
            command=lambda: self.start_bot("鑽石"),
        )
        self.diamond_button.pack(side="left", padx=(8, 0))
        self.stop_button = ttk.Button(
            controls,
            text="停止選取 Bot",
            command=self.stop_bot,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=(8, 0))
        self.stop_all_button = ttk.Button(
            controls,
            text="停止全部 Bot",
            command=self.stop_all_bots,
            state="disabled",
        )
        self.stop_all_button.pack(side="left", padx=(8, 0))

        self.status_text = tk.StringVar(value="正在搜尋 ROX 視窗...")
        ttk.Label(root, textvariable=self.status_text).pack(
            anchor="w",
            padx=16,
            pady=(0, 12),
        )

        self.refresh_windows()
        self.poll_process()

    def item_id_for_hwnd(self, hwnd: int) -> str:
        return f"window-{hwnd}"

    def selected_hwnd(self) -> int | None:
        window = self.selected_window()
        return window.hwnd if window is not None else None

    def active_session(self, hwnd: int) -> BotSession | None:
        session = self.bot_sessions.get(hwnd)
        if session is None:
            return None
        if session.process.poll() is None:
            return session
        self.bot_sessions.pop(hwnd, None)
        return None

    def bot_status_text(self, hwnd: int) -> str:
        session = self.active_session(hwnd)
        if session is None:
            return "未啟動"
        return f"{session.bot_name}執行中"

    def update_controls(self) -> None:
        hwnd = self.selected_hwnd()
        selected_running = (
            hwnd is not None and self.active_session(hwnd) is not None
        )
        any_running = any(
            session.process.poll() is None
            for session in self.bot_sessions.values()
        )
        self.stop_button.configure(
            state="normal" if selected_running else "disabled"
        )
        self.stop_all_button.configure(
            state="normal" if any_running else "disabled"
        )

    def update_tree_bot_status(self, hwnd: int) -> None:
        item_id = self.item_id_for_hwnd(hwnd)
        if not self.tree.exists(item_id):
            self.update_controls()
            return
        values = list(self.tree.item(item_id, "values"))
        if len(values) >= 5:
            values[4] = self.bot_status_text(hwnd)
            self.tree.item(item_id, values=values)
        self.update_controls()

    def refresh_windows(self) -> None:
        selected_hwnd = None
        selected = self.tree.selection()
        if selected:
            selected_window = self.windows.get(selected[0])
            if selected_window is not None:
                selected_hwnd = selected_window.hwnd

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.windows.clear()

        matches = [
            window
            for window in find_windows(cfg.WINDOW_TITLE_KEYWORDS)
            if is_game_window(window)
        ]
        for window in matches:
            item_id = self.item_id_for_hwnd(window.hwnd)
            try:
                hwnd, pid, size, status, title = describe_window(window)
            except OSError:
                continue
            self.windows[item_id] = window
            values = (
                hwnd,
                pid,
                size,
                status,
                self.bot_status_text(window.hwnd),
                title,
            )
            self.tree.insert("", "end", iid=item_id, values=values)
            if window.hwnd == selected_hwnd:
                self.tree.selection_set(item_id)

        if matches:
            if not self.tree.selection() and self.tree.get_children():
                first = self.tree.get_children()[0]
                self.tree.selection_set(first)
                self.tree.focus(first)
            self.status_text.set(
                f"找到 {len(self.windows)} 個 ROX 遊戲視窗。"
                "選擇後按「啟動園藝」或「啟動釣魚」。"
            )
        else:
            self.status_text.set("找不到 ROX 遊戲視窗，請先開啟遊戲。")
        self.update_controls()

    def selected_window(self) -> WindowInfo | None:
        selected = self.tree.selection()
        if not selected:
            return None
        return self.windows.get(selected[0])

    def start_bot(self, bot_name: str) -> None:
        window = self.selected_window()
        if window is None:
            messagebox.showwarning("ROX Bot", "請先選擇一個 ROX 遊戲視窗。")
            return

        active = self.active_session(window.hwnd)
        if active is not None:
            messagebox.showinfo(
                "ROX Bot",
                f"{active.bot_name} 已經在這個視窗執行中。",
            )
            self.update_controls()
            return

        command = bot_command(bot_name, window.hwnd)
        bot_path = Path(command[0] if getattr(sys, "frozen", False) else command[1])
        try:
            process = subprocess.Popen(
                command,
                cwd=bot_path.parent,
                creationflags=CREATE_NEW_CONSOLE,
            )
        except OSError as exc:
            messagebox.showerror("啟動失敗", str(exc))
            return

        self.bot_sessions[window.hwnd] = BotSession(
            bot_name=bot_name,
            process=process,
            title=window.title,
        )
        self.update_tree_bot_status(window.hwnd)
        self.status_text.set(
            f"{bot_name} Bot 執行中：{window.title} (handle={window.hwnd})"
        )

    def stop_bot(self) -> None:
        window = self.selected_window()
        if window is None:
            messagebox.showwarning("ROX Bot", "請先選擇一個 ROX 遊戲視窗。")
            return
        session = self.active_session(window.hwnd)
        if session is None:
            messagebox.showinfo("ROX Bot", "選取的視窗目前沒有執行中的 Bot。")
            self.update_tree_bot_status(window.hwnd)
            return

        release_mouse_buttons()
        session.process.terminate()
        self.status_text.set(
            f"正在停止{session.bot_name} Bot：{session.title} "
            f"(handle={window.hwnd})"
        )

    def stop_all_bots(self) -> None:
        running = [
            (hwnd, session)
            for hwnd, session in self.bot_sessions.items()
            if session.process.poll() is None
        ]
        if not running:
            self.update_controls()
            return

        release_mouse_buttons()
        for _hwnd, session in running:
            session.process.terminate()
        self.status_text.set(f"正在停止 {len(running)} 個 Bot...")

    def mark_stopped(self, hwnd: int) -> None:
        stopped = self.bot_sessions.pop(hwnd, None)
        self.update_tree_bot_status(hwnd)
        if stopped is not None:
            self.status_text.set(
                f"{stopped.bot_name} Bot 已停止：{stopped.title} "
                f"(handle={hwnd})"
            )

    def poll_process(self) -> None:
        for hwnd, session in list(self.bot_sessions.items()):
            if session.process.poll() is not None:
                self.mark_stopped(hwnd)
        self.root.after(500, self.poll_process)

    def close(self) -> None:
        running = [
            session
            for session in self.bot_sessions.values()
            if session.process.poll() is None
        ]
        if running:
            leave_running = messagebox.askyesno(
                "關閉啟動器",
                f"仍有 {len(running)} 個 Bot 在執行。"
                "要讓 Bot 繼續執行並關閉啟動器嗎？",
            )
            if not leave_running:
                return
        self.root.destroy()


def main() -> None:
    if not is_admin():
        if relaunch_as_admin():
            return
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "ROX Bot 啟動器",
            "需要系統管理員權限才能對同樣以管理員權限執行的遊戲送出點擊。",
        )
        root.destroy()
        return

    root = tk.Tk()
    GardeningLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
