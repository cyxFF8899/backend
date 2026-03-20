from __future__ import annotations

from typing import Iterator

from ...config import Settings

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    HumanMessage = None  # type: ignore
    SystemMessage = None  # type: ignore
    ChatOpenAI = None  # type: ignore


class LLMModule:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = bool(settings.llm_api_key)

        self.client = None
        if self.enabled and ChatOpenAI is not None:
            try:
                self.client = ChatOpenAI(
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                    model=settings.llm_model,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                )
            except Exception:
                self.client = None

    def chat(self, *, system_prompt: str, user_prompt: str) -> str:
        if not self.enabled:
            return "未配置 API KEY，当前无法调用大模型。"
        if self.client is None or HumanMessage is None or SystemMessage is None:
            return "LLM 依赖未安装或初始化失败，请安装 langchain-openai。"

        try:
            resp = self.client.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            return str(resp.content or "").strip()
        except Exception as exc:
            return f"模型调用失败：{exc}"

    def stream_chat(self, *, system_prompt: str, user_prompt: str) -> Iterator[str]:
        if not self.enabled:
            yield "未配置 API KEY，当前无法调用大模型。"
            return
        if self.client is None or HumanMessage is None or SystemMessage is None:
            yield "LLM 依赖未安装或初始化失败，请安装 langchain-openai。"
            return

        try:
            for chunk in self.client.stream(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            ):
                content = chunk.content
                if isinstance(content, str):
                    if content:
                        yield content
                    continue

                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            text = str(part.get("text") or "")
                            if text:
                                yield text
                        else:
                            text = str(part or "")
                            if text:
                                yield text
        except Exception as exc:
            yield f"模型流式调用失败：{exc}"
