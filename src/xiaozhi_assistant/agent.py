from __future__ import annotations

import json
from typing import Any, Callable

from .action_log import record
from .llm import AIClient
from .tools import browser, files, office, pdf_tools, screen, system, wechat, windows


def _schema(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False},
        },
    }


TOOLS: dict[str, tuple[Callable[..., Any], dict[str, Any]]] = {
    "search_files": (files.search_files, _schema("search_files", "搜索本机文件", {"query":{"type":"string"},"root":{"type":"string","default":"桌面"}}, ["query"])),
    "list_directory": (files.list_directory, _schema("list_directory", "列出目录内容", {"path":{"type":"string","default":"桌面"}})),
    "move_path": (files.move_path, _schema("move_path", "移动文件或文件夹", {"source":{"type":"string"},"destination":{"type":"string"},"overwrite":{"type":"boolean","default":False}}, ["source","destination"])),
    "copy_path": (files.copy_path, _schema("copy_path", "复制文件或文件夹", {"source":{"type":"string"},"destination":{"type":"string"},"overwrite":{"type":"boolean","default":False}}, ["source","destination"])),
    "create_word_document": (office.create_word_document, _schema("create_word_document", "创建Word文档。模型应先生成完整正文再调用。", {"path":{"type":"string"},"title":{"type":"string"},"content":{"type":"string"},"author":{"type":"string","default":""}}, ["path","title","content"])),
    "read_word_document": (office.read_word_document, _schema("read_word_document", "读取Word正文", {"path":{"type":"string"}}, ["path"])),
    "excel_profile": (office.excel_profile, _schema("excel_profile", "本地统计Excel，返回结构化摘要", {"path":{"type":"string"}}, ["path"])),
    "excel_preview": (office.excel_preview, _schema("excel_preview", "预览Excel前若干行", {"path":{"type":"string"},"sheet":{"type":"string","default":""},"rows":{"type":"integer","default":20}}, ["path"])),
    "read_pdf": (pdf_tools.read_pdf, _schema("read_pdf", "读取PDF文本", {"path":{"type":"string"},"max_chars":{"type":"integer","default":30000}}, ["path"])),
    "ocr_scanned_pdf": (pdf_tools.ocr_scanned_pdf, _schema("ocr_scanned_pdf", "对扫描PDF逐页做本地OCR", {"path":{"type":"string"},"max_pages":{"type":"integer","default":30}}, ["path"])),
    "search_pdf": (pdf_tools.search_pdf, _schema("search_pdf", "搜索PDF关键词", {"path":{"type":"string"},"keyword":{"type":"string"}}, ["path","keyword"])),
    "browser_open": (browser.browser_open, _schema("browser_open", "打开网页", {"url":{"type":"string"}}, ["url"])),
    "browser_search": (browser.browser_search, _schema("browser_search", "搜索网页", {"query":{"type":"string"},"engine":{"type":"string","enum":["bing","baidu","google"],"default":"bing"}}, ["query"])),
    "browser_current_page": (browser.browser_current_page, _schema("browser_current_page", "读取当前网页DOM正文", {"max_chars":{"type":"integer","default":24000}})),
    "browser_click_text": (browser.browser_click_text, _schema("browser_click_text", "按可见文字点击网页按钮或链接", {"text":{"type":"string"}}, ["text"])),
    "browser_fill": (browser.browser_fill, _schema("browser_fill", "填写网页输入框", {"field":{"type":"string"},"value":{"type":"string"}}, ["field","value"])),
    "browser_extract_tables": (browser.browser_extract_tables, _schema("browser_extract_tables", "提取网页表格", {})),
    "browser_upload_file": (browser.browser_upload_file, _schema("browser_upload_file", "把本机文件设置到网页文件上传控件", {"field":{"type":"string"},"file_path":{"type":"string"}}, ["field","file_path"])),
    "list_windows": (windows.list_windows, _schema("list_windows", "列出Windows窗口", {})),
    "activate_window": (windows.activate_window, _schema("activate_window", "激活窗口", {"title_contains":{"type":"string"}}, ["title_contains"])),
    "window_action": (windows.window_action, _schema("window_action", "最小化/最大化/恢复/关闭窗口。关闭需要确认。", {"title_contains":{"type":"string"},"action":{"type":"string","enum":["minimize","maximize","restore","close"]},"confirmed":{"type":"boolean","default":False}}, ["title_contains","action"])),
    "ui_tree": (windows.ui_tree, _schema("ui_tree", "读取窗口UI Automation控件", {"title_contains":{"type":"string"}}, ["title_contains"])),
    "ui_click": (windows.ui_click, _schema("ui_click", "用UI Automation点击桌面控件", {"title_contains":{"type":"string"},"control_name":{"type":"string"},"control_type":{"type":"string","default":""}}, ["title_contains","control_name"])),
    "open_program": (windows.open_program, _schema("open_program", "启动程序", {"path_or_name":{"type":"string"}}, ["path_or_name"])),
    "prepare_wechat_message": (wechat.prepare_wechat_message, _schema("prepare_wechat_message", "准备微信消息但不发送，必须让用户确认", {"contact":{"type":"string"},"message":{"type":"string"}}, ["contact","message"])),
    "prepare_wechat_file": (wechat.prepare_wechat_file, _schema("prepare_wechat_file", "准备给微信联系人发送文件，但不立即发送", {"contact":{"type":"string"},"file_path":{"type":"string"},"caption":{"type":"string","default":""}}, ["contact","file_path"])),
    "wechat_confirm_send": (wechat.wechat_confirm_send, _schema("wechat_confirm_send", "仅当用户明确确认后，发送已准备的微信消息", {"pending_id":{"type":"string"}}, ["pending_id"])),
    "system_status": (system.system_status, _schema("system_status", "获取电脑状态", {})),
    "set_system_volume": (system.set_system_volume, _schema("set_system_volume", "设置系统音量", {"percent":{"type":"integer","minimum":0,"maximum":100}}, ["percent"])),
    "take_screenshot": (screen.take_screenshot, _schema("take_screenshot", "截屏并保存", {"path":{"type":"string","default":""}})),
    "local_ocr_screen": (screen.local_ocr_screen, _schema("local_ocr_screen", "仅在UIA/DOM不可用时OCR屏幕", {"keyword":{"type":"string","default":""}})),
}

