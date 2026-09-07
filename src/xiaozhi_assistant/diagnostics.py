from __future__ import annotations

import os
import platform
from pathlib import Path

from .config import load_settings
from .secrets_store import get_api_key


def run_diagnostics() -> list[tuple[str, bool, str]]:
    settings = load_settings()
    out: list[tuple[str, bool, str]] = []
    out.append(("操作系统", os.name == "nt", platform.platform()))
    out.append(("小智 MCP 地址", settings.xiaozhi_endpoint.startswith(("ws://", "wss://")), "已配置" if settings.xiaozhi_endpoint else "未配置"))
    out.append(("AI API Key", bool(get_api_key()), "已加密保存" if get_api_key() else "未配置"))
    out.append(("AI Base URL", bool(settings.ai.base_url), settings.ai.base_url or "未配置"))
    out.append(("AI 模型", bool(settings.ai.model), settings.ai.model or "未配置"))
    try:
        from .tools.browser import _find_browser_executable
        browser = _find_browser_executable()
        out.append(("Chrome/Edge", True, browser))
    except Exception as exc:
        out.append(("Chrome/Edge", False, str(exc)))
    try:
        import docx, pandas, openpyxl, pypdf  # noqa: F401
        out.append(("Office/PDF 组件", True, "正常"))
    except Exception as exc:
        out.append(("Office/PDF 组件", False, str(exc)))
    try:
        from rapidocr_onnxruntime import RapidOCR  # noqa: F401
        out.append(("本地 OCR", True, "RapidOCR 可用"))
    except Exception as exc:
        out.append(("本地 OCR", False, str(exc)))
    if os.name == "nt":
        try:
            from pywinauto import Desktop  # noqa: F401
            out.append(("Windows UI Automation", True, "可用"))
        except Exception as exc:
            out.append(("Windows UI Automation", False, str(exc)))
    return out
