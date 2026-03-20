from __future__ import annotations

from pathlib import Path
from typing import Any

from ...config import Settings


class GraphModule:
    """图数据模块（独立于 RAG）。

    当前先提供最小占位实现，后续可在这里接入 Neo4j 查询。
    """

    def __init__(self, settings: Settings, project_root: Path) -> None:
        _ = settings, project_root

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        _ = query, limit
        return []
