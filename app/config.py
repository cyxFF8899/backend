from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    app_name: str = "Agri Backend"
    db_path: str = "backend/data/chat.db"

    # LLM (OpenAI-compatible API)
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3.5-plus"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1200

    # RAG index and retrieval
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    embedding_hf_endpoint: str = "https://hf-mirror.com"
    chroma_persist_dir: str = "backend/data/chroma"
    chroma_collection_name: str = "agri_knowledge"
    index_data_dir: str = "backend/data/raw"
    index_auto_build: bool = True
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 80
    chroma_add_batch_size: int = 128
    top_k_hits: int = 3
    hit_max_chars: int = 700

    # Chat orchestration
    context_window_turns: int = 5
    stream_chunk_sleep_ms: int = 0
    followup_max_questions: int = 3

    # Intent module
    intent_model_dir: str = "backend/models/intent/best_model"
    intent_mapping_path: str = "backend/models/intent/best_model/intent_to_id.json"
    intent_confidence_threshold: float = 0.7
    non_agri_keywords_csv: str = (
        "python,java,代码,编程,股票,基金,币圈,以太坊,比特币,娱乐新闻,明星八卦,"
        "足球比分,篮球比分,电影票房,旅游攻略,恋爱建议"
    )
    agri_keywords_csv: str = (
        "农业,作物,种植,播种,施肥,灌溉,病虫害,农药,农资,水稻,小麦,玉米,果树,蔬菜,大棚,"
        "苗情,墒情,农产品,收购,产量,农机"
    )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", "Agri Backend").strip(),
            db_path=os.getenv("DB_PATH", "backend/data/chat.db").strip(),
            llm_api_key=(
                os.getenv("DASHSCOPE_API_KEY", "").strip()
                or os.getenv("OPENAI_API_KEY", "").strip()
                or os.getenv("LLM_API_KEY", "").strip()
            ),
            llm_base_url=os.getenv(
                "DASHSCOPE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ).strip(),
            llm_model=os.getenv("DASHSCOPE_MODEL", "qwen3.5-plus").strip(),
            llm_temperature=_safe_float(os.getenv("DASHSCOPE_TEMPERATURE"), 0.2),
            llm_max_tokens=_safe_int(os.getenv("DASHSCOPE_MAX_TOKENS"), 1200),
            embedding_model_name=os.getenv(
                "EMBEDDING_MODEL_NAME", "BAAI/bge-small-zh-v1.5"
            ).strip(),
            embedding_hf_endpoint=os.getenv(
                "EMBEDDING_HF_ENDPOINT", "https://hf-mirror.com"
            ).strip(),
            chroma_persist_dir=os.getenv("CHROMA_PERSIST_DIR", "backend/data/chroma").strip(),
            chroma_collection_name=os.getenv("CHROMA_COLLECTION_NAME", "agri_knowledge").strip(),
            index_data_dir=os.getenv("INDEX_DATA_DIR", "backend/data/raw").strip(),
            index_auto_build=_safe_bool(os.getenv("INDEX_AUTO_BUILD"), True),
            rag_chunk_size=_safe_int(os.getenv("RAG_CHUNK_SIZE"), 380),
            rag_chunk_overlap=_safe_int(os.getenv("RAG_CHUNK_OVERLAP"), 60),
            chroma_add_batch_size=_safe_int(os.getenv("CHROMA_ADD_BATCH_SIZE"), 128),
            top_k_hits=_safe_int(os.getenv("TOP_K_HITS"), 3),
            hit_max_chars=_safe_int(os.getenv("HIT_MAX_CHARS"), 700),
            context_window_turns=_safe_int(os.getenv("CONTEXT_WINDOW_TURNS"), 5),
            stream_chunk_sleep_ms=_safe_int(os.getenv("STREAM_CHUNK_SLEEP_MS"), 0),
            followup_max_questions=_safe_int(os.getenv("FOLLOWUP_MAX_QUESTIONS"), 3),
            intent_model_dir=os.getenv(
                "INTENT_MODEL_DIR", "backend/models/intent/best_model"
            ).strip(),
            intent_mapping_path=os.getenv(
                "INTENT_MAPPING_PATH", "backend/models/intent/best_model/intent_to_id.json"
            ).strip(),
            intent_confidence_threshold=_safe_float(
                os.getenv("INTENT_CONFIDENCE_THRESHOLD"), 0.7
            ),
            non_agri_keywords_csv=os.getenv("NON_AGRI_KEYWORDS_CSV", "").strip()
            or cls.non_agri_keywords_csv,
            agri_keywords_csv=os.getenv("AGRI_KEYWORDS_CSV", "").strip()
            or cls.agri_keywords_csv,
        )

    def resolve_db_path(self, project_root: Path) -> Path:
        return _resolve_path(project_root, self.db_path)

    def resolve_chroma_dir(self, project_root: Path) -> Path:
        return _resolve_path(project_root, self.chroma_persist_dir)

    def resolve_index_data_dir(self, project_root: Path) -> Path:
        return _resolve_path(project_root, self.index_data_dir)

    def resolve_intent_model_dir(self, project_root: Path) -> Path:
        return _resolve_path(project_root, self.intent_model_dir)

    def resolve_intent_mapping_path(self, project_root: Path) -> Path:
        return _resolve_path(project_root, self.intent_mapping_path)

    def non_agri_keywords(self) -> list[str]:
        return _parse_csv_keywords(self.non_agri_keywords_csv)

    def agri_keywords(self) -> list[str]:
        return _parse_csv_keywords(self.agri_keywords_csv)


def _resolve_path(project_root: Path, value: str) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    return (project_root / p).resolve()


def _parse_csv_keywords(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


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
