from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple


ANSWER_SYSTEM_PROMPT = """你是农业问答助手。
请基于提供的检索与知识图谱证据回答，并遵循：
1. 证据优先，不编造数据或结论；
2. 语言简洁、专业、可执行；
3. 若证据不足，明确指出不确定性并说明还需哪些信息；
4. 只输出中文。"""

CLARIFY_SYSTEM_PROMPT = """你是农业咨询引导员。
用户问题信息不足，请给出简短中文澄清引导，明确需要补充的关键要素（如作物、症状、地区、时间）。"""

DIRECT_SYSTEM_PROMPT = """你是农业问答助手。
当前未启用检索与知识图谱，请直接回答用户问题。
当问题依赖外部事实时，请明确提示：当前回答未使用检索证据。"""

FOLLOWUP_SYSTEM_PROMPT = """你是农业问答助手。
请根据当前问答上下文，生成后续追问建议。
只输出 JSON，对象结构必须严格为：
{
  "need_followup": true,
  "followup_questions": ["问题1", "问题2", "问题3"]
}
约束：
1. followup_questions 最多 3 条；
2. 每条问题都要具体、可回答、与当前主题强相关；
3. 如果当前已足够完整，输出：
{"need_followup": false, "followup_questions": []}
4. 不要输出任何 JSON 之外的文字。"""


class PromptModule:
    @staticmethod
    def _compact_intent(intent_packet: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "intent": intent_packet.get("intent", "咨询"),
            "domain": intent_packet.get("domain", "unclear"),
            "confidence": float(intent_packet.get("confidence", 0.0)),
            "entities": intent_packet.get("entities", []),
            "categories": intent_packet.get("categories", {}),
            "keywords": intent_packet.get("keywords", []),
        }

    def build_rag_messages(
        self,
        *,
        query: str,
        intent_packet: Dict[str, Any],
        retrieval_hits: List[Dict[str, Any]],
        kg_hits: List[Dict[str, Any]],
        history: List[dict],
        target: str,
    ) -> Tuple[str, str]:
        payload = {
            "query": query,
            "target": target,
            "intent_packet": self._compact_intent(intent_packet),
            "retrieval_hits": retrieval_hits,
            "kg_hits": kg_hits,
            "conversation_history": history,
        }
        system_prompt = CLARIFY_SYSTEM_PROMPT if target == "clarify" else ANSWER_SYSTEM_PROMPT
        user_prompt = (
            "请基于以下结构化上下文回答用户问题；若证据不足请明确说明：\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        return system_prompt, user_prompt

    def build_direct_messages(self, *, query: str, history: List[dict]) -> Tuple[str, str]:
        payload = {
            "query": query,
            "conversation_history": history,
        }
        user_prompt = "请直接回答用户问题：\n" + json.dumps(
            payload, ensure_ascii=False, indent=2
        )
        return DIRECT_SYSTEM_PROMPT, user_prompt

    def build_followup_messages(
        self,
        *,
        query: str,
        intent_packet: Dict[str, Any],
        target: str,
        history: List[dict],
        retrieval_hits: List[Dict[str, Any]],
        kg_hits: List[Dict[str, Any]],
        answer: str,
    ) -> Tuple[str, str]:
        payload = {
            "query": query,
            "target": target,
            "intent_packet": self._compact_intent(intent_packet),
            "current_answer": answer,
            "retrieval_hits": retrieval_hits[:3],
            "kg_hits": kg_hits[:2],
            "conversation_history": history[-4:],
        }
        user_prompt = (
            "请根据以下上下文判断是否需要追问，并按要求仅输出 JSON：\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        return FOLLOWUP_SYSTEM_PROMPT, user_prompt
