from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from ..config import load_settings
from ..secrets_store import get_api_key


class AIError(RuntimeError):
    pass


class AIClient:
    """Unified AI adapter for OpenAI, DeepSeek, Doubao Ark and OpenAI-compatible APIs.

    Auto mode prefers the Responses API, then falls back to Chat Completions.
    This keeps current OpenAI/DeepSeek/Doubao support while retaining broad
    compatibility with older OpenAI-compatible gateways.
    """

    def __init__(self) -> None:
        settings = load_settings().ai
        key = get_api_key()
        if not key:
            raise AIError("尚未配置 API Key，请打开小智电脑助手设置。")
        if not settings.base_url or not settings.model:
            raise AIError("API Base URL 或模型名称为空，请先完成设置。")
        self.settings = settings
        self.client = OpenAI(
            api_key=key,
            base_url=settings.base_url.rstrip("/"),
            timeout=settings.timeout_seconds,
        )

    def complete(self, prompt: str, system: str = "你是专业、可靠的中文办公助手。", max_output_tokens: int = 8192) -> str:
        mode = self.settings.api_mode
        errors: list[str] = []
        if mode in ("auto", "responses"):
            try:
                return self._responses(prompt, system, max_output_tokens)
            except Exception as exc:
                errors.append(f"Responses API: {exc}")
                if mode == "responses":
                    raise AIError(errors[-1]) from exc
        if mode in ("auto", "chat"):
            try:
                return self._chat(prompt, system, max_output_tokens)
            except Exception as exc:
                errors.append(f"Chat Completions: {exc}")
        raise AIError("AI 调用失败：" + " | ".join(errors))

    def _responses(self, prompt: str, system: str, max_output_tokens: int) -> str:
        response = self.client.responses.create(
            model=self.settings.model,
            instructions=system,
            input=prompt,
            max_output_tokens=max_output_tokens,
        )
        text = getattr(response, "output_text", None)
        if text:
            return text.strip()
        # Compatibility fallback for providers that emulate Responses incompletely.
        data = response.model_dump() if hasattr(response, "model_dump") else {}
        chunks: list[str] = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    chunks.append(str(content["text"]))
        if chunks:
            return "\n".join(chunks).strip()
        raise AIError("模型返回为空。")

    def _chat(self, prompt: str, system: str, max_output_tokens: int) -> str:
        kwargs: dict[str, Any] = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_output_tokens,
        }
        # Temperature is not accepted by every reasoning model/provider.
        if self.settings.temperature is not None:
            kwargs["temperature"] = self.settings.temperature
        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            if "temperature" in str(exc).lower():
                kwargs.pop("temperature", None)
                response = self.client.chat.completions.create(**kwargs)
            else:
                raise
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise AIError("模型返回为空。")
        return str(content).strip()

    def complete_with_image(self, image_path: str | Path, question: str) -> str:
        path = Path(image_path)
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        data_url = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
        response = self.client.chat.completions.create(
            model=self.settings.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_tokens=4096,
        )
        if not response.choices or not response.choices[0].message.content:
            raise AIError("当前模型没有返回图像分析结果，可能不支持视觉输入。")
        return str(response.choices[0].message.content).strip()

    def test(self) -> str:
        answer = self.complete("只回复：连接成功", system="你是 API 连通性测试助手。", max_output_tokens=64)
        return answer[:200]


def json_for_ai(value: Any, max_chars: int = 24000) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[已截断]"
    return text
