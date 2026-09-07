from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .paths import config_path


@dataclass
class AISettings:
    provider: str = "OpenAI"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.6-luna"
    api_mode: str = "auto"  # auto | responses | chat
    timeout_seconds: int = 120
    temperature: float = 0.3


@dataclass
class ModuleSettings:
    files: bool = True
    office: bool = True
    pdf: bool = True
    browser: bool = True
    windows: bool = True
    wechat: bool = True
    ocr: bool = True
    screen: bool = True
    system: bool = True


@dataclass
class SafetySettings:
    require_send_confirmation: bool = True
    require_delete_confirmation: bool = True
    require_command_confirmation: bool = True
    max_webpage_chars_for_ai: int = 24000
    max_file_chars_for_ai: int = 30000


@dataclass
class AppSettings:
    xiaozhi_endpoint: str = ""
    auto_connect: bool = True
    auto_start_windows: bool = False
    start_minimized: bool = False
    update_manifest_url: str = ""
    ai: AISettings = field(default_factory=AISettings)
    modules: ModuleSettings = field(default_factory=ModuleSettings)
    safety: SafetySettings = field(default_factory=SafetySettings)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        return cls(
            xiaozhi_endpoint=data.get("xiaozhi_endpoint", ""),
            auto_connect=bool(data.get("auto_connect", True)),
            auto_start_windows=bool(data.get("auto_start_windows", False)),
            start_minimized=bool(data.get("start_minimized", False)),
            update_manifest_url=data.get("update_manifest_url", ""),
            ai=AISettings(**data.get("ai", {})),
            modules=ModuleSettings(**data.get("modules", {})),
            safety=SafetySettings(**data.get("safety", {})),
        )


def load_settings(path: Path | None = None) -> AppSettings:
    path = path or config_path()
    if not path.exists():
        return AppSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppSettings.from_dict(data)
    except Exception:
        return AppSettings()


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-5.6-luna",
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
    },
    "豆包方舟": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seed-2-0-lite-260215",
    },
    "自定义兼容API": {
        "base_url": "",
        "model": "",
    },
}
