from __future__ import annotations


class RouterModule:
    def __init__(self) -> None:
        self.agri_intents = {"agri", "病虫害", "气候", "种植管理", "农产品管理"}

    def derive_target(self, *, intent: str) -> str:
        label = str(intent or "").strip().lower()
        if label == "non_agri":
            return "handoff"
        if label == "agri":
            return "agri_expert"
        if label in self.agri_intents:
            return "agri_expert"
        return "clarify"
