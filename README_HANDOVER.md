# 交接说明（Agri Backend）

本文档用于项目交付给下一位开发者，重点说明当前状态、目录结构、风险点和后续建议。

## 1. 当前交付状态

### 已完成

- 主链路可用：`intent -> route -> retrieval -> prompt -> llm -> persist`
- 意图识别为三分类：`agri / non_agri / clarify`
- 上下文记忆：SQLite，默认窗口 5 轮
- 向量检索：Chroma，支持自动构建和手动重建
- 知识库管理接口：上传原始文件、更新索引、查询状态
- `location` 已进入检索与提示词上下文
- 默认检索条数 `TOP_K_HITS=3`
- 已去除 KG 注入，新增独立 Graph 模块（与 RAG 分离）

### 未完成 / 暂未纳入主链路

- Graph 查询仍是占位实现，尚未正式接入 Neo4j
- Graph 未并入聊天主流程（仅保留 debug 调试入口）
- 自动化回归测试（pytest）未系统化，当前以交互脚本联调为主

## 2. 关键目录

```txt
backend/
  app/
    api.py                     # HTTP 接口入口
    config.py                  # 配置与环境变量
    db.py                      # SQLite
    modules/
      agri_qa/chat.py          # 主编排
      intent/module.py         # 意图三分类
      retrieval/module.py      # 检索模块（RAG）
      graph/module.py          # 图模块（独立，占位）
    rag/
      index_service.py         # 索引构建（切块、批处理）
      retriever.py             # 向量检索
      loaders.py               # 原始数据加载
  data/raw/                    # 原始知识库目录
  tests/
    frontend_test.py           # 前端接口联调
    debug_test.py              # debug 接口联调
```

## 3. 运行步骤

在 `backend` 目录执行：

```powershell
uv venv --python 3.10 .venv
.\.venv\Scripts\activate
uv pip install -r .\requirements.txt
Copy-Item .\.env.example .\.env
uv run .\scripts\build_index.py --rebuild
uv run .\main.py
```

## 4. 关键配置

- RAG：
  - `RAG_CHUNK_SIZE=380`
  - `RAG_CHUNK_OVERLAP=60`
  - `CHROMA_ADD_BATCH_SIZE=128`
  - `TOP_K_HITS=3`
- 会话：
  - `CONTEXT_WINDOW_TURNS=5`
- 意图：
  - `INTENT_MODEL_DIR`
  - `INTENT_MAPPING_PATH`
  - `INTENT_CONFIDENCE_THRESHOLD`

## 5. 接口清单

### 面向前端

- `GET /api/health`
- `POST /api/chat`
- `POST /api/chat/stream`
- `POST /api/knowledge/upload`
- `POST /api/knowledge/index/update`
- `GET /api/knowledge/index/status`

### Debug

- `POST /api/debug/intent`
- `POST /api/debug/retrieval`
- `POST /api/debug/graph`
- `POST /api/debug/router`
- `POST /api/debug/prompt/rag`
- `POST /api/debug/prompt/direct`
- `POST /api/debug/llm`
- `POST /api/debug/llm/stream`

## 6. 风险与注意事项

- `debug/llm*` 与主聊天接口依赖可用的 LLM API Key。
- 首次建索引或重建索引耗时较长，避免在高峰时执行。
- Graph 模块当前为占位，调用 `debug/graph` 预期可用但结果可能为空。
- 若终端出现中文乱码，优先确认编辑器按 UTF-8 打开文件。

## 7. 后续建议

1. 将 `graph/module.py` 接入 Neo4j 驱动，并补 `search/neighbors/subgraph` 接口。
2. 增加鉴权与权限控制（登录注册后，限制知识库更新接口）。
3. 增加 pytest 回归：路由、SSE、知识库接口、索引构建与 location 检索行为。
