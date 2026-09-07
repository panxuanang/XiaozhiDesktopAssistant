from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import quote_plus

import pychrome
import requests

from ..action_log import record
from ..config import load_settings
from ..llm import AIClient
from ..paths import browser_profile_dir

DEBUG_PORT = 9222


def _port_open(port: int = DEBUG_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _find_browser_executable() -> str:
    candidates = []
    if os.name == "nt":
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        candidates += [
            os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(pf86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(pf86, "Microsoft", "Edge", "Application", "msedge.exe"),
        ]
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for path in candidates:
        if path and Path(path).exists():
            return path
    raise FileNotFoundError("未找到 Chrome 或 Edge。请先安装 Chrome/Edge 浏览器。")


def ensure_browser() -> pychrome.Browser:
    if not _port_open():
        exe = _find_browser_executable()
        flags = [
            exe,
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={browser_profile_dir()}",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-allow-origins=*",
        ]
        if os.name == "nt":
            subprocess.Popen(flags, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            subprocess.Popen(flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 8
        while time.time() < deadline and not _port_open():
            time.sleep(0.2)
        if not _port_open():
            raise RuntimeError("浏览器启动成功但 DevTools 端口未就绪。")
    return pychrome.Browser(url=f"http://127.0.0.1:{DEBUG_PORT}")


def _tab():
    browser = ensure_browser()
    tabs = [t for t in browser.list_tab() if getattr(t, "type", "page") == "page"]
    if not tabs:
        tab = browser.new_tab("about:blank")
        try:
            tab.start()
        except Exception:
            pass
    else:
        tab = tabs[-1]
        for candidate in tabs:
            try:
                candidate.start()
                focus = candidate.Runtime.evaluate(expression="document.hasFocus()", returnByValue=True)
                if focus.get("result", {}).get("value") is True:
                    tab = candidate
                    break
            except Exception:
                continue
        try:
            tab.start()
        except Exception:
            pass
    try:
        tab.Runtime.enable()
        tab.Page.enable()
    except Exception:
        pass
    return tab


def _eval(expression: str):
    tab = _tab()
    result = tab.Runtime.evaluate(expression=expression, returnByValue=True, awaitPromise=True)
    return result.get("result", {}).get("value")


def browser_open(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    browser = ensure_browser()
    tab = browser.new_tab(url)
    try:
        tab.start()
        tab.Page.enable()
        tab.Page.navigate(url=url)
        time.sleep(1.2)
    except Exception:
        pass
    record("browser_open", {"url": url})
    return f"已打开：{url}"


def browser_search(query: str, engine: str = "bing") -> str:
    engines = {
        "bing": "https://www.bing.com/search?q=",
        "baidu": "https://www.baidu.com/s?wd=",
        "google": "https://www.google.com/search?q=",
    }
    url = engines.get(engine.lower(), engines["bing"]) + quote_plus(query)
    return browser_open(url)


def browser_current_page(max_chars: int = 30000) -> dict[str, str]:
    script = """(() => ({title: document.title, url: location.href, text: document.body ? document.body.innerText : ''}))()"""
    value = _eval(script) or {}
    return {
        "title": str(value.get("title", "")),
        "url": str(value.get("url", "")),
        "text": str(value.get("text", ""))[:max_chars],
    }


def summarize_current_webpage(question: str = "总结当前网页的主要内容") -> str:
    settings = load_settings()
    page = browser_current_page(settings.safety.max_webpage_chars_for_ai)
    ai = AIClient()
    result = ai.complete(
        f"任务：{question}\n网页标题：{page['title']}\n网页地址：{page['url']}\n\n网页正文：\n{page['text']}",
        system="你是网页阅读助手。只根据提供的网页正文总结或回答问题，不臆造网页没有的信息。",
    )
    record("summarize_current_webpage", {"url": page["url"], "question": question}, detail=result[:500])
    return result


def browser_click_text(text: str) -> str:
    needle = json.dumps(text)
    script = f"""(() => {{
      const target = {needle}.trim().toLowerCase();
      const els = [...document.querySelectorAll('button,a,[role="button"],input[type="button"],input[type="submit"],summary')];
      const el = els.find(e => ((e.innerText || e.value || e.getAttribute('aria-label') || '').trim().toLowerCase() === target))
              || els.find(e => ((e.innerText || e.value || e.getAttribute('aria-label') || '').trim().toLowerCase().includes(target)));
      if (!el) return {{ok:false, reason:'not found'}};
      el.scrollIntoView({{block:'center'}}); el.click(); return {{ok:true, tag:el.tagName, text:(el.innerText||el.value||'').trim()}};
    }})()"""
    result = _eval(script)
    record("browser_click_text", {"text": text}, detail=str(result))
    return json.dumps(result, ensure_ascii=False)


def browser_fill(field: str, value: str) -> str:
    f = json.dumps(field)
    v = json.dumps(value)
    script = f"""(() => {{
      const target = {f}.trim().toLowerCase();
      const candidates = [...document.querySelectorAll('input,textarea,[contenteditable="true"]')];
      const labelText = e => {{
        const id=e.id; let lab=id?document.querySelector(`label[for="${{CSS.escape(id)}}"]`):null;
        return [e.placeholder,e.name,e.getAttribute('aria-label'),lab?.innerText].filter(Boolean).join(' ').toLowerCase();
      }};
      const el = candidates.find(e => labelText(e) === target) || candidates.find(e => labelText(e).includes(target));
      if (!el) return {{ok:false, reason:'field not found'}};
      el.focus();
      if (el.isContentEditable) el.innerText={v}; else el.value={v};
      el.dispatchEvent(new Event('input',{{bubbles:true}})); el.dispatchEvent(new Event('change',{{bubbles:true}}));
      return {{ok:true}};
    }})()"""
    result = _eval(script)
    record("browser_fill", {"field": field, "value_len": len(value)}, detail=str(result))
    return json.dumps(result, ensure_ascii=False)


def browser_extract_tables(max_tables: int = 10) -> str:
    script = f"""(() => [...document.querySelectorAll('table')].slice(0,{max_tables}).map((t,ti)=>({{
      index:ti,
      rows:[...t.querySelectorAll('tr')].slice(0,100).map(r=>[...r.querySelectorAll('th,td')].map(c=>c.innerText.trim()))
    }})))()"""
    result = _eval(script) or []
    return json.dumps(result, ensure_ascii=False)[:50000]


def browser_download_by_text(text: str, download_dir: str) -> str:
    target = str(Path(download_dir).expanduser().resolve())
    tab = _tab()
    try:
        tab.Page.setDownloadBehavior(behavior="allow", downloadPath=target)
    except Exception:
        pass
    return browser_click_text(text) + f"\n下载目录：{target}"


def browser_upload_file(field: str, file_path: str) -> str:
    path = str(Path(file_path).expanduser().resolve())
    if not Path(path).exists():
        raise FileNotFoundError(path)
    tab = _tab()
    try:
        tab.DOM.enable()
    except Exception:
        pass
    f = json.dumps(field)
    expression = f"""(() => {{
      const target={f}.trim().toLowerCase();
      const candidates=[...document.querySelectorAll('input[type=\"file\"]')];
      const labelText=e=>{{const id=e.id; const lab=id?document.querySelector(`label[for=\"${{CSS.escape(id)}}\"]`):null; return [e.name,e.getAttribute('aria-label'),lab?.innerText].filter(Boolean).join(' ').toLowerCase();}};
      return candidates.find(e=>labelText(e)===target) || candidates.find(e=>labelText(e).includes(target)) || candidates[0] || null;
    }})()"""
    obj = tab.Runtime.evaluate(expression=expression, returnByValue=False).get("result", {})
    object_id = obj.get("objectId")
    if not object_id:
        return json.dumps({"ok": False, "reason": "file input not found"}, ensure_ascii=False)
    tab.DOM.setFileInputFiles(files=[path], objectId=object_id)
    record("browser_upload_file", {"field": field, "path": path})
    return json.dumps({"ok": True, "path": path}, ensure_ascii=False)
