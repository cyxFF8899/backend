from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

from ...config import Settings


class IntentModule:
    def __init__(self, settings: Settings, project_root: Path) -> None:
        self.settings = settings
        self.project_root = project_root
        self._interpreter: Any | None = None
        self._agri_intents = {"病虫害", "气候", "种植管理", "农产品管理"}
        self._load_interpreter()

    def _load_interpreter(self) -> None:
        try:
            intent_root = self.project_root / "IntentRecognition"
            if str(intent_root) not in sys.path:
                sys.path.append(str(intent_root))
            from semantic import SemanticInterpreter  # type: ignore

            self._interpreter = SemanticInterpreter()
            self._interpreter.weights["disease_pest"] = self.settings.weight_disease_pest
            self._interpreter.weights["climate"] = self.settings.weight_climate
            self._interpreter.weights["management"] = self.settings.weight_management
            self._interpreter.weights["product"] = self.settings.weight_product
            self._interpreter.weights["hint_bonus"] = self.settings.weight_hint_bonus
            self._interpreter.weights["crop_bonus"] = self.settings.weight_crop_bonus
            self._interpreter.fuzzy["enabled"] = self.settings.fuzzy_enabled
            self._interpreter.fuzzy["max_distance"] = self.settings.fuzzy_max_distance
            self._interpreter.fuzzy["max_term_len"] = self.settings.fuzzy_max_term_len
        except Exception:
            self._interpreter = None

    def predict(self, text: str) -> Dict[str, Any]:
        query = str(text or "").strip()
        if not query:
            return self._empty_packet()
        if self._interpreter is None:
            return self._fallback_predict(query)

        try:
            raw = self._interpreter.interpret(query)
            if not isinstance(raw, dict):
                return self._fallback_predict(query)
            intent_obj = raw.get("intent", {})
            label = str(intent_obj.get("label", "综合咨询"))
            confidence = float(intent_obj.get("confidence", 0.0))
            domain = "agri" if label in self._agri_intents else "unclear"
            return {
                "intent": label,
                "confidence": confidence,
                "domain": domain,
                "entities": raw.get("entities", []),
                "categories": raw.get("categories", {}),
                "keywords": raw.get("keywords", []),
            }
        except Exception:
            return self._fallback_predict(query)

    @staticmethod
    def _empty_packet() -> Dict[str, Any]:
        return {
            "intent": "综合咨询",
            "confidence": 0.0,
            "domain": "unclear",
            "entities": [],
            "categories": {},
            "keywords": [],
        }

    def _fallback_predict(self, query: str) -> Dict[str, Any]:
        if any(k in query for k in ["病", "虫", "防治", "农药"]):
            label = "病虫害"
        elif any(k in query for k in ["气温", "降雨", "天气", "干旱"]):
            label = "气候"
        elif any(k in query for k in ["采收", "冷链", "储藏", "加工"]):
            label = "农产品管理"
        else:
            label = "种植管理"
        return {
            "intent": label,
            "confidence": 0.51,
            "domain": "agri" if label in self._agri_intents else "unclear",
            "entities": [],
            "categories": {},
            "keywords": [],
        }
