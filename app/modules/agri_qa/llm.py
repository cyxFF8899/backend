from __future__ import annotations

from typing import Iterator

from openai import OpenAI

from ...config import Settings


class LLMModule:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = bool(settings.llm_api_key)
        self.client = (
            OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
            if self.enabled
            else None
        )

    def chat(self, *, system_prompt: str, user_prompt: str) -> str:
        if not self.enabled or self.client is None:
            return "未配置 DASHSCOPE_API_KEY，当前无法调用大模型。"
        try:
            resp = self.client.chat.completions.create(
                model=self.settings.llm_model,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return str(resp.choices[0].message.content or "").strip()
        except Exception as exc:
            return f"模型调用失败：{exc}"

    def stream_chat(self, *, system_prompt: str, user_prompt: str) -> Iterator[str]:
        if not self.enabled or self.client is None:
            yield "未配置 DASHSCOPE_API_KEY，当前无法调用大模型。"
            return
        try:
            stream = self.client.chat.completions.create(
                model=self.settings.llm_model,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
                stream=True,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                if delta is None:
                    continue
                content = getattr(delta, "content", None)
                if not content:
                    continue
                if isinstance(content, str):
                    yield content
                    continue
                for part in content:
                    text = getattr(part, "text", None)
                    if text:
                        yield text
        except Exception as exc:
            yield f"模型流式调用失败：{exc}"
