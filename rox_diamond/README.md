# ROX Diamond Buyer Bot

Start ROX, open Trading House, and switch to the Diamond page before running.
The bot scans for the market buy button, opens the purchase dialog, enters the
maximum quantity by pressing `9` four times, confirms the keypad, and clicks the
purchase button.
If the purchase dialog stays open after clicking purchase, the bot closes that
dialog and returns to scanning the Diamond page. The close action uses the
detected pink `X` button position, with retries if the dialog remains open.
Quantity entry uses one foreground activation followed by fast consecutive
clicks for the four digits, keypad confirmation, and purchase button.

The default stop key is `Q`.

```powershell
cd D:\ai-agent-project\ROX
.\.venv\Scripts\python.exe .\rox_diamond\diamond_bot.py
```

Useful checks:

```powershell
.\.venv\Scripts\python.exe .\rox_diamond\diamond_bot.py --inspect
.\.venv\Scripts\python.exe .\rox_diamond\diamond_bot.py --list-windows
.\.venv\Scripts\python.exe .\rox_diamond\diamond_bot.py --hwnd 123456
```

The bot uses Windows `SendInput` clicks because the Trading House purchase
button does not reliably accept background `PostMessage` clicks. Screen capture
still requires the ROX window to remain visible and not be covered.
