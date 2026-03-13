from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from ...config import Settings, load_json


class KGModule:
    def __init__(self, settings: Settings, project_root: Path) -> None:
        self.settings = settings
        self.project_root = project_root
        self.graph_path = settings.resolve_kg_graph_path(project_root)
        self.samples_path = settings.resolve_kg_samples_path(project_root)

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        graph_hits = self._search_graph(keywords, top_k=top_k)
        if graph_hits:
            return graph_hits

        # 图为空时回落到样例语料，保证知识图谱链路始终可用
        return self._search_samples(keywords, top_k=top_k)

    def _search_graph(self, keywords: List[str], top_k: int) -> List[Dict[str, Any]]:
        data = load_json(self.graph_path, {})
        nodes = data.get("nodes", []) if isinstance(data, dict) else []
        edges = data.get("edges", []) if isinstance(data, dict) else []
        if not isinstance(nodes, list):
            nodes = []
        if not isinstance(edges, list):
            edges = []

        results: List[Dict[str, Any]] = []
        for node in nodes:
            text = self._node_text(node)
            if not text:
                continue
            score = self._score_text(text, keywords)
            if score <= 0:
                continue
            results.append(
                {
                    "content": text[:400],
                    "source": "knowledge_graph",
                    "score": float(score),
                }
            )

        for edge in edges:
            text = self._edge_text(edge)
            if not text:
                continue
            score = self._score_text(text, keywords)
            if score <= 0:
                continue
            results.append(
                {
                    "content": text[:400],
                    "source": "knowledge_graph",
                    "score": float(score),
                }
            )

        results.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
        dedup: List[Dict[str, Any]] = []
        seen = set()
        for item in results:
            key = item["content"][:120]
            if key in seen:
                continue
            seen.add(key)
            dedup.append(item)
            if len(dedup) >= max(1, top_k):
                break
        return dedup

    def _search_samples(self, keywords: List[str], top_k: int) -> List[Dict[str, Any]]:
        data = load_json(self.samples_path, [])
        if not isinstance(data, list):
            return []
        scored: List[Dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            content = str(item.get("content") or "")
            source = str(item.get("source") or "kg_samples")
            text = f"{title}\n{content}".strip()
            score = self._score_text(text, keywords)
            if score <= 0:
                continue
            scored.append(
                {
                    "content": content[:400] if content else title[:200],
                    "source": source,
                    "score": float(score),
                }
            )
        scored.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
        return scored[: max(1, top_k)]

    @staticmethod
    def _extract_keywords(query: str) -> List[str]:
        text = str(query or "").strip()
        if not text:
            return []
        items = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        if not items:
            return [text]
        seen = set()
        out: List[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out

    @staticmethod
    def _score_text(text: str, keywords: List[str]) -> int:
        return sum(1 for kw in keywords if kw and kw in text)

    @staticmethod
    def _node_text(node: Any) -> str:
        if isinstance(node, str):
            return node
        if isinstance(node, dict):
            parts = [
                str(node.get("id") or ""),
                str(node.get("name") or ""),
                str(node.get("label") or ""),
                str(node.get("content") or ""),
            ]
            text = " ".join(p for p in parts if p).strip()
            return text
        return ""

    @staticmethod
    def _edge_text(edge: Any) -> str:
        if isinstance(edge, str):
            return edge
        if isinstance(edge, dict):
            parts = [
                str(edge.get("source") or ""),
                str(edge.get("target") or ""),
                str(edge.get("relation") or ""),
                str(edge.get("type") or ""),
            ]
            return " -> ".join(p for p in parts if p).strip()
        return ""
