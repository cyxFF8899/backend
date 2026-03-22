# Agri Backend

农业问答后端（FastAPI + SQLite + LangChain/Chroma）。

当前主链路能力：`RAG 对话 + 上下文记忆（窗口 5）+ 三分类意图路由（agri/non_agri/clarify）`。

## 核心能力

- 农业 RAG 对话（Chroma 向量检索）
- 会话上下文记忆（SQLite，按 `session_id` 持久化）
- 意图硬路由
  - `agri` -> `agri_expert`
  - `non_agri` -> `handoff`
  - `clarify` -> `clarify`
- 知识库管理接口
  - 上传原始知识文件
  - 更新/重建索引
  - 查询索引状态
- 独立 Graph 模块（与 RAG 分离）
  - 基于 Neo4j，提供节点/关系创建、按 ID 查询、关系查询、关键词搜索
  - 未并入主聊天链路（当前仅独立 API 调用）

## 快速启动（Windows + uv）

在 `backend` 目录执行：

```powershell
uv venv --python 3.10 .venv
.\.venv\Scripts\activate
uv pip install -r .\requirements.txt
Copy-Item .\.env.example .\.env
uv run .\scripts\build_index.py --rebuild
uv run .\main.py
```

服务地址：`http://127.0.0.1:8000`

## API 总览

### 前端接口

- `GET /api/health`
- `POST /api/chat`
- `POST /api/chat/stream`（SSE）
- `POST /api/knowledge/upload`
- `POST /api/knowledge/index/update`
- `GET /api/knowledge/index/status`

### Debug 接口

- `POST /api/debug/intent`
- `POST /api/debug/retrieval`
- `POST /api/debug/graph`
- `POST /api/debug/router`
- `POST /api/debug/prompt/rag`
- `POST /api/debug/prompt/direct`
- `POST /api/debug/llm`
- `POST /api/debug/llm/stream`（SSE）

### Graph 接口（Neo4j）

- `POST /api/graph/node`
- `POST /api/graph/relationship`
- `GET /api/graph/node/{node_id}`
- `GET /api/graph/node/{node_id}/relationships`
- `GET /api/graph/search?query=xxx&limit=10`

## Postman 调用示例（图数据库）

Base URL：`http://127.0.0.1:8000`

1. 新增节点

- Method: `POST`
- URL: `/api/graph/node`
- Body:

```json
{
  "label": "Crop",
  "properties": {
    "id": "crop_maize_001",
    "name": "玉米",
    "description": "常见粮食作物"
  }
}
```

2. 新增关系

- Method: `POST`
- URL: `/api/graph/relationship`
- Body:

```json
{
  "start_id": "crop_maize_001",
  "end_id": "disease_001",
  "relationship_type": "HAS_DISEASE",
  "properties": {
    "source": "manual",
    "level": "high"
  }
}
```

3. 查询节点

- Method: `GET`
- URL: `/api/graph/node/crop_maize_001`

4. 查询节点关系

- Method: `GET`
- URL: `/api/graph/node/crop_maize_001/relationships`

5. 关键词搜索

- Method: `GET`
- URL: `/api/graph/search?query=玉米&limit=10`

注意：`/api/graph/relationship` 与按 ID 查询都依赖节点属性 `properties.id`，创建节点时请务必提供唯一 `id`。

## 常用环境变量

见 `backend/.env.example`。

- LLM：`DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、`DASHSCOPE_MODEL`
- RAG：`EMBEDDING_MODEL_NAME`、`EMBEDDING_HF_ENDPOINT`、`CHROMA_PERSIST_DIR`、`INDEX_DATA_DIR`、`INDEX_AUTO_BUILD`
- 切块与批处理：
  - `RAG_CHUNK_SIZE`（默认 380）
  - `RAG_CHUNK_OVERLAP`（默认 60）
  - `CHROMA_ADD_BATCH_SIZE`（默认 128）
- 检索命中数：
  - `TOP_K_HITS`（默认 3）
- 上下文：
  - `CONTEXT_WINDOW_TURNS`（默认 5）
- 意图：
  - `INTENT_MODEL_DIR`、`INTENT_MAPPING_PATH`、`INTENT_CONFIDENCE_THRESHOLD`
- 图数据库：
  - `NEO4J_URI`、`NEO4J_USERNAME`、`NEO4J_PASSWORD`

## 测试脚本

测试脚本位于 `backend/tests`：

- `backend/tests/frontend_test.py`：前端接口联调
- `backend/tests/debug_test.py`：debug 接口联调

运行：

```powershell
python .\tests\frontend_test.py
python .\tests\debug_test.py
```

## 说明

- 向量库仅存知识语料，不存会话记忆。
- 会话记忆只走 SQLite。
- Graph 模块与 RAG 完全分离，当前已接入 Neo4j。
