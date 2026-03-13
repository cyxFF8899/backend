from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

from ...config import Settings


class RetrievalModule:
    def __init__(self, settings: Settings, project_root: Path) -> None:
        self.settings = settings
        self.project_root = project_root
        self._retriever: Any | None = None
        self._init_error: str | None = None

    def _get_retriever(self) -> Any | None:
        if self._retriever is not None:
            return self._retriever
        if self._init_error is not None:
            return None

        try:
            # KnowledgeRetrieval 原代码用 from src.xxx 导入，这里补一个最小路径桥接
            retrieval_root = self.project_root / "KnowledgeRetrieval"
            if str(retrieval_root) not in sys.path:
                sys.path.append(str(retrieval_root))
            from src.retrieval.three_channel_retrieval import ThreeChannelRetrieval  # type: ignore

            self._retriever = ThreeChannelRetrieval()
            return self._retriever
        except Exception as exc:
            self._init_error = str(exc)
            return None

    def search(self, *, query: str, user_id: str, location: str = "") -> List[Dict[str, Any]]:
        retriever = self._get_retriever()
        if retriever is None:
            return []

        try:
            raw = retriever.retrieve(
                question=query,
                location=location,
                user_id=user_id or "default",
                include_multimodal=False,
                include_realtime=False,
            )
        except Exception:
            return []

        results = raw.get("results", []) if isinstance(raw, dict) else []
        if not isinstance(results, list):
            return []

        cleaned: List[Dict[str, Any]] = []
        seen = set()
        for item in results:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue

            source = str(
                item.get("channel")
                or item.get("source")
                or (item.get("metadata", {}) or {}).get("source")
                or "retrieval"
            ).strip()
            key = (source, content[:120])
            if key in seen:
                continue
            seen.add(key)

            hit: Dict[str, Any] = {
                "content": content[: self.settings.hit_max_chars],
                "source": source,
            }
            score = item.get("score")
            if isinstance(score, (int, float)):
                hit["score"] = float(score)

            title = str(item.get("title") or "").strip()
            if title:
                hit["title"] = title

            cleaned.append(hit)
            if len(cleaned) >= self.settings.top_k_hits:
                break
        return cleaned
