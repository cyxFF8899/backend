from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# 统一加载环境变量，支持项目根目录或 backend 目录下的 .env
load_dotenv()


@dataclass
class Settings:
    """系统运行配置：集中管理路径与可调参数。"""

    app_name: str = "Agri Backend"
    db_path: str = "backend/data/chat.db"
    intent_resources_dir: str = "IntentRecognition/semantic/resources"
    kg_graph_path: str = "KnowledgeRetrieval/knowledge_base/knowledge_graph.json"
    kg_samples_path: str = "KnowledgeGraph/data/samples/samples.json"

    # LLM 配置（默认走 DashScope OpenAI 兼容接口）
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3.5-flash"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1200

    top_k_hits: int = 4
    hit_max_chars: int = 700
    stream_chunk_sleep_ms: int = 0
    history_limit: int = 6

    # 与原规则保持一致的默认权重
    weight_disease_pest: float = 1.0
    weight_climate: float = 1.0
    weight_management: float = 1.0
    weight_product: float = 1.5
    weight_hint_bonus: float = 0.4
    weight_crop_bonus: float = 0.2

    fuzzy_enabled: bool = True
    fuzzy_max_distance: int = 1
    fuzzy_max_term_len: int = 4

    @classmethod
    def from_env(cls) -> "Settings":
        # 允许通过 .env 或系统环境变量覆盖默认值
        return cls(
            app_name=os.getenv("APP_NAME", "Agri Backend").strip(),
            db_path=os.getenv("DB_PATH", "backend/data/chat.db").strip(),
            intent_resources_dir=os.getenv(
                "INTENT_RESOURCES_DIR", "IntentRecognition/semantic/resources"
            ).strip(),
            kg_graph_path=os.getenv(
                "KG_GRAPH_PATH", "KnowledgeRetrieval/knowledge_base/knowledge_graph.json"
            ).strip(),
            kg_samples_path=os.getenv(
                "KG_SAMPLES_PATH", "KnowledgeGraph/data/samples/samples.json"
            ).strip(),
            llm_api_key=os.getenv("DASHSCOPE_API_KEY", "").strip(),
            llm_base_url=os.getenv(
                "DASHSCOPE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ).strip(),
            llm_model=os.getenv("DASHSCOPE_MODEL", "qwen3.5-plus").strip(),
            llm_temperature=_safe_float(os.getenv("DASHSCOPE_TEMPERATURE"), 0.2),
            llm_max_tokens=_safe_int(os.getenv("DASHSCOPE_MAX_TOKENS"), 1200),
            top_k_hits=_safe_int(os.getenv("TOP_K_HITS"), 4),
            hit_max_chars=_safe_int(os.getenv("HIT_MAX_CHARS"), 700),
            stream_chunk_sleep_ms=_safe_int(os.getenv("STREAM_CHUNK_SLEEP_MS"), 0),
            history_limit=_safe_int(os.getenv("HISTORY_LIMIT"), 6),
            weight_disease_pest=_safe_float(os.getenv("WEIGHT_DISEASE_PEST"), 1.0),
            weight_climate=_safe_float(os.getenv("WEIGHT_CLIMATE"), 1.0),
            weight_management=_safe_float(os.getenv("WEIGHT_MANAGEMENT"), 1.0),
            weight_product=_safe_float(os.getenv("WEIGHT_PRODUCT"), 1.5),
            weight_hint_bonus=_safe_float(os.getenv("WEIGHT_HINT_BONUS"), 0.4),
            weight_crop_bonus=_safe_float(os.getenv("WEIGHT_CROP_BONUS"), 0.2),
            fuzzy_enabled=_safe_bool(os.getenv("FUZZY_ENABLED"), True),
            fuzzy_max_distance=_safe_int(os.getenv("FUZZY_MAX_DISTANCE"), 1),
            fuzzy_max_term_len=_safe_int(os.getenv("FUZZY_MAX_TERM_LEN"), 4),
        )

    def resolve_resources_dir(self, project_root: Path) -> Path:
        p = Path(self.intent_resources_dir)
        if p.is_absolute():
            return p
        return (project_root / p).resolve()

    def resolve_kg_graph_path(self, project_root: Path) -> Path:
        p = Path(self.kg_graph_path)
        if p.is_absolute():
            return p
        return (project_root / p).resolve()

    def resolve_kg_samples_path(self, project_root: Path) -> Path:
        p = Path(self.kg_samples_path)
        if p.is_absolute():
            return p
        return (project_root / p).resolve()


def _safe_int(v: str | None, default: int) -> int:
    try:
        return int(v) if v is not None and str(v).strip() else default
    except ValueError:
        return default


def _safe_float(v: str | None, default: float) -> float:
    try:
        return float(v) if v is not None and str(v).strip() else default
    except ValueError:
        return default


def _safe_bool(v: str | None, default: bool) -> bool:
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return default


def load_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default
