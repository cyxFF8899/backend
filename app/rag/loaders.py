from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from langchain_core.documents import Document

try:
    from langchain_unstructured import UnstructuredLoader
except Exception:  # pragma: no cover
    UnstructuredLoader = None  # type: ignore


def load_documents_from_raw(data_dir: Path) -> list[Document]:
    if not data_dir.exists():
        return []

    documents: list[Document] = []
    enable_unstructured = os.getenv("ENABLE_UNSTRUCTURED_LOADER", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    for path in sorted(data_dir.iterdir()):
        if path.is_dir():
            continue
        name_lower = path.name.lower()
        # Skip temporary/training dump files; they are noisy for online retrieval.
        if name_lower.startswith(("tmp", "train_")):
            continue
        suffix = path.suffix.lower()
        if suffix == ".json":
            documents.extend(_load_json_qa(path))
            continue
        if suffix == ".csv":
            documents.extend(_load_csv_file(path))
            continue
        if suffix in {".txt", ".md"}:
            documents.extend(_load_text_file(path))
            continue
        if suffix in {".pdf", ".doc", ".docx"} and enable_unstructured:
            documents.extend(_load_unstructured_file(path))
    return documents


def _load_json_qa(path: Path) -> list[Document]:
    out: list[Document] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return out

    if not isinstance(payload, list):
        return out

    for item in payload:
        if not isinstance(item, dict):
            continue
        conv = item.get("conversations")
        if not isinstance(conv, list):
            continue

        user_value = ""
        assistant_value = ""
        for turn in conv:
            if not isinstance(turn, dict):
                continue
            from_role = str(turn.get("from") or "").strip().lower()
            value = str(turn.get("value") or "").strip()
            if not value:
                continue
            if from_role == "user" and not user_value:
                user_value = value
            elif from_role == "assistant" and not assistant_value:
                assistant_value = value
            if user_value and assistant_value:
                break

        if not user_value and not assistant_value:
            continue

        page_content = f"问题：{user_value}\n回答：{assistant_value}" if assistant_value else f"问题：{user_value}"
        if _looks_garbled_text(page_content):
            continue

        out.append(
            Document(
                page_content=page_content,
                metadata={
                    "source": str(path),
                    "record_id": str(item.get("id") or ""),
                    "doc_type": "qa_json",
                    "question": user_value,
                },
            )
        )
    return out


def _load_unstructured_file(path: Path) -> list[Document]:
    if UnstructuredLoader is None:
        return []

    try:
        try:
            loader = UnstructuredLoader(file_path=str(path))
        except TypeError:
            loader = UnstructuredLoader(str(path))
        docs = loader.load()
    except Exception:
        return []

    normalized: list[Document] = []
    for d in docs:
        content = str(getattr(d, "page_content", "") or "").strip()
        if not content:
            continue
        meta = dict(getattr(d, "metadata", {}) or {})
        meta.setdefault("source", str(path))
        meta.setdefault("doc_type", "file")
        normalized.append(Document(page_content=content, metadata=meta))
    return normalized


def _load_text_file(path: Path) -> list[Document]:
    try:
        content = path.read_text(encoding="utf-8").strip()
    except Exception:
        return []
    if not content:
        return []
    if _looks_garbled_text(content):
        return []
    return [
        Document(
            page_content=content,
            metadata={
                "source": str(path),
                "doc_type": "text_file",
            },
        )
    ]


def _load_csv_file(path: Path) -> list[Document]:
    rows: list[Document] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = [x for x in (reader.fieldnames or []) if x]

            for idx, row in enumerate(reader, start=1):
                if not isinstance(row, dict):
                    continue

                pieces: list[str] = []
                for field in fieldnames:
                    value = str(row.get(field) or "").strip()
                    if value:
                        pieces.append(f"{field}: {value}")
                if not pieces:
                    continue
                page_content = "\n".join(pieces)
                if _looks_garbled_text(page_content):
                    continue

                rows.append(
                    Document(
                        page_content=page_content,
                        metadata={
                            "source": str(path),
                            "doc_type": "csv_row",
                            "record_id": str(idx),
                        },
                    )
                )
    except Exception:
        return []

    return rows


def _looks_garbled_text(text: str) -> bool:
    sample = str(text or "").strip()
    if not sample:
        return False
    sample = sample[:2000]

    # Common mojibake patterns from UTF-8 text decoded with a legacy charset.
    suspicious_chars = sum(1 for ch in sample if "\u00C0" <= ch <= "\u00FF")
    replacement_chars = sample.count("�")
    ratio = (suspicious_chars + replacement_chars * 2) / max(1, len(sample))
    return ratio >= 0.12
