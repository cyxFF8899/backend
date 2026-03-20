from __future__ import annotations

import json
import re
import time
from typing import Any, Iterator

from ...config import Settings
from ...db import DB
from ...repositories import ChatRepository
from ..intent import IntentModule
from ..retrieval import RetrievalModule
from .llm import LLMModule
from .prompt import PromptModule
from .router import RouterModule


class ChatModule:
    _EMPTY_ANSWER = "当前暂时无法生成答案，请稍后重试。"
    _HANDOFF_ANSWER = "当前问题不在农业问答范围内，请补充农业相关问题。"
    _SYMBOL_PATTERN = re.compile(r"[{}\[\]\\\"'“”‘’`]")
    _SPACE_PATTERN = re.compile(r"\s+")

    def __init__(
        self,
        *,
        settings: Settings,
        db: DB,
        chat_repo: ChatRepository,
        intent: IntentModule,
        retrieval: RetrievalModule,
        router: RouterModule,
        prompt: PromptModule,
        llm: LLMModule,
    ) -> None:
        self.settings = settings
        self.db = db
        self.chat_repo = chat_repo
        self.intent = intent
        self.retrieval = retrieval
        self.router = router
        self.prompt = prompt
        self.llm = llm

    def chat(
        self,
        *,
        query: str,
        user_id: str = "",
        session_id: str = "",
        location: str = "",
        rag: bool = True,
    ) -> dict[str, Any]:
        context = self._build_context(
            query=query,
            user_id=user_id,
            session_id=session_id,
            location=location,
            rag=rag,
        )
        answer = self._generate_answer(context)
        self._save_turn(
            session_id=context["session_id"],
            user_id=context["user_id"],
            query=context["query"],
            answer=answer,
        )
        return self._build_response(context=context, answer=answer)

    def stream_chat(
        self,
        *,
        query: str,
        user_id: str = "",
        session_id: str = "",
        location: str = "",
        rag: bool = True,
    ) -> Iterator[dict[str, Any]]:
        context = self._build_context(
            query=query,
            user_id=user_id,
            session_id=session_id,
            location=location,
            rag=rag,
        )

        if context["target"] == "handoff":
            answer = self._HANDOFF_ANSWER
            self._save_turn(
                session_id=context["session_id"],
                user_id=context["user_id"],
                query=context["query"],
                answer=answer,
            )
            yield {"type": "done", "data": self._build_response(context=context, answer=answer)}
            return

        system_prompt, user_prompt = self._build_main_messages(context)

        chunks: list[str] = []
        for token in self.llm.stream_chat(system_prompt=system_prompt, user_prompt=user_prompt):
            if not token:
                continue
            chunks.append(token)
            yield {"type": "chunk", "content": token}
            if self.settings.stream_chunk_sleep_ms > 0:
                time.sleep(self.settings.stream_chunk_sleep_ms / 1000.0)

        answer = "".join(chunks).strip()
        if not answer:
            answer = self.llm.chat(system_prompt=system_prompt, user_prompt=user_prompt).strip()
            if not answer:
                answer = self._fallback_answer(context)

        self._save_turn(
            session_id=context["session_id"],
            user_id=context["user_id"],
            query=context["query"],
            answer=answer,
        )
        yield {"type": "done", "data": self._build_response(context=context, answer=answer)}

    def _build_context(
        self,
        *,
        query: str,
        user_id: str,
        session_id: str,
        location: str,
        rag: bool,
    ) -> dict[str, Any]:
        clean_query = self._clean_text(query) or str(query or "").strip()
        clean_location = self._clean_location(location)
        sid = self._ensure_session_id(session_id=session_id, user_id=user_id)

        history_limit = max(2, int(self.settings.context_window_turns) * 2)
        history = self._clean_history(self.chat_repo.list_recent(session_id=sid, limit=history_limit))

        if not rag:
            return {
                "mode": "direct_llm",
                "query": clean_query,
                "user_id": user_id,
                "session_id": sid,
                "location": clean_location,
                "intent_packet": {},
                "target": "llm_direct",
                "history": history,
                "retrieval_hits": [],
            }

        intent_packet = self.intent.predict(clean_query)
        target = self.router.derive_target(
            intent=str(intent_packet.get("intent", "")),
        )

        retrieval_hits: list[dict[str, Any]] = []
        if target == "agri_expert":
            retrieval_hits = self._clean_hits(
                self.retrieval.search(query=clean_query, user_id=user_id, location=clean_location)
            )

        return {
            "mode": "rag",
            "query": clean_query,
            "user_id": user_id,
            "session_id": sid,
            "location": clean_location,
            "intent_packet": intent_packet,
            "target": target,
            "history": history,
            "retrieval_hits": retrieval_hits,
        }

    def _generate_answer(self, context: dict[str, Any]) -> str:
        if context["target"] == "handoff":
            return self._HANDOFF_ANSWER

        system_prompt, user_prompt = self._build_main_messages(context)
        answer = self.llm.chat(system_prompt=system_prompt, user_prompt=user_prompt).strip()
        if answer:
            return answer
        return self._fallback_answer(context)

    def _build_main_messages(self, context: dict[str, Any]) -> tuple[str, str]:
        if context["mode"] == "direct_llm":
            return self.prompt.build_direct_messages(
                query=context["query"],
                history=context["history"],
                location=context["location"],
            )

        return self.prompt.build_rag_messages(
            query=context["query"],
            location=context["location"],
            intent_packet=context["intent_packet"],
            retrieval_hits=context["retrieval_hits"],
            history=context["history"],
            target=context["target"],
        )

    def _build_response(self, *, context: dict[str, Any], answer: str) -> dict[str, Any]:
        citations = self._collect_citations(context["retrieval_hits"])
        need_followup, followup_questions = self._build_followups(context=context, answer=answer)
        return {
            "answer": answer,
            "citations": citations,
            "need_followup": need_followup,
            "followup_questions": followup_questions,
            "session_id": context["session_id"],
        }

    def _build_followups(self, *, context: dict[str, Any], answer: str) -> tuple[bool, list[str]]:
        if not answer.strip() or context["target"] in {"handoff", "clarify"}:
            return False, []

        system_prompt, user_prompt = self.prompt.build_followup_messages(
            query=context["query"],
            location=context["location"],
            intent_packet=context["intent_packet"],
            target=context["target"],
            history=context["history"],
            retrieval_hits=context["retrieval_hits"],
            answer=answer,
        )
        raw = self.llm.chat(system_prompt=system_prompt, user_prompt=user_prompt)
        questions = self._parse_followup_questions(raw)
        return bool(questions), questions

    def _parse_followup_questions(self, raw: str) -> list[str]:
        text = str(raw or "").strip()
        if not text:
            return []

        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()

        data = self._parse_json_object(text)
        if not data or not bool(data.get("need_followup", False)):
            return []

        questions_raw = data.get("followup_questions", [])
        if not isinstance(questions_raw, list):
            return []

        limit = max(1, int(self.settings.followup_max_questions))
        questions: list[str] = []
        for item in questions_raw:
            question = self._clean_text(item)
            if not question or question in questions:
                continue
            questions.append(question)
            if len(questions) >= limit:
                break
        return questions

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end <= start:
                return {}
            snippet = text[start : end + 1]
            try:
                parsed = json.loads(snippet)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}

    def _fallback_answer(self, context: dict[str, Any]) -> str:
        snippets: list[str] = []
        for hit in context["retrieval_hits"][:2]:
            content = str(hit.get("content") or "").strip()
            if content:
                snippets.append(content)
        if snippets:
            return "未获取到稳定模型回复，先给你可参考信息：\n" + "\n".join(
                f"{i + 1}. {text}" for i, text in enumerate(snippets)
            )
        return self._EMPTY_ANSWER

    def _save_turn(self, *, session_id: str, user_id: str, query: str, answer: str) -> None:
        if not query.strip():
            return

        self.chat_repo.append_message(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=query,
        )
        self.chat_repo.append_message(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            content=answer,
        )

        # Keep legacy table in sync for compatibility with existing tooling.
        self.db.save_chat(user_id=user_id or "", query=query, answer=answer)

    @staticmethod
    def _ensure_session_id(*, session_id: str, user_id: str) -> str:
        sid = str(session_id or "").strip()
        if sid:
            return sid
        uid = str(user_id or "anonymous").strip() or "anonymous"
        return f"sess_{uid}_{int(time.time() * 1000)}"

    @classmethod
    def _clean_text(cls, raw: Any) -> str:
        text = str(raw or "")
        text = cls._SYMBOL_PATTERN.sub("", text)
        text = cls._SPACE_PATTERN.sub(" ", text).strip()
        return text

    @classmethod
    def _clean_location(cls, raw: Any) -> str:
        return cls._clean_text(raw)[:32]

    def _clean_history(self, history: list[dict[str, Any]]) -> list[dict[str, str]]:
        cleaned: list[dict[str, str]] = []
        for turn in history:
            if not isinstance(turn, dict):
                continue
            role = str(turn.get("role") or "").strip().lower()
            content = self._clean_text(turn.get("content", ""))
            if role not in {"user", "assistant"} or not content:
                continue
            cleaned.append({"role": role, "content": content})
        return cleaned

    def _clean_hits(self, hits: Any) -> list[dict[str, Any]]:
        if not isinstance(hits, list):
            return []

        cleaned: list[dict[str, Any]] = []
        seen = set()
        for hit in hits:
            if not isinstance(hit, dict):
                continue

            content = self._clean_text(hit.get("content", ""))
            source = self._clean_text(hit.get("source", ""))
            if not content:
                continue

            key = (source, content[:120])
            if key in seen:
                continue
            seen.add(key)

            item: dict[str, Any] = {
                "content": content,
                "source": source or "unknown",
                "score": self._normalize_score(hit.get("score", 0.0)),
            }
            metadata = hit.get("metadata", {})
            if isinstance(metadata, dict):
                item["metadata"] = metadata
            cleaned.append(item)

        return cleaned

    @staticmethod
    def _normalize_score(raw: Any) -> float:
        if isinstance(raw, bool):
            return 0.0
        if isinstance(raw, (int, float)):
            score = float(raw)
        elif isinstance(raw, str):
            value = raw.strip()
            if not value:
                return 0.0
            try:
                score = float(value)
            except ValueError:
                return 0.0
        else:
            return 0.0

        if score < 0:
            return 0.0
        if score > 1:
            return 1.0
        return round(score, 4)

    def _collect_citations(self, retrieval_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen = set()
        for hit in retrieval_hits:
            content = str(hit.get("content") or "").strip()
            source = str(hit.get("source") or "").strip()
            if not content:
                continue
            key = (content[:120], source)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "content": content,
                    "source": source,
                    "score": self._normalize_score(hit.get("score", 0.0)),
                }
            )
            if len(items) >= 5:
                break
        return items
