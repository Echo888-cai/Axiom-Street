# P5-4 受约束研究对话设计

**日期：** 2026-09-08  
**状态：** 已纳入持续交付计划  
**范围：** Copilot 对话台账、异步任务、Provider 适配、右栏交互

## 目标

为已经存在的 Copilot 聚合上下文、劝停分析和建议动作增加一个可追踪的研究对话入口，使用户能够围绕当前策略或回测提问，并获得基于真实台账事实的回答。

## 安全边界

- 对话只能绑定当前策略或回测 scope。
- 用户问题长度限制为 1–1200 字符；空白问题拒绝。
- Provider 输入由“聚合上下文 + 用户问题”组成，禁止读取策略源码、参数配置、价格序列和风险限额写入口。
- Provider 只返回文本；不接受工具调用、不执行代码、不改变策略状态、不创建验证任务。
- 现有建议动作仍由确定式候选生成，用户确认后才调用现有验证 API。
- 每次对话请求、状态、模型、回答、错误和耗时写入 `copilot_chat_messages`，形成可审计台账。
- 没有 API key 时返回诚实的禁用状态，不排队、不出站。

## 方案

- 新增 `CopilotChatMessage` 模型和 Alembic `0012_copilot_chat_messages`。
- Agent 层新增只读查询 `list_chat_messages` 和 prompt builder `build_chat_messages`。
- Provider 新增 `chat(context, user_message)`，复用已有超时、重试和错误翻译。
- API 新增 `GET /api/v1/copilot/chat` 与 enqueue-only 的 `POST /api/v1/copilot/chat`。
- Worker 新增 `copilot.chat`，只有 `_record_chat` 可以写新的 Copilot 台账。
- 前端右栏增加 `ChatBlock`，展示历史、排队/失败状态、快捷问题和隐私提示。

## 数据流

```text
Web ChatBlock → POST /copilot/chat → API 202 → Celery copilot.chat
    → build_context + user question → DeepSeek aggregate-only
    → copilot_chat_messages → GET polling → Web ChatBlock
```

## 验证

- Provider 覆盖禁用、不出站、成功回答、错误翻译和空回答。
- Worker 覆盖 DONE、FAILED、未知 scope、超长问题和唯一写点。
- API 覆盖 202/404/422/503 和历史消息倒序。
- Agent 隔离锁禁止敏感列、业务写路径和非台账写入。
- 前端覆盖快捷问题、轮询、禁用态、失败态和隐私提示。
- Alembic、Ruff、Mypy、TypeScript、全量测试、构建和 OpenAPI codegen 必须通过。

## 非目标

- 不做开放式 Agent 工具调用。
- 不让模型生成策略代码或直接运行验证。
- 不实现 Paper/Live 下单；这些属于后续 Phase 6/7。
