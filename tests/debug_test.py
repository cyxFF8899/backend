from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


# 统一测试结果结构，便于终端展示与统计。
@dataclass
class TestResult:
    name: str
    ok: bool
    status: int
    detail: str


# JSON 请求工具：覆盖成功与失败响应，避免单测失败后脚本中断。
def _request_json(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 60,
) -> tuple[int, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=body, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return int(resp.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="ignore")
        try:
            return int(exc.code), json.loads(text)
        except Exception:
            return int(exc.code), {"error": text}


# SSE 请求工具：用于 debug/llm/stream 接口。
def _post_sse(
    *,
    url: str,
    payload: dict[str, Any],
    timeout: int = 120,
    max_events: int = 30,
) -> tuple[int, list[dict[str, Any]], bool]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    events: list[dict[str, Any]] = []
    saw_done = False
    status = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(resp.status)
            for raw in resp:
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_text = line[5:].strip()
                if data_text == "[DONE]":
                    saw_done = True
                    break
                try:
                    packet = json.loads(data_text)
                    events.append(packet)
                    if packet.get("type") == "done":
                        saw_done = True
                        break
                except Exception:
                    continue
                if len(events) >= max_events:
                    break
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        text = exc.read().decode("utf-8", errors="ignore")
        events.append({"error": text})
    except Exception as exc:
        events.append({"error": str(exc)})
    return status, events, saw_done


def _ok(status: int) -> bool:
    return 200 <= status < 300


def test_debug_intent(base_url: str, timeout: int) -> TestResult:
    status, data = _request_json(
        method="POST",
        url=f"{base_url}/api/debug/intent",
        payload={"query": "水稻纹枯病怎么防治"},
        timeout=timeout,
    )
    return TestResult(
        name="POST /api/debug/intent",
        ok=_ok(status) and isinstance(data, dict) and "intent_packet" in data,
        status=status,
        detail=str(data),
    )


def test_debug_retrieval(base_url: str, timeout: int) -> TestResult:
    status, data = _request_json(
        method="POST",
        url=f"{base_url}/api/debug/retrieval",
        payload={"query": "马铃薯晚疫病防治", "user_id": "debug_user", "location": "云南"},
        timeout=timeout,
    )
    return TestResult(
        name="POST /api/debug/retrieval",
        ok=_ok(status) and isinstance(data, dict) and "hits" in data and "count" in data,
        status=status,
        detail=f"count={data.get('count') if isinstance(data, dict) else 'n/a'}",
    )


def test_debug_graph(base_url: str, timeout: int) -> TestResult:
    status, data = _request_json(
        method="POST",
        url=f"{base_url}/api/debug/graph",
        payload={"query": "马铃薯", "limit": 10},
        timeout=timeout,
    )
    return TestResult(
        name="POST /api/debug/graph",
        ok=_ok(status) and isinstance(data, dict) and "hits" in data and "count" in data,
        status=status,
        detail=f"count={data.get('count') if isinstance(data, dict) else 'n/a'}",
    )


def test_debug_router(base_url: str, timeout: int) -> TestResult:
    status, data = _request_json(
        method="POST",
        url=f"{base_url}/api/debug/router",
        payload={"intent": "agri"},
        timeout=timeout,
    )
    return TestResult(
        name="POST /api/debug/router",
        ok=_ok(status) and isinstance(data, dict) and "target" in data,
        status=status,
        detail=str(data),
    )


def test_debug_prompt_rag(base_url: str, timeout: int) -> TestResult:
    payload = {
        "query": "马铃薯晚疫病如何预防",
        "location": "云南",
        "intent_packet": {
            "intent": "agri",
            "confidence": 0.88,
            "keywords": ["马铃薯", "晚疫病"],
        },
        "retrieval_hits": [
            {"content": "轮作可降低病害压力。", "source": "test_source", "score": 0.8}
        ],
        "history": [{"role": "user", "content": "最近雨水很多"}],
        "target": "agri_expert",
    }
    status, data = _request_json(
        method="POST",
        url=f"{base_url}/api/debug/prompt/rag",
        payload=payload,
        timeout=timeout,
    )
    return TestResult(
        name="POST /api/debug/prompt/rag",
        ok=_ok(status) and isinstance(data, dict) and "system_prompt" in data and "user_prompt" in data,
        status=status,
        detail=f"keys={list(data.keys()) if isinstance(data, dict) else 'n/a'}",
    )


def test_debug_prompt_direct(base_url: str, timeout: int) -> TestResult:
    payload = {
        "query": "给我一个马铃薯种植管理清单",
        "location": "云南",
        "history": [{"role": "user", "content": "我是云南地区"}],
    }
    status, data = _request_json(
        method="POST",
        url=f"{base_url}/api/debug/prompt/direct",
        payload=payload,
        timeout=timeout,
    )
    return TestResult(
        name="POST /api/debug/prompt/direct",
        ok=_ok(status) and isinstance(data, dict) and "system_prompt" in data and "user_prompt" in data,
        status=status,
        detail=f"keys={list(data.keys()) if isinstance(data, dict) else 'n/a'}",
    )


def test_debug_llm(base_url: str, timeout: int) -> TestResult:
    payload = {
        "system_prompt": "你是农业助手，请简洁回答。",
        "user_prompt": "马铃薯块茎膨大期施肥要点是什么？",
    }
    status, data = _request_json(
        method="POST",
        url=f"{base_url}/api/debug/llm",
        payload=payload,
        timeout=max(timeout, 120),
    )
    return TestResult(
        name="POST /api/debug/llm",
        ok=_ok(status) and isinstance(data, dict) and "answer" in data,
        status=status,
        detail=f"keys={list(data.keys()) if isinstance(data, dict) else 'n/a'}",
    )


def test_debug_llm_stream(base_url: str, timeout: int) -> TestResult:
    payload = {
        "system_prompt": "你是农业助手，请简洁回答。",
        "user_prompt": "马铃薯田间常见病害有哪些？",
    }
    status, events, saw_done = _post_sse(
        url=f"{base_url}/api/debug/llm/stream",
        payload=payload,
        timeout=max(timeout, 120),
    )
    return TestResult(
        name="POST /api/debug/llm/stream",
        ok=_ok(status) and saw_done,
        status=status,
        detail=f"events={len(events)}, saw_done={saw_done}",
    )


def _print_menu(cases: dict[str, tuple[str, Callable[[str, int], TestResult]]]) -> None:
    print("\n可选测试项：")
    print("  A. 全部执行")
    for key, (name, _) in cases.items():
        print(f"  {key}. {name}")
    print("  Q. 退出")
    print("输入示例：A 或 1 或 1,3,8")


def _parse_selection(
    raw: str,
    cases: dict[str, tuple[str, Callable[[str, int], TestResult]]],
) -> list[str]:
    text = raw.strip().upper()
    if not text:
        return []
    if text == "A":
        return list(cases.keys())
    if text == "Q":
        return ["Q"]
    picked: list[str] = []
    for token in text.split(","):
        key = token.strip()
        if key in cases and key not in picked:
            picked.append(key)
    return picked


def main() -> None:
    print("=== Debug 接口交互测试 ===")
    base_url = (
        input("输入服务地址（默认 http://127.0.0.1:8000）：").strip()
        or "http://127.0.0.1:8000"
    )
    timeout_raw = input("输入请求超时秒数（默认 60）：").strip() or "60"
    try:
        timeout = max(10, int(timeout_raw))
    except ValueError:
        timeout = 60

    cases: dict[str, tuple[str, Callable[[str, int], TestResult]]] = {
        "1": ("POST /api/debug/intent", test_debug_intent),
        "2": ("POST /api/debug/retrieval", test_debug_retrieval),
        "3": ("POST /api/debug/graph", test_debug_graph),
        "4": ("POST /api/debug/router", test_debug_router),
        "5": ("POST /api/debug/prompt/rag", test_debug_prompt_rag),
        "6": ("POST /api/debug/prompt/direct", test_debug_prompt_direct),
        "7": ("POST /api/debug/llm", test_debug_llm),
        "8": ("POST /api/debug/llm/stream", test_debug_llm_stream),
    }

    while True:
        _print_menu(cases)
        raw = input("\n请选择要执行的测试项：")
        selected = _parse_selection(raw, cases)
        if not selected:
            print("输入无效，请重新选择。")
            continue
        if selected == ["Q"]:
            print("已退出。")
            break

        results: list[TestResult] = []
        for key in selected:
            name, fn = cases[key]
            print(f"\n执行 -> {key}. {name}")
            result = fn(base_url, timeout)
            mark = "PASS" if result.ok else "FAIL"
            print(f"[{mark}] {result.name}  status={result.status}  detail={result.detail}")
            results.append(result)

        ok_count = sum(1 for item in results if item.ok)
        print(f"\n本轮完成：{ok_count}/{len(results)} 通过。")


if __name__ == "__main__":
    main()
