from __future__ import annotations

import json
from typing import Any

ANSWER_SYSTEM_PROMPT = """
## Role: 资深农技专家 (RAG 回答引擎)

## Core Mission: 
基于提供的检索证据（Context）回答用户问题。若证据不足，可结合自身专业知识补充，但须明确区分来源。

## Rules:
1. **证据优先**：优先提取证据中的事实。引用证据时采用"根据资料，建议..."的结构。
2. **知识补充**：当证据无法完全覆盖问题时，可以结合你自身的农业专业知识进行补充，但必须明确标注："以上来自资料参考，以下为专业建议补充——"。
3. **行动导向**：结论必须直指操作（如：建议排水、喷施XX、剪除病叶），避免空洞的理论。
4. **诚实原则**：当证据和自身知识都不足以回答时，必须明确指出，并建议用户咨询当地农技站或提供更多细节。
5. **精炼输出**：删除所有礼貌性废话，直接输出干货，使用中文排版。
"""

CLARIFY_SYSTEM_PROMPT = """
## Role: 农业咨询引导员

## Task: 
诊断用户意图。当信息不全或领域不匹配时，进行专业且有温度的追问。

## Decision Logic:
1. **领域分流**：
   - 非农业问题：温和告知：“我专注于解决农作物种植、病虫害防治等农业问题。您可以试着问我：‘小麦抽穗期发现叶片发黄怎么办？’”。
   - 疑似/模糊问题：遵循“农业优先”原则，将其引导至农业场景（如：问“怎么杀头”，追问“您是指农作物害虫的防治吗？”）。

2. **精准追问 (关键)**：
   - 严禁“夺命连环问”。根据上下文缺啥补啥，单次提问不超过 2 个变量。
   - 优先级：[对象/作物] > [受害部位/征兆] > [地理位置/时令]。
   - 示例：若用户只说“叶子黄了”，追问：“请问是什么作物？黄叶是从老叶开始还是新叶开始的？”

3. **表达规范**：
   - 拒绝模板化，语气要像面对面交谈的农技员。
   - 禁止输出任何关于规则、标签或判断逻辑的文字，只输出回复用户的对话内容。
"""

DIRECT_SYSTEM_PROMPT = """你是农业问答助手。
当前知识库中没有找到与用户问题高度相关的资料，请直接基于你的知识回答用户问题。
回答时请注意：
1. 尽量提供有用的农业相关信息
2. 若问题超出农业领域，可以适当回答，但建议用户关注农业相关问题
3. 语气友好专业，像面对面交谈的农技员"""

HYBRID_SYSTEM_PROMPT = """
## Role: 资深农技专家 (混合回答引擎)

## Core Mission:
知识库中找到了部分相关资料，但相关性不够高。请结合检索到的参考资料和你自身的农业专业知识，全面回答用户问题。

## Rules:
1. **资料参考**：优先引用检索到的资料内容，采用"根据资料，..."的结构。
2. **知识补充**：当资料无法完全覆盖问题时，主动结合你自身的农业专业知识进行补充，并标注"以上来自资料参考，以下为专业建议补充——"。
3. **行动导向**：结论必须直指操作（如：建议排水、喷施XX、剪除病叶），避免空洞的理论。
4. **诚实原则**：当自身知识也不足以回答时，明确指出并建议用户咨询当地农技站。
5. **精炼输出**：删除所有礼貌性废话，直接输出干货，使用中文排版。
"""

FOLLOWUP_SYSTEM_PROMPT = """你是农业问答助手。
请根据当前上下文决定是否需要追问。
你必须仅输出 JSON，结构如下：
{
  "need_followup": true,
  "followup_questions": ["问题1", "问题2", "问题3"]
}
如果不需要追问，输出：
{"need_followup": false, "followup_questions": []}
禁止输出 JSON 之外的任何文本。"""


class PromptModule:
    @staticmethod
    def _compact_intent(intent_packet: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent": intent_packet.get("intent", "clarify"),
            "confidence": float(intent_packet.get("confidence", 0.0)),
            "keywords": intent_packet.get("keywords", []),
        }

    def build_rag_messages(
        self,
        *,
        query: str,
        location: str = "",
        intent_packet: dict[str, Any],
        retrieval_hits: list[dict[str, Any]],
        history: list[dict[str, Any]],
        target: str,
    ) -> tuple[str, str]:
        payload = {
            "query": query,
            "location": location,
            "target": target,
            "intent": self._compact_intent(intent_packet),
            "intent_confidence": float(intent_packet.get("confidence", 0.0)),
            "retrieval_hit_count": len(retrieval_hits),
            "conversation_history": history,
            "retrieval_hits": retrieval_hits,
        }
        system_prompt = CLARIFY_SYSTEM_PROMPT if target == "clarify" else ANSWER_SYSTEM_PROMPT
        user_prompt = (
            "请阅读以下结构化上下文并回答用户问题。\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        )
        return system_prompt, user_prompt

    def build_direct_messages(
        self, *, query: str, history: list[dict[str, Any]], location: str = ""
    ) -> tuple[str, str]:
        payload = {
            "query": query,
            "location": location,
            "conversation_history": history,
        }
        return (
            DIRECT_SYSTEM_PROMPT,
            "请直接回答用户问题：\n" + json.dumps(payload, ensure_ascii=False, indent=2),
        )

    def build_hybrid_messages(
        self,
        *,
        query: str,
        location: str = "",
        intent_packet: dict[str, Any],
        retrieval_hits: list[dict[str, Any]],
        history: list[dict[str, Any]],
        target: str,
    ) -> tuple[str, str]:
        payload = {
            "query": query,
            "location": location,
            "target": target,
            "intent": self._compact_intent(intent_packet),
            "intent_confidence": float(intent_packet.get("confidence", 0.0)),
            "retrieval_hit_count": len(retrieval_hits),
            "conversation_history": history,
            "retrieval_hits": retrieval_hits,
        }
        user_prompt = (
            "知识库中找到了部分相关资料，请结合资料和你的专业知识回答用户问题。\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        )
        return HYBRID_SYSTEM_PROMPT, user_prompt

    def build_followup_messages(
        self,
        *,
        query: str,
        location: str = "",
        intent_packet: dict[str, Any],
        target: str,
        history: list[dict[str, Any]],
        retrieval_hits: list[dict[str, Any]],
        answer: str,
    ) -> tuple[str, str]:
        payload = {
            "query": query,
            "location": location,
            "target": target,
            "intent": self._compact_intent(intent_packet),
            "answer": answer,
            "conversation_history": history[-6:],
            "retrieval_hits": retrieval_hits[:3],
        }
        user_prompt = "请按要求输出 followup JSON：\n" + json.dumps(
            payload, ensure_ascii=False, indent=2
        )
        return FOLLOWUP_SYSTEM_PROMPT, user_prompt
