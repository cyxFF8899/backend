# Mock Data Guide

## Files

- `mock_payloads.py`: 推荐使用。Python 结构，便于手动注释、删减、组合。
- `chat_requests.json`: 常用聊天请求样例。
- `debug_requests.json`: `/api/debug/*` 的请求样例合集。

## Quick import

```python
from backend.tests.mocks.mock_payloads import (
    CHAT_CASES,
    INTENT_DEBUG_CASES,
    RETRIEVAL_DEBUG_CASES,
    KG_DEBUG_CASES,
    ROUTER_DEBUG_CASES,
    PROMPT_RAG_DEBUG_CASES,
    PROMPT_DIRECT_DEBUG_CASES,
    LLM_DEBUG_CASES,
)
```

## Tip

如果你想“临时屏蔽”某条数据，优先在 `mock_payloads.py` 里直接注释该条字典。

