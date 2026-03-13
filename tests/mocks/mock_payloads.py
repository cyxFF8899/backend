"""
Centralized mock payloads for API and module-level testing.

Usage example:
    from backend.tests.mocks.mock_payloads import CHAT_CASES
"""

# -----------------------------
# /api/chat and /api/chat/stream
# -----------------------------
CHAT_CASES = [
    {
        "name": "chat_rag_true_disease",
        "request": {
            "query": "水稻纹枯病怎么防治？",
            "user_id": "u001",
            "session_id": "sess_u001_001",
            "location": "湖南",
            "rag": True,
        },
    },
    {
        "name": "chat_rag_true_climate",
        "request": {
            "query": "最近连续阴雨，玉米倒伏风险怎么判断？",
            "user_id": "u002",
            "session_id": "sess_u002_001",
            "location": "河南",
            "rag": True,
        },
    },
    {
        "name": "chat_rag_true_management",
        "request": {
            "query": "桃树多久浇一次水比较合适？",
            "user_id": "u003",
            "session_id": "sess_u003_001",
            "location": "山东",
            "rag": True,
        },
    },
    {
        "name": "chat_rag_true_product_management",
        "request": {
            "query": "苹果采收后冷链运输的温度建议是多少？",
            "user_id": "u004",
            "session_id": "sess_u004_001",
            "location": "陕西",
            "rag": True,
        },
    },
    {
        "name": "chat_rag_false_direct_llm",
        "request": {
            "query": "请给我一个春季果园管理的通用清单",
            "user_id": "u005",
            "session_id": "sess_u005_001",
            "location": "",
            "rag": False,
        },
    },
    {
        "name": "chat_missing_session_auto_generate",
        "request": {
            "query": "大棚番茄灌溉频率怎么安排？",
            "user_id": "u006",
            "session_id": "",
            "location": "河北",
            "rag": True,
        },
    },
    {
        "name": "chat_non_agri_query",
        "request": {
            "query": "帮我写一段旅行攻略",
            "user_id": "u007",
            "session_id": "sess_u007_001",
            "location": "",
            "rag": True,
        },
    },
    {
        "name": "chat_long_query_stress",
        "request": {
            "query": (
                "我在江苏盐城种了水稻，最近先是低温后又升温，田里积水偏多，"
                "叶片有黄化和少量褐斑，想知道是否与根系缺氧或病害有关，"
                "同时希望给一个7天内可执行的管理建议。"
            ),
            "user_id": "u008",
            "session_id": "sess_u008_001",
            "location": "江苏",
            "rag": True,
        },
    },
]

# -----------------------------
# /api/debug/intent
# -----------------------------
INTENT_DEBUG_CASES = [
    {"query": "梨树开花期遇到倒春寒怎么办？"},
    {"query": "连续高温会影响番茄坐果吗？"},
    {"query": "香蕉采后保鲜和预冷流程怎么做？"},
    {"query": "请推荐一个学习 Python 的入门路线"},
    {"query": "葡萄叶片出现白粉状斑点，是否白粉病？"},
]

# -----------------------------
# /api/debug/retrieval
# -----------------------------
RETRIEVAL_DEBUG_CASES = [
    {"query": "水稻纹枯病防治", "user_id": "u101", "location": "湖南"},
    {"query": "桃树灌溉周期", "user_id": "u102", "location": "山东"},
    {"query": "苹果冷链贮藏温度", "user_id": "u103", "location": "陕西"},
    {"query": "不太可能命中的关键词_abcdefg", "user_id": "u104", "location": ""},
]

# -----------------------------
# /api/debug/kg
# -----------------------------
KG_DEBUG_CASES = [
    {"query": "玉米倒伏风险", "top_k": 3},
    {"query": "果树修剪", "top_k": 5},
    {"query": "病虫害绿色防控", "top_k": 2},
    {"query": "冷链运输", "top_k": 4},
]

# -----------------------------
# /api/debug/router
# -----------------------------
ROUTER_DEBUG_CASES = [
    {"intent": "病虫害", "domain": "agri"},
    {"intent": "气候", "domain": "agri"},
    {"intent": "种植管理", "domain": "unclear"},
    {"intent": "娱乐", "domain": "non_agri"},
    {"intent": "未知意图", "domain": "unclear"},
]

# -----------------------------
# /api/debug/prompt/rag
# -----------------------------
PROMPT_RAG_DEBUG_CASES = [
    {
        "query": "桃树多久浇一次水？",
        "intent_packet": {
            "intent": "种植管理",
            "domain": "agri",
            "confidence": 0.72,
            "entities": [{"type": "crop", "value": "桃树"}],
            "categories": {"crop": ["桃树"], "management": ["浇水"]},
            "keywords": ["桃树", "浇水", "频率"],
        },
        "retrieval_hits": [
            {
                "content": "桃树生长期灌溉应根据土壤墒情进行，避免大水漫灌。",
                "source": "农业技术手册",
                "score": 0.86,
            },
            {
                "content": "花前和果实膨大期是果树需水关键期。",
                "source": "果树栽培指南",
                "score": 0.83,
            },
        ],
        "kg_hits": [
            {
                "content": "桃树 -> 关键管理 -> 灌溉",
                "source": "knowledge_graph",
                "score": 0.8,
            }
        ],
        "history": [
            {"query": "桃树叶片发黄怎么办？", "answer": "先看土壤湿度和根系情况。"}
        ],
        "target": "agri_expert",
    },
    {
        "query": "这个问题描述还不够完整",
        "intent_packet": {
            "intent": "综合咨询",
            "domain": "unclear",
            "confidence": 0.33,
            "entities": [],
            "categories": {},
            "keywords": [],
        },
        "retrieval_hits": [],
        "kg_hits": [],
        "history": [],
        "target": "clarify",
    },
]

# -----------------------------
# /api/debug/prompt/direct
# -----------------------------
PROMPT_DIRECT_DEBUG_CASES = [
    {
        "query": "给我一个春季小麦田间管理 checklist",
        "history": [],
    },
    {
        "query": "总结一下如何减少果园病虫害发生率",
        "history": [
            {"query": "我主要种苹果", "answer": "了解，后续将以苹果为主给建议。"}
        ],
    },
]

# -----------------------------
# /api/debug/llm and /api/debug/llm/stream
# -----------------------------
LLM_DEBUG_CASES = [
    {
        "system_prompt": "你是农业助手，请简洁回答。",
        "user_prompt": "水稻分蘖期施肥要点是什么？",
    },
    {
        "system_prompt": "你是农业助手，请先说明不确定性。",
        "user_prompt": "未知作物在未知地区如何高产？",
    },
]

# -----------------------------
# Basic response shape checks
# -----------------------------
CHAT_RESPONSE_REQUIRED_KEYS = [
    "answer",
    "citations",
    "need_followup",
    "followup_questions",
    "session_id",
]

CITATION_REQUIRED_KEYS = ["content", "source", "score"]

