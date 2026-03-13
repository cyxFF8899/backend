from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, Iterator, List

from ...config import Settings
from ...db import DB
from ..intent import IntentModule
from ..kg import KGModule
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
        intent: IntentModule,
        retrieval: RetrievalModule,
        kg: KGModule,
        router: RouterModule,
        prompt: PromptModule,
        llm: LLMModule,
    ) -> None:
        self.settings = settings
        self.db = db
        self.intent = intent
        self.retrieval = retrieval
        self.kg = kg
        self.router = router
        self.prompt = prompt
        self.llm = llm
        self._session_history: Dict[str, List[Dict[str, str]]] = {}

    def chat(
        self,
        *,
        query: str,
        user_id: str = "",
        session_id: str = "",
        location: str = "",
        rag: bool = True,
    ) -> Dict[str, Any]:
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
    ) -> Iterator[Dict[str, Any]]:
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

        chunks: List[str] = []
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
    ) -> Dict[str, Any]:
        clean_query = self._clean_text(query)
        if not clean_query:
            clean_query = str(query or "").strip()

        sid = self._ensure_session_id(session_id=session_id, user_id=user_id)
        history = self._clean_history(self._get_session_history(sid))

        if not rag:
            return {
                "mode": "direct_llm",
                "query": clean_query,
                "user_id": user_id,
                "session_id": sid,
                "location": location,
                "intent_packet": {},
                "target": "llm_direct",
                "history": history,
                "retrieval_hits": [],
                "kg_hits": [],
            }

        intent_packet = self.intent.predict(clean_query)
        target = self.router.derive_target(
            intent=str(intent_packet.get("intent", "")),
            domain=str(intent_packet.get("domain", "unclear")),
        )

        retrieval_hits = self._clean_hits(
            self.retrieval.search(query=clean_query, user_id=user_id, location=location)
        )
        kg_hits = self._clean_hits(self.kg.search(query=clean_query, top_k=3))

        return {
            "mode": "rag",
            "query": clean_query,
            "user_id": user_id,
            "session_id": sid,
            "location": location,
            "intent_packet": intent_packet,
            "target": target,
            "history": history,
            "retrieval_hits": retrieval_hits,
            "kg_hits": kg_hits,
        }

    def _generate_answer(self, context: Dict[str, Any]) -> str:
        if context["target"] == "handoff":
            return self._HANDOFF_ANSWER

        system_prompt, user_prompt = self._build_main_messages(context)
        answer = self.llm.chat(system_prompt=system_prompt, user_prompt=user_prompt).strip()
        if answer:
            return answer
        return self._fallback_answer(context)

    def _build_main_messages(self, context: Dict[str, Any]) -> tuple[str, str]:
        if context["mode"] == "direct_llm":
            return self.prompt.build_direct_messages(
                query=context["query"],
                history=context["history"],
            )
        return self.prompt.build_rag_messages(
            query=context["query"],
            intent_packet=context["intent_packet"],
            retrieval_hits=context["retrieval_hits"],
            kg_hits=context["kg_hits"],
            history=context["history"],
            target=context["target"],
        )

    def _build_response(self, *, context: Dict[str, Any], answer: str) -> Dict[str, Any]:
        citations = self._collect_citations(context["retrieval_hits"], context["kg_hits"])
        need_followup, followup_questions = self._build_followups(context=context, answer=answer)
        return {
            "answer": answer,
            "citations": citations,
            "need_followup": need_followup,
            "followup_questions": followup_questions,
            "session_id": context["session_id"],
        }

    def _build_followups(self, *, context: Dict[str, Any], answer: str) -> tuple[bool, List[str]]:
        if not answer.strip() or context["target"] == "handoff":
            return False, []

        system_prompt, user_prompt = self.prompt.build_followup_messages(
            query=context["query"],
            intent_packet=context["intent_packet"],
            target=context["target"],
            history=context["history"],
            retrieval_hits=context["retrieval_hits"],
            kg_hits=context["kg_hits"],
            answer=answer,
        )
        raw = self.llm.chat(system_prompt=system_prompt, user_prompt=user_prompt)
        followup_questions = self._parse_followup_questions(raw)
        return bool(followup_questions), followup_questions

    def _parse_followup_questions(self, raw: str) -> List[str]:
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

        questions: List[str] = []
        for item in questions_raw:
            question = self._clean_text(item)
            if not question or question in questions:
                continue
            questions.append(question)
            if len(questions) >= 3:
                break
        return questions

    @staticmethod
    def _parse_json_object(text: str) -> Dict[str, Any]:
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

    def _fallback_answer(self, context: Dict[str, Any]) -> str:
        snippets: List[str] = []
        for hit in context["retrieval_hits"][:2]:
            content = str(hit.get("content") or "").strip()
            if content:
                snippets.append(content)
        for hit in context["kg_hits"][:1]:
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
        self._append_session_history(session_id=session_id, query=query, answer=answer)
        self.db.save_chat(user_id=user_id or "", query=query, answer=answer)

    def _ensure_session_id(self, *, session_id: str, user_id: str) -> str:
        sid = str(session_id or "").strip()
        if sid:
            return sid
        uid = str(user_id or "anonymous").strip() or "anonymous"
        return f"sess_{uid}_{int(time.time() * 1000)}"

    def _get_session_history(self, session_id: str) -> List[Dict[str, str]]:
        return list(self._session_history.get(session_id, []))

    def _append_session_history(self, *, session_id: str, query: str, answer: str) -> None:
        if session_id not in self._session_history:
            self._session_history[session_id] = []
        self._session_history[session_id].append({"query": query, "answer": answer})
        self._session_history[session_id] = self._session_history[session_id][
            -self.settings.history_limit :
        ]

    @classmethod
    def _clean_text(cls, raw: Any) -> str:
        text = str(raw or "")
        text = cls._SYMBOL_PATTERN.sub("", text)
        text = cls._SPACE_PATTERN.sub(" ", text).strip()
        return text

    def _clean_history(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        cleaned: List[Dict[str, str]] = []
        for turn in history:
            if not isinstance(turn, dict):
                continue
            item: Dict[str, str] = {}
            for key in ("query", "answer", "role", "content"):
                if key not in turn:
                    continue
                value = self._clean_text(turn.get(key, ""))
                if value:
                    item[key] = value
            if item:
                cleaned.append(item)
        return cleaned

    def _clean_hits(self, hits: Any) -> List[Dict[str, Any]]:
        if not isinstance(hits, list):
            return []

        cleaned: List[Dict[str, Any]] = []
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

            item: Dict[str, Any] = {
                "content": content,
                "source": source or "unknown",
                "score": self._normalize_score(hit.get("score", 0.0)),
            }
            title = self._clean_text(hit.get("title", ""))
            if title:
                item["title"] = title
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

    def _collect_citations(
        self, retrieval_hits: List[Dict[str, Any]], kg_hits: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen = set()
        for hit in retrieval_hits + kg_hits:
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
