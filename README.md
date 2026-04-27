# Agri Backend

农业问答后端 (FastAPI + MySQL + LangChain/Chroma)。

本项目作为“作物生长智能体”的核心服务，集成了 RAG 对话、意图识别、会话管理及知识库维护功能。

## 核心能力

- **农业 RAG 对话**: 基于 Chroma 向量检索和 LangChain 编排，支持本地知识库增强。
- **意图识别模块**: 集成 BERT 模型，自动识别 `agri` (农业)、`non_agri` (非农业) 及 `clarify` (需澄清) 意图。
- **会话持久化**: 使用 MySQL 存储用户信息与聊天记录，支持 `session_id` 维度的上下文追踪。
- **流式响应**: 支持 SSE (Server-Sent Events) 流式输出，提升用户交互体验。
- **地理位置适配**: 结合前端传入的坐标，动态调整回答策略并提供本地农业天气。

## 快速启动 (Windows)

在 `backend` 目录执行：

1. **创建并激活虚拟环境**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. **安装依赖**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **配置环境**:
   复制 `.env.example` 为 `.env`，并配置以下关键项：
   - `DATABASE_URL`: MySQL 连接字符串 (e.g., `mysql+pymysql://root:password@localhost:3306/agri_db`)
   - `DASHSCOPE_API_KEY`: 阿里云百炼 API Key
   - `DASHSCOPE_MODEL`: 推荐使用 `glm-4.7` 或 `qwen-plus`

4. **初始化数据库**:
   如果使用 MySQL，先创建数据库再导入 SQL 文件：
   ```powershell
   mysql -u root -p < backend/scripts/db_scripts/init.sql
   ```
   或运行迁移脚本修复表结构：
   ```powershell
   python fix_db_v2.py
   ```

5. **启动服务**:
   ```powershell
   python main.py
   ```

服务地址：`http://127.0.0.1:8000`

## API 总览

### 核心接口
- `POST /api/auth/login`: 用户登录
- `POST /api/chat/stream`: 流式对话接口 (SSE)
- `GET /api/weather`: 获取农业天气信息

### 知识库管理
- `POST /api/knowledge/upload`: 上传知识文件
- `POST /api/knowledge/index/update`: 更新/重建向量索引
- `GET /api/knowledge/index/status`: 查询索引状态

### 调试接口 (Debug)
- `POST /api/debug/intent`: 测试意图识别
- `POST /api/debug/llm`: 测试大模型直接调用

## 依赖说明
- **Python**: 3.10.x
- **关键库**: `fastapi`, `langchain-openai`, `sqlalchemy`, `pymysql`, `transformers`, `chromadb`
- **注意**: 由于版本兼容性，`bcrypt` 需锁定为 `4.0.1`。

## 目录结构
- `app/api.py`: 路由定义
- `app/modules/agri_qa/`: 问答逻辑与 RAG 核心
- `app/modules/intent/`: 意图识别模型加载与推理
- `app/repositories/`: 数据库访问层
- `models/intent/`: 存放预训练的 BERT 模型
