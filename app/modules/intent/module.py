from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import torch
from torch import nn
from transformers import BertConfig, BertModel, BertTokenizer

from ...config import Settings


class _IntentModelAdapter(nn.Module):
    def __init__(self, config: BertConfig, num_labels: int) -> None:
        super().__init__()
        self.bert = BertModel(config)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        self.classifier = nn.Linear(config.hidden_size, num_labels)

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.pooler_output
        pooled_output = self.dropout(pooled_output)
        return self.classifier(pooled_output)


class IntentModule:
    def __init__(self, settings: Settings, project_root: Path) -> None:
        self.settings = settings
        self.project_root = project_root

        self.model_dir = settings.resolve_intent_model_dir(project_root)
        self.mapping_path = settings.resolve_intent_mapping_path(project_root)
        self.threshold = float(settings.intent_confidence_threshold)

        self.non_agri_keywords = settings.non_agri_keywords()
        self.agri_keywords = settings.agri_keywords()

        self.intent_to_id: dict[str, int] = {}
        self.id_to_intent: dict[int, str] = {}

        self.device = torch.device("cpu")
        self.tokenizer: BertTokenizer | None = None
        self.model: _IntentModelAdapter | None = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            with self.mapping_path.open("r", encoding="utf-8") as f:
                mapping = json.load(f)
            if not isinstance(mapping, dict):
                return

            self.intent_to_id = {str(k): int(v) for k, v in mapping.items()}
            self.id_to_intent = {v: k for k, v in self.intent_to_id.items()}
            if not self.intent_to_id:
                return

            config = BertConfig.from_pretrained(str(self.model_dir))
            self.tokenizer = BertTokenizer.from_pretrained(str(self.model_dir))
            model = _IntentModelAdapter(config=config, num_labels=len(self.intent_to_id))

            state_dict = self._read_state_dict(self.model_dir)
            if not state_dict:
                return

            translated: dict[str, torch.Tensor] = {}
            for key, value in state_dict.items():
                if key.startswith("bert."):
                    translated[key] = value
                    continue
                if key.startswith("intent_classifier."):
                    translated[key.replace("intent_classifier", "classifier")] = value
                    continue
                if key.startswith("classifier."):
                    translated[key] = value

            model.load_state_dict(translated, strict=False)
            model.to(self.device)
            model.eval()
            self.model = model
        except Exception:
            self.model = None
            self.tokenizer = None

    @staticmethod
    def _read_state_dict(model_dir: Path) -> dict[str, torch.Tensor]:
        safetensors_path = model_dir / "model.safetensors"
        if safetensors_path.exists():
            try:
                from safetensors.torch import load_file

                return load_file(str(safetensors_path), device="cpu")
            except Exception:
                pass

        pt_path = model_dir / "pytorch_model.bin"
        if pt_path.exists():
            try:
                payload = torch.load(str(pt_path), map_location="cpu")
                if isinstance(payload, dict):
                    return payload
            except Exception:
                pass

        return {}

    @staticmethod
    def _normalize_intent(raw_intent: str) -> str:
        text = str(raw_intent or "").strip()
        low = text.lower()

        if low in {"agri", "agriculture", "disease", "climate", "management", "crop"}:
            return "agri"
        if low in {"non_agri", "non-agri", "nonagri", "other"}:
            return "non_agri"
        if low in {"clarify", "unclear", "unknown", "greeting", "feedback"}:
            return "clarify"
        return "clarify"

    @classmethod
    def _build_packet(
        cls, *, intent: str, confidence: float, keywords: list[str] | None = None
    ) -> dict[str, Any]:
        normalized = cls._normalize_intent(intent)
        value = max(0.0, min(1.0, float(confidence)))
        unique_keywords = list(dict.fromkeys([kw for kw in (keywords or []) if str(kw).strip()]))
        return {
            "intent": normalized,
            "confidence": round(value, 4),
            "keywords": unique_keywords,
        }

    def predict(self, text: str) -> dict[str, Any]:
        query = str(text or "").strip()
        if not query:
            return self._build_packet(intent="clarify", confidence=0.0)

        non_agri_hits = [kw for kw in self.non_agri_keywords if kw and kw in query]
        if non_agri_hits:
            return self._build_packet(intent="non_agri", confidence=0.99, keywords=non_agri_hits)

        agri_hits = [kw for kw in self.agri_keywords if kw and kw in query]

        if self.model is None or self.tokenizer is None or not self.id_to_intent:
            if agri_hits:
                return self._build_packet(intent="agri", confidence=0.6, keywords=agri_hits)
            return self._build_packet(intent="clarify", confidence=0.35)

        try:
            encoded = self.tokenizer(
                query,
                add_special_tokens=True,
                max_length=128,
                padding="max_length",
                truncation=True,
                return_attention_mask=True,
                return_tensors="pt",
            )
            input_ids = encoded["input_ids"].to(self.device)
            attention_mask = encoded["attention_mask"].to(self.device)

            with torch.no_grad():
                logits = self.model(input_ids=input_ids, attention_mask=attention_mask)
                probs = torch.softmax(logits, dim=1)

            confidence_tensor, pred_id = torch.max(probs, dim=1)
            confidence = float(confidence_tensor.item())
            pred_idx = int(pred_id.item())
            raw_intent = self.id_to_intent.get(pred_idx, "clarify")
            intent = self._normalize_intent(raw_intent)

            if agri_hits and intent != "agri":
                intent = "agri"
                confidence = max(confidence, 0.66)

            if confidence < self.threshold and intent != "agri" and not agri_hits:
                intent = "clarify"

            keywords = agri_hits if intent == "agri" else []
            return self._build_packet(intent=intent, confidence=confidence, keywords=keywords)
        except Exception:
            if agri_hits:
                return self._build_packet(intent="agri", confidence=0.55, keywords=agri_hits)
            return self._build_packet(intent="clarify", confidence=0.0)

    def classify(self, text: str) -> dict[str, Any]:
        return self.predict(text)
