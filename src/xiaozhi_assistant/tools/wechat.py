from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..action_log import record
from ..paths import pending_dir


def _pending_path(pid: str) -> Path:
    return pending_dir() / f"wechat_{pid}.json"


def prepare_wechat_message(contact: str, message: str) -> str:
    pid = uuid.uuid4().hex[:12]
    _pending_path(pid).write_text(json.dumps({"kind":"text", "contact": contact, "message": message, "created_at": time.time()}, ensure_ascii=False), encoding="utf-8")
    record("prepare_wechat_message", {"contact": contact, "message_len": len(message)}, detail=f"pending={pid}")
    return f"CONFIRM_REQUIRED: 准备给【{contact}】发送微信：\n{message}\n\n请向用户确认。用户明确确认后调用 wechat_confirm_send，pending_id={pid}"


def _activate_wechat() -> None:
    if os.name != "nt":
        raise RuntimeError("微信自动化仅支持 Windows。")
    from pywinauto import Desktop
    candidates = []
    for win in Desktop(backend="uia").windows():
        try:
            title = win.window_text()
            if "微信" in title or "WeChat" in title:
                candidates.append(win)
        except Exception:
            pass
    if not candidates:
        raise RuntimeError("没有找到微信窗口，请先登录并打开微信。")
    candidates[0].set_focus()
    time.sleep(0.4)


def _paste_text(text: str) -> None:
    import pyautogui
    import pyperclip
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")


def wechat_confirm_send(pending_id: str) -> str:
    path = _pending_path(pending_id)
    if not path.exists():
        raise RuntimeError("确认请求不存在或已过期。")
    data = json.loads(path.read_text(encoding="utf-8"))
    if time.time() - float(data.get("created_at", 0)) > 600:
        path.unlink(missing_ok=True)
        raise RuntimeError("这条待发送微信已超过10分钟，请重新准备。")
    contact = data["contact"]
    message = data.get("message", "")
    import pyautogui
    _activate_wechat()
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.35)
    _paste_text(contact)
    time.sleep(0.8)
    pyautogui.press("enter")
    time.sleep(0.7)
    if data.get("kind") == "file":
        file_path = Path(data["file_path"])
        if not file_path.exists():
            raise FileNotFoundError(file_path)
        import win32clipboard
        import win32con
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_HDROP, (str(file_path),))
        finally:
            win32clipboard.CloseClipboard()
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        pyautogui.press("enter")
        if message:
            time.sleep(0.4)
            _paste_text(message)
            pyautogui.press("enter")
    else:
        _paste_text(message)
        time.sleep(0.2)
        pyautogui.press("enter")
    path.unlink(missing_ok=True)
    record("wechat_confirm_send", {"contact": contact, "kind": data.get("kind", "text"), "message_len": len(message)}, detail="sent")
    return f"已尝试发送给：{contact}。请在微信窗口确认内容是否已出现。"


def read_wechat_ui(max_nodes: int = 250) -> str:
    _activate_wechat()
    from pywinauto import Desktop
    win = next(w for w in Desktop(backend="uia").windows() if "微信" in w.window_text() or "WeChat" in w.window_text())
    lines = []
    for ctrl in win.descendants()[:max_nodes]:
        try:
            text = ctrl.window_text().strip()
            if text:
                lines.append(text)
        except Exception:
            pass
    return "\n".join(lines)[-20000:]


def prepare_wechat_file(contact: str, file_path: str, caption: str = "") -> str:
    target = Path(file_path).expanduser().resolve()
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(target)
    pid = uuid.uuid4().hex[:12]
    _pending_path(pid).write_text(json.dumps({"kind":"file", "contact":contact, "file_path":str(target), "message":caption, "created_at":time.time()}, ensure_ascii=False), encoding="utf-8")
    record("prepare_wechat_file", {"contact": contact, "file": str(target)}, detail=f"pending={pid}")
    return f"CONFIRM_REQUIRED: 准备给【{contact}】发送文件【{target.name}】。请向用户确认后调用 wechat_confirm_send，pending_id={pid}"


def latest_pending_message() -> dict | None:
    items = sorted(pending_dir().glob("wechat_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not items:
        return None
    data = json.loads(items[0].read_text(encoding="utf-8"))
    if time.time() - float(data.get("created_at", 0)) > 600:
        items[0].unlink(missing_ok=True)
        return None
    data["pending_id"] = items[0].stem.replace("wechat_", "")
    return data
