from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Callable


# 测试结果结构：统一输出接口名、状态码、是否通过和简要信息。
@dataclass
class TestResult:
    name: str
    ok: bool
    status: int
    detail: str


# HTTP JSON 请求工具：兼容正常返回与错误返回，避免脚本中断。
def _request_json(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 60,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    body = None
    final_headers = {"Accept": "application/json"}
    if headers:
        final_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        final_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=body, method=method.upper(), headers=final_headers)
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


# Multipart 上传工具：用于测试知识库上传接口。
def _post_multipart_file(
    *,
    url: str,
    field_name: str,
    file_name: str,
    content: bytes,
    timeout: int = 60,
) -> tuple[int, Any]:
    boundary = f"----CodexBoundary{uuid.uuid4().hex}"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{file_name}"\r\n'
        "Content-Type: text/plain\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = head + content + tail

    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
    )
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


# SSE 工具：读取流式接口，直到 done 或 [DONE]。
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


def _chat_payload() -> dict[str, Any]:
    return {
        "query": "水稻纹枯病怎么防治",
        "user_id": "frontend_test_user",
        "session_id": f"sess_frontend_{int(time.time())}",
        "location": "湖南",
        "rag": True,
    }


# 各接口测试函数
def test_health(base_url: str, timeout: int, rebuild_index: bool) -> TestResult:
    _ = rebuild_index
    status, data = _request_json(method="GET", url=f"{base_url}/api/health", timeout=timeout)
    return TestResult(
        name="GET /api/health",
        ok=_ok(status) and data.get("status") == "ok",
        status=status,
        detail=str(data),
    )


def test_chat(base_url: str, timeout: int, rebuild_index: bool) -> TestResult:
    _ = rebuild_index
    status, data = _request_json(
        method="POST",
        url=f"{base_url}/api/chat",
        payload=_chat_payload(),
        timeout=timeout,
    )
    return TestResult(
        name="POST /api/chat",
        ok=_ok(status) and isinstance(data, dict) and "answer" in data,
        status=status,
        detail=f"keys={list(data.keys()) if isinstance(data, dict) else 'n/a'}",
    )


def test_chat_stream(base_url: str, timeout: int, rebuild_index: bool) -> TestResult:
    _ = rebuild_index
    status, events, saw_done = _post_sse(
        url=f"{base_url}/api/chat/stream",
        payload=_chat_payload(),
        timeout=max(timeout, 120),
    )
    return TestResult(
        name="POST /api/chat/stream",
        ok=_ok(status) and saw_done,
        status=status,
        detail=f"events={len(events)}, saw_done={saw_done}",
    )


def test_knowledge_upload(base_url: str, timeout: int, rebuild_index: bool) -> TestResult:
    _ = rebuild_index
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as f:
        f.write("测试知识文件：马铃薯晚疫病可通过轮作和药剂预防。")
        temp_path = f.name
    try:
        with open(temp_path, "rb") as f:
            status, data = _post_multipart_file(
                url=f"{base_url}/api/knowledge/upload",
                field_name="file",
                file_name=os.path.basename(temp_path),
                content=f.read(),
                timeout=timeout,
            )
        return TestResult(
            name="POST /api/knowledge/upload",
            ok=_ok(status) and isinstance(data, dict) and "stored_as" in data,
            status=status,
            detail=str(data),
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_index_update(base_url: str, timeout: int, rebuild_index: bool) -> TestResult:
    status, data = _request_json(
        method="POST",
        url=f"{base_url}/api/knowledge/index/update",
        payload={"rebuild": bool(rebuild_index)},
        timeout=max(timeout, 180),
    )
    return TestResult(
        name="POST /api/knowledge/index/update",
        ok=_ok(status) and isinstance(data, dict) and "indexed_count" in data,
        status=status,
        detail=str(data),
    )


def test_index_status(base_url: str, timeout: int, rebuild_index: bool) -> TestResult:
    _ = rebuild_index
    status, data = _request_json(
        method="GET",
        url=f"{base_url}/api/knowledge/index/status",
        timeout=timeout,
    )
    return TestResult(
        name="GET /api/knowledge/index/status",
        ok=_ok(status) and isinstance(data, dict) and "ready" in data,
        status=status,
        detail=str(data),
    )


def _print_menu(cases: dict[str, tuple[str, Callable[[str, int, bool], TestResult]]]) -> None:
    print("\n可选测试项：")
    print("  A. 全部执行")
    for key, (name, _) in cases.items():
        print(f"  {key}. {name}")
    print("  Q. 退出")
    print("输入示例：A 或 1 或 1,3,5")


def _parse_selection(
    raw: str,
    cases: dict[str, tuple[str, Callable[[str, int, bool], TestResult]]],
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


def _run_selected(
    *,
    base_url: str,
    timeout: int,
    rebuild_index: bool,
    selected_keys: list[str],
    cases: dict[str, tuple[str, Callable[[str, int, bool], TestResult]]],
) -> list[TestResult]:
    results: list[TestResult] = []
    for key in selected_keys:
        name, fn = cases[key]
        print(f"\n执行 -> {key}. {name}")
        result = fn(base_url, timeout, rebuild_index)
        mark = "PASS" if result.ok else "FAIL"
        print(f"[{mark}] {result.name}  status={result.status}  detail={result.detail}")
        results.append(result)
    return results


def main() -> None:
    print("=== 前端接口交互测试 ===")
    base_url = input("输入服务地址（默认 http://127.0.0.1:8000）: ").strip() or "http://127.0.0.1:8000"
    timeout_raw = input("输入请求超时秒数（默认 60）: ").strip() or "60"
    rebuild_raw = input("索引更新是否 rebuild=true（默认 false）[y/N]: ").strip().lower()

    try:
        timeout = max(10, int(timeout_raw))
    except ValueError:
        timeout = 60
    rebuild_index = rebuild_raw in {"y", "yes", "1", "true"}

    cases: dict[str, tuple[str, Callable[[str, int, bool], TestResult]]] = {
        "1": ("GET /api/health", test_health),
        "2": ("POST /api/chat", test_chat),
        "3": ("POST /api/chat/stream", test_chat_stream),
        "4": ("POST /api/knowledge/upload", test_knowledge_upload),
        "5": ("POST /api/knowledge/index/update", test_index_update),
        "6": ("GET /api/knowledge/index/status", test_index_status),
    }

    while True:
        _print_menu(cases)
        raw = input("\n请选择要执行的测试项: ")
        selected = _parse_selection(raw, cases)
        if not selected:
            print("输入无效，请重新选择。")
            continue
        if selected == ["Q"]:
            print("已退出。")
            break

        results = _run_selected(
            base_url=base_url,
            timeout=timeout,
            rebuild_index=rebuild_index,
            selected_keys=selected,
            cases=cases,
        )
        ok_count = sum(1 for item in results if item.ok)
        print(f"\n本轮完成：{ok_count}/{len(results)} 通过。")


if __name__ == "__main__":
    main()
