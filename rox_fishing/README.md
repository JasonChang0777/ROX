# ROX Fishing Bot

Windows PC 版 ROX 自動釣魚工具。程式會：

1. 找到標題含 `ROX` 或 `RÖX` 的遊戲視窗並切到前景。
2. 確認目前使用有限魚餌後，點擊固定比例的拋竿按鈕。
3. 偵測提竿按鈕變綠並快速點擊三次。
4. 等待釣魚結果，再開始下一輪。
5. 有限魚餌用完、畫面切回無限初始魚餌時自動停止。

```text
檢查有限魚餌 -> 拋竿 -> 等待上鉤 -> 收竿 -> 等待結果 -> 再檢查魚餌
```

## 安裝

```powershell
cd D:\ai-agent-project\ROX
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 執行

只有一個 ROX 視窗時：

```powershell
cd D:\ai-agent-project\ROX
.\.venv\Scripts\python.exe .\rox_fishing\fishing_bot.py
```

指定完成 25 次釣魚後自動停止：

```powershell
.\.venv\Scripts\python.exe .\rox_fishing\fishing_bot.py --count 25
```

從 ROX Bot 啟動器按「啟動釣魚」時，會先詢問釣魚次數。釣魚 Bot
不再辨識魚餌，完成指定次數後結束。

有多個 ROX 視窗時，先執行 `--list-windows`，再指定序號或 HWND：

```powershell
.\.venv\Scripts\python.exe .\rox_fishing\fishing_bot.py --list-windows
.\.venv\Scripts\python.exe .\rox_fishing\fishing_bot.py --window-index 2
.\.venv\Scripts\python.exe .\rox_fishing\fishing_bot.py --hwnd 8585488
```

- 按 `Q` 可隨時停止。
- 終端機內也可按 `Ctrl+C` 停止。
- Log 位於 `rox_fishing\logs\fishing_bot.log`。

程式使用螢幕擷取，因此 ROX 必須保持可見且位於前景。切到其他視窗時會暫停
辨識，回到 ROX 後自動繼續。

## 多開 ROX

先列出目前可見的 ROX 視窗：

```powershell
cd D:\ai-agent-project\ROX
.\.venv\Scripts\python.exe .\rox_fishing\fishing_bot.py --list-windows
```

輸出會包含視窗序號、handle、process ID 與客戶區大小。再用序號或 handle
指定要控制的角色：

```powershell
.\.venv\Scripts\python.exe .\rox_fishing\fishing_bot.py --window-index 2
.\.venv\Scripts\python.exe .\rox_fishing\fishing_bot.py --hwnd 1508906
```

偵測到多個 ROX 視窗但未指定時，Bot 會拒絕啟動，避免點錯角色。

目前使用前景螢幕擷取與 `SendInput`，不建議同時執行多個釣魚 Bot。多個程序
會互相切換前景視窗，導致截圖與點擊落在不同角色。正確用法是一次執行一個
Bot，透過上述參數選擇本次要控制的視窗。

## 拋竿位置

拋竿按鈕使用 `config.py` 的固定比例座標：

```python
CAST_BUTTON_POINT = (0.84921875, 0.7333333333333333)
```

程式會依 ROX 客戶區等比例換算：

- `1280x720`：約 `(1087, 528)`
- `1600x900`：約 `(1359, 660)`

Bot 只使用這個固定比例座標，不需要額外校準。若遊戲 UI 改版導致位置偏移，
直接修改 `CAST_BUTTON_POINT`。

## 雙螢幕與 DPI

程式使用 Per-Monitor DPI V2 與實體像素座標，可支援不同解析度或縮放比例的
雙螢幕。啟動 Log 會記錄：

```text
Client bounds: left=... top=... size=...
Monitor bounds: left=... top=... size=...
```

例如遊戲設定為 `1280x720`，在 125% 縮放的 2K 螢幕上，實際擷取區可能是
`1600x900`。這是正常的 DPI 換算，固定比例座標會一起縮放。

## 擷取與點擊

預設設定：

- `CAPTURE_MODE = "screen"`：擷取螢幕上實際可見的 ROX 客戶區。
- `CLICK_MODE = "sendinput"`：使用 Windows 實體滑鼠輸入。
- `RESTORE_CURSOR_AFTER_CLICK = True`：點擊後把滑鼠移回原本位置。
- `RESTORE_FOREGROUND_AFTER_CLICK = False`：保持 ROX 在前景，避免螢幕擷取暫停。
- `SHOW_PREVIEW = False`：不顯示 OpenCV 視窗，避免遮住遊戲。
- `SAVE_DEBUG_FRAMES = True`：保存辨識用偵錯圖。

ROX 的 DirectX 畫面通常無法透過 `PrintWindow` 正常取得，因此遊戲不可被
其他視窗遮住或最小化。純 `PostMessage` 背景點擊也可能被 ROX 忽略，
`sendinput` 是目前較可靠的模式。ROX 點擊期間會短暫占用滑鼠，完成後 Bot
會還原游標位置。使用 `screen` 擷取時，ROX 必須保持在前景；若將
`RESTORE_FOREGROUND_AFTER_CLICK` 設為 `True`，切回其他視窗後偵測會暫停。

點擊時序使用園藝 Bot 已驗證的設定：切到前景後等待 `100ms`、游標移動後
等待 `50ms`、左鍵按住 `120ms`，放開後再停留 `100ms` 才還原游標。
即使點擊途中被中斷，程式也會先送出左鍵放開事件。

ROX 與 Bot 必須使用相同權限。如果 ROX 以系統管理員執行，啟動 Bot 的
PowerShell 或 VS Code 也必須使用系統管理員權限。

## 偵錯圖片

偵錯圖片位於 `rox_fishing\debug`：

- `bite_latest.png`：等待上鉤時每秒更新的最新偵測區域。
- `bite_baseline.png`：拋竿後建立的固定比較基準，不會持續更新。
- `green_peak.png`：本輪最高上鉤變化分數的畫面。

查看偵錯圖片前建議先按 `Q` 停止 Bot。執行中切到 IDE 時，程式會暫停螢幕
辨識，避免把 IDE 畫面當成遊戲畫面。

## 辨識數值

Log 主要顯示：

- `Fishing progress`：目前已完成次數與目標次數。
- `bite`：目前提竿區域相對基準圖新增的亮綠色比例。
- `green`：提竿區域本身的綠色比例，主要供診斷參考。

## 測試

```powershell
cd D:\ai-agent-project\ROX
.\.venv\Scripts\python.exe -m unittest discover -s .\rox_fishing -p "test_*.py"
```

單獨測試滑鼠點擊：

```powershell
cd D:\ai-agent-project\ROX\rox_fishing
..\.venv\Scripts\python.exe test_click.py
```

## 待辦

- 為各狀態加入最長停留時間與逾時偵錯截圖。