SYSTEM_PROMPT = """你是运行在用户 Windows 电脑上的执行型桌面助手。你的目标是可靠完成用户任务，而不是只给教程。
优先级：直接文件/API操作 > DOM/UI Automation > 快捷键 > OCR > 坐标点击。
规则：
1. 不编造文件、表格、网页或执行结果；需要时先调用工具读取。
2. 写 Word 时直接调用 create_word_document，不要打开 Word 模拟打字。
3. 分析 Excel 时先调用 excel_profile/excel_preview，再基于真实统计结果分析。
4. 总结网页时读取 browser_current_page，不用 OCR。
5. 微信发送必须先 prepare_wechat_message；只有当前用户输入明确表示确认上一条待发消息时才能调用 wechat_confirm_send。
6. 不执行删除文件、支付、下单等高风险动作；这些动作应提示用户在专门安全流程中确认。
7. 最终用简洁中文说明已完成什么、结果在哪里；失败要说明具体原因。
"""


def _tool_result(value: Any, max_chars: int = 24000) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    return text[:max_chars] + ("...[截断]" if len(text) > max_chars else "")


def desktop_agent(instruction: str, max_steps: int = 10) -> str:
    normalized = instruction.strip().lower()
    explicit_wechat_confirm = normalized in {"确认", "确认发送", "发吧", "发送吧", "可以发", "就这样发", "确认发出"} or "确认发送" in normalized
    if explicit_wechat_confirm:
        pending = wechat.latest_pending_message()
        if pending:
            return wechat.wechat_confirm_send(pending["pending_id"])
    ai = AIClient()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": instruction},
    ]
    tool_specs = [spec for _, spec in TOOLS.values()]
    for _ in range(max(1, min(max_steps, 16))):
        response = ai.client.chat.completions.create(
            model=ai.settings.model,
            messages=messages,
            tools=tool_specs,
            tool_choice="auto",
        )
        if not response.choices:
            raise RuntimeError("AI Agent 没有返回结果。")
        msg = response.choices[0].message
        if not msg.tool_calls:
            answer = msg.content or "任务已结束，但模型没有返回文字结果。"
            record("desktop_agent", {"instruction": instruction}, detail=str(answer)[:1000])
            return str(answer)
        messages.append(msg.model_dump(exclude_none=True))
        for call in msg.tool_calls:
            name = call.function.name
            if name not in TOOLS:
                result = f"未知工具：{name}"
            else:
                func = TOOLS[name][0]
                try:
                    args = json.loads(call.function.arguments or "{}")
                    if name == "wechat_confirm_send" and not explicit_wechat_confirm:
                        result = "安全阻止：当前用户输入没有明确确认发送微信。请先结束本轮并让用户确认。"
                    elif name == "window_action" and args.get("action") == "close" and args.get("confirmed") and "确认" not in normalized:
                        result = "安全阻止：当前用户输入没有明确确认关闭窗口。"
                    else:
                        result = _tool_result(func(**args))
                except Exception as exc:
                    result = f"工具执行失败：{type(exc).__name__}: {exc}"
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    return "任务步骤超过上限，已停止。请把任务拆成更小步骤后重试。"
