# Agri Backend

农业问答后端服务
当前版本已经完成模块重构，采用“业务编排 + 可复用大模块”分层：

- 业务编排：`agri_qa`（chat / prompt / llm / router）
- 可复用能力：`intent`、`retrieval`、`kg`



>  各个模块请在各自的模块文件夹和`app/modules`重新优化自己的代码

## 1. 目录结构

```txt
backend/
  app/
    api.py
    config.py
    db.py
    main.py
    schemas.py
    modules/
      __init__.py
      agri_qa/
        __init__.py
        chat.py
        prompt.py
        llm.py
        router.py
      intent/
        __init__.py
        module.py
      retrieval/
        __init__.py
        module.py
      kg/
        __init__.py
        module.py
  data/
  tests/
  .env.example
  main.py
  requirements.txt
  requirements.extracted.txt
  README.md
  接口规范.md
```

## 2. 核心链路

### 2.1 `rag=true`（默认）

1. 意图识别（Intent）
2. 路由决策（Router）
3. 检索召回（Retrieval）+ 知识图谱召回（KG）
4. Prompt 构造（Prompt）
5. LLM 生成答案（LLM）
6. AI 生成后续追问（followup）

### 2.2 `rag=false`

- 直接走 LLM 对话，不执行意图/检索/KG。

## 3. 关键行为说明

### 3.1 Follow-up 由 AI 生成

`followup_questions` 不再是硬编码模板，而是由模型根据当前上下文动态生成：

- 最多返回 3 条
- 仅保留与当前主题相关的问题
- 输出异常或无效 JSON 时自动回退为不追问

### 3.2 文本清洗（减少噪声）

在进入主流程前，会对用户问题、历史对话、检索命中做统一清洗：

- 去除冗余符号：`{ } [ ] " ' “ ” ‘ ’ \``
- 压缩连续空白字符
- 去重并规范化引用命中

## 4. API 总览

统一前缀：`/api/*`

### 4.1 核心接口

- `GET /api/health`
- `POST /api/chat`
- `POST /api/chat/stream`（SSE）

`POST /api/chat` 请求示例：

```json
{
  "query": "水稻纹枯病怎么防治？",
  "user_id": "u001",
  "session_id": "sess_u001_001",
  "location": "湖南",
  "rag": true
}
```

字段说明：

- `query`：用户问题（必填，不能为空）
- `user_id`：用户 ID（可选）
- `session_id`：会话 ID（可选；为空时后端自动生成并回传）
- `location`：地域信息（可选）
- `rag`：是否启用 RAG 链路（默认 `true`）

响应结构：

```json
{
  "answer": "string",
  "citations": [
    {
      "content": "string",
      "source": "string",
      "score": 0.95
    }
  ],
  "need_followup": true,
  "followup_questions": [
    "问题1",
    "问题2",
    "问题3"
  ],
  "session_id": "sess_u001_001"
}
```

说明：

- `citations` 最多返回 5 条
- `followup_questions` 最多返回 3 条

### 4.2 流式输出（SSE）

`POST /api/chat/stream` 返回 `text/event-stream`，事件格式：

- 分片事件：`{"type":"chunk","content":"..."}`
- 完成事件：`{"type":"done","data":{...同 /api/chat 响应...}}`
- 结束标记：`event: end` + `data: [DONE]`

## 5. 调试接口

用于快速定位问题在意图、检索、路由、提示词还是模型调用层：

- `POST /api/debug/intent`
- `POST /api/debug/retrieval`
- `POST /api/debug/kg`
- `POST /api/debug/router`
- `POST /api/debug/prompt/rag`
- `POST /api/debug/prompt/direct`
- `POST /api/debug/llm`
- `POST /api/debug/llm/stream`

## 6. 数据库

目前使用轻量的SQLite（默认：`backend/data/chat.db`），当前使用单表 `chat_history`：

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `user_id TEXT`
- `query TEXT NOT NULL`
- `answer TEXT NOT NULL`
- `time TEXT NOT NULL`

## 7. 环境变量

请参考 `backend/.env.example`。

关键配置：

- `DASHSCOPE_API_KEY`
- `DASHSCOPE_BASE_URL`
- `DASHSCOPE_MODEL`
- `DASHSCOPE_TEMPERATURE`
- `DASHSCOPE_MAX_TOKENS`
- `INTENT_RESOURCES_DIR`
- `KG_GRAPH_PATH`
- `KG_SAMPLES_PATH`
- `TOP_K_HITS`
- `HIT_MAX_CHARS`
- `HISTORY_LIMIT`
- `STREAM_CHUNK_SLEEP_MS`

## 8. 启动

1. 安装依赖

   建议使用python10~12

```bash
pip install -r backend/requirements.txt
```

2. 配置环境变量（可复制 `backend/.env.example` 到 `.env`）

3. 启动服务

```bash
python backend/main.py
```

服务地址：`http://127.0.0.1:8000`

## 9. 依赖文件说明

- `requirements.txt`：后端运行依赖（合并版）
- `requirements.extracted.txt`：历史模块依赖提取快照（用于追溯）
