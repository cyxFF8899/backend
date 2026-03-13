from __future__ import annotations


class RouterModule:
    def __init__(self) -> None:
        self.agri_intents = {"病虫害", "气候", "种植管理", "农产品管理"}
        self.non_agri_intents = {"娱乐", "编程"}

    def derive_target(self, *, intent: str, domain: str = "unclear") -> str:
        if domain == "agri":
            return "agri_expert"
        if domain == "non_agri":
            return "handoff"
        if intent in self.agri_intents:
            return "agri_expert"
        if intent in self.non_agri_intents:
            return "handoff"
        return "clarify"
