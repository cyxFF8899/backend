from __future__ import annotations

import shutil
from itertools import islice
from pathlib import Path
from typing import Iterable

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config import Settings
from .loaders import load_documents_from_raw


class IndexService:
    def __init__(self, *, settings: Settings, project_root: Path) -> None:
        self.settings = settings
        self.project_root = project_root
        self.persist_dir = settings.resolve_chroma_dir(project_root)
        self.data_dir = settings.resolve_index_data_dir(project_root)
        self.collection_name = settings.chroma_collection_name
        self._embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model_name)

    def ensure_index(self) -> None:
        if self.is_ready():
            return
        if not self.settings.index_auto_build:
            return
        self.build(rebuild=False)

    def is_ready(self) -> bool:
        if not self.persist_dir.exists():
            return False
        if not any(self.persist_dir.iterdir()):
            return False
        try:
            count = self.count()
            return count > 0
        except Exception:
            return False

    def count(self) -> int:
        store = self.get_vectorstore()
        try:
            return int(store._collection.count())  # type: ignore[attr-defined]
        except Exception:
            raw = store.get(include=[])
            ids = raw.get("ids", []) if isinstance(raw, dict) else []
            return len(ids)

    def build(self, *, rebuild: bool = False) -> int:
        if rebuild and self.persist_dir.exists():
            shutil.rmtree(self.persist_dir, ignore_errors=True)

        self.persist_dir.mkdir(parents=True, exist_ok=True)

        docs = load_documents_from_raw(self.data_dir)
        if not docs:
            return 0

        chunks = self._split_documents(docs)
        if not chunks:
            return 0

        self._add_chunks(chunks)
        return self.count()

    def get_vectorstore(self) -> Chroma:
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        return Chroma(
            collection_name=self.collection_name,
            embedding_function=self._embeddings,
            persist_directory=str(self.persist_dir),
        )

    def _split_documents(self, docs: list[Document]) -> list[Document]:
        if not docs:
            return []

        chunk_size = max(120, int(self.settings.rag_chunk_size))
        chunk_overlap = max(0, int(self.settings.rag_chunk_overlap))
        if chunk_overlap >= chunk_size:
            chunk_overlap = max(0, chunk_size // 5)

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "；", "：", "，", " ", ""],
        )
        return splitter.split_documents(docs)

    def _add_chunks(self, chunks: list[Document], *, store: Chroma | None = None) -> None:
        if not chunks:
            return
        vectorstore = store or self.get_vectorstore()
        batch_size = max(1, int(self.settings.chroma_add_batch_size))
        for batch in _iter_batches(chunks, batch_size):
            vectorstore.add_documents(batch)


def _iter_batches(items: list[Document], batch_size: int) -> Iterable[list[Document]]:
    iterator = iter(items)
    while True:
        batch = list(islice(iterator, batch_size))
        if not batch:
            return
        yield batch
