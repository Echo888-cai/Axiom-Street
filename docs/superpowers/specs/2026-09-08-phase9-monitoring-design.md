# Phase 9 运行监控规格

## 目标

让操作者在系统内看到 API、数据库、Redis、Worker/Docker、LEAN 沙箱和 Prometheus 观测状态，并对 Worker 心跳过期给出明确的降级状态。

## 设计

- 后端 `/health` 和 `/api/v1/health` 保持兼容，`checks` 增加 `worker` 与 `security`，不暴露环境变量值、凭证或完整异常堆栈。
- Worker 心跳按现有 90 秒 TTL 判断；缺失或过期即 `ok=false`，说明具体是“未上报”还是“心跳过期”。
- `security` 检查反映应用实际使用的沙箱策略，而不是人工标记。
- 前端设置页增加“运行监控”卡片，定时刷新并展示状态、心跳年龄、Docker/LEAN 镜像、沙箱策略与 Prometheus 地址。
- 所有状态来自真实 health API；失败、缺失、不可用统一显示 `—` 或降级，不生成模拟数值。

## 验收标准

1. 健康接口能区分 PostgreSQL/Redis/Worker/Docker/Sandbox 状态。
2. Worker 心跳缺失或超过 90 秒时整体至少为 `degraded`，PostgreSQL 失败时为 `down`。
3. 设置页有可测试的运行监控卡片，支持刷新和错误态。
4. 现有 `/health` 契约、前端全量测试和生产构建通过。
