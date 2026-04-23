from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..config import Settings
from .index_service import IndexService


class Retriever:
    def __init__(self, *, settings: Settings, project_root: Path, index_service: IndexService) -> None:
        self.settings = settings
        self.project_root = project_root
        self.index_service = index_service

    def search(self, query: str, k: int | None = None, location: str = "") -> list[dict[str, Any]]:
        text = str(query or "").strip()
        if not text:
            return []

        if not self.index_service.is_ready():
            self.index_service.ensure_index()
            if not self.index_service.is_ready():
                return []

        vectorstore = self.index_service.get_vectorstore()
        top_k = max(1, int(k or self.settings.top_k_hits))
        candidate_k = max(top_k * 8, 20)
        clean_location = self._clean_location(location)

        # 带地区先检索一轮，再用原问题兜底，提升命中率同时保持兼容。
        queries = self._build_query_variants(text=text, location=clean_location)
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for q in queries:
            for hit in self._search_once(vectorstore=vectorstore, query=q, top_k=candidate_k):
                key = (str(hit.get("source") or ""), str(hit.get("content") or "")[:120])
                old = merged.get(key)
                if old is None or float(hit.get("score", 0.0)) > float(old.get("score", 0.0)):
                    merged[key] = hit

        hits = list(merged.values())
        keywords = self._query_keywords(text)
        if keywords:
            matched = [x for x in hits if self._keyword_coverage(str(x.get("content") or ""), keywords) > 0]
            if matched:
                hits = matched
        if clean_location:
            self._apply_location_boost(hits=hits, location=clean_location)
        self._apply_quality_adjustments(hits=hits, query=text)

        hits.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
        return hits[:top_k]

    def _search_once(self, *, vectorstore: Any, query: str, top_k: int) -> list[dict[str, Any]]:
        try:
            docs_scores = vectorstore.similarity_search_with_relevance_scores(query, k=top_k)
            return self._normalize_results(docs_scores, score_mode="relevance", max_items=top_k)
        except Exception:
            try:
                docs_scores = vectorstore.similarity_search_with_score(query, k=top_k)
                return self._normalize_results(docs_scores, score_mode="distance", max_items=top_k)
            except Exception:
                return []

    @staticmethod
    def _clean_location(location: str) -> str:
        return str(location or "").strip().replace("\n", " ").replace("\r", " ")[:32]

    @staticmethod
    def _build_query_variants(*, text: str, location: str) -> list[str]:
        if not location:
            return [text]
        if location in text:
            return [text]
        return [f"{location} {text}", text]

    def _apply_location_boost(self, *, hits: list[dict[str, Any]], location: str) -> None:
        for hit in hits:
            if not self._hit_matches_location(hit=hit, location=location):
                continue
            score = float(hit.get("score", 0.0))
            hit["score"] = round(min(1.0, score + 0.08), 4)
            metadata = hit.get("metadata")
            if isinstance(metadata, dict):
                metadata["location_match"] = True
            else:
                hit["metadata"] = {"location_match": True}

    @staticmethod
    def _hit_matches_location(*, hit: dict[str, Any], location: str) -> bool:
        content = str(hit.get("content") or "")
        source = str(hit.get("source") or "")
        if location in content or location in source:
            return True
        metadata = hit.get("metadata", {})
        if isinstance(metadata, dict):
            for value in metadata.values():
                if location in str(value or ""):
                    return True
        return False

    @classmethod
    def _apply_quality_adjustments(cls, *, hits: list[dict[str, Any]], query: str) -> None:
        keywords = cls._query_keywords(query)
        for hit in hits:
            content = str(hit.get("content") or "")
            score = float(hit.get("score", 0.0))

            if cls._looks_like_link_list(content):
                score *= 0.65
            if cls._looks_like_json_fragment(content):
                score *= 0.82
            if keywords and cls._keyword_coverage(content, keywords) > 0:
                score += 0.1

            hit["score"] = round(max(0.0, min(1.0, score)), 4)

    @staticmethod
    def _query_keywords(query: str) -> list[str]:
        q = str(query or "").strip()
        if not q:
            return []

        cleaned = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", q)
        stop_phrases = ("如何", "怎么", "怎样", "请问", "防治", "防控", "措施", "方法", "技术")
        for s in stop_phrases:
            cleaned = cleaned.replace(s, "")

        terms: set[str] = set()
        if len(cleaned) >= 2:
            for size in (2, 3, 4):
                for i in range(0, max(0, len(cleaned) - size + 1)):
                    t = cleaned[i : i + size]
                    if t:
                        terms.add(t)
        if len(cleaned) >= 2:
            terms.add(cleaned)
        return sorted((t for t in terms if len(t) >= 2), key=len, reverse=True)[:12]

    @staticmethod
    def _keyword_coverage(content: str, keywords: list[str]) -> int:
        text = str(content or "")
        return sum(1 for kw in keywords if kw in text)

    @staticmethod
    def _looks_like_link_list(content: str) -> bool:
        text = str(content or "").strip()
        if not text:
            return False
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return False
        url_lines = sum(1 for ln in lines if ln.startswith("http://") or ln.startswith("https://"))
        if url_lines >= 2 and url_lines / len(lines) >= 0.6:
            return True
        return False

    @staticmethod
    def _looks_like_json_fragment(content: str) -> bool:
        text = str(content or "")
        marker_count = text.count("{") + text.count("}") + text.count("\\\"") + text.count('":')
        return marker_count >= 8

    def _normalize_results(
        self,
        docs_scores: list[tuple[Any, float]],
        *,
        score_mode: str,
        max_items: int,
    ) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for doc, raw_score in docs_scores:
            content = str(getattr(doc, "page_content", "") or "").strip()
            if not content:
                continue

            metadata = dict(getattr(doc, "metadata", {}) or {})
            source = "knowledge_base"
            question = str(metadata.get("question") or "").strip()
            record_id = str(metadata.get("record_id") or "").strip()

            key = (source, content[:120])
            if key in seen:
                continue
            seen.add(key)

            if score_mode == "distance":
                # 距离越小代表越相关，这里统一转换为 0~1 的相关度。
                score = 1.0 / (1.0 + max(0.0, float(raw_score)))
            else:
                score = float(raw_score)

            score = max(0.0, min(1.0, score))
            item = {
                "content": content[: self.settings.hit_max_chars],
                "source": source,
                "score": round(score, 4),
                "metadata": {
                    "question": question,
                    "record_id": record_id,
                },
            }
            hits.append(item)
            if len(hits) >= max_items:
                break

        return hits
