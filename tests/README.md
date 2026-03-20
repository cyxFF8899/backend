# backend/tests 使用说明

本目录包含两份可交互测试脚本，均支持在终端按编号选择测试项。

## 文件

- `frontend_test.py`
  - 面向前端接口联调
  - 覆盖：`/api/health`、`/api/chat`、`/api/chat/stream`、`/api/knowledge/*`
- `debug_test.py`
  - 调试接口联调
  - 覆盖：`/api/debug/intent`、`/api/debug/retrieval`、`/api/debug/graph`、`/api/debug/router`、`/api/debug/prompt/*`、`/api/debug/llm*`

## 运行方式

在 `backend` 目录执行：

```powershell
python .\tests\frontend_test.py
python .\tests\debug_test.py
```

## 交互说明

脚本启动后会提示：

1. 输入服务地址（默认 `http://127.0.0.1:8000`）
2. 输入超时时间
3. 通过菜单选择测试项

菜单支持：

- `A`：执行全部
- `1`：执行单项
- `1,3,5`：执行多项
- `Q`：退出

## 注意事项

- `debug/llm` 与 `debug/llm/stream` 依赖可用的 LLM API Key。
- `knowledge/index/update` 若选择重建索引，耗时会明显增加。
- 若服务未启动或依赖未安装，脚本会显示失败详情但不会崩溃退出。
