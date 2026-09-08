# 真实 Broker 接入评估（仅设计，不实施）

## 结论

当前不应接入真实 Broker。系统已经具备纸面执行、独立风控、对账快照、Live readiness 检查和 fail-closed 激活接口，但还缺少真实资金环境必须具备的订单状态机、外部状态对账、凭证隔离、幂等重试、人工审批和可演练的 kill switch。现在接入会把研究系统的可信边界直接扩大到资金风险边界。

当前代码事实：

- `services/api/routers/live.py` 中 `LIVE_BROKER_IMPLEMENTED = False`。
- `POST /api/v1/live/activate` 当前不会 enqueue、改状态或触碰外部网络。
- `quant/execution/paper.py` 是纯纸面规则，不能直接当作外部 Broker 适配器。
- `GET /api/v1/live/readiness` 会输出策略状态、八个验证闸门、风险配置、纸面对账、开关和 Broker 实现状态。

## 未来边界

```text
策略信号
   │
   ▼
服务端风控 ──拒绝/缩量──┐
   │                    │
   ▼                    │
订单意图（幂等键）       │
   │                    │
   ├─ PaperAdapter       ├─ BrokerAdapter（未来）
   │                    │
   ▼                    ▼
纸面账本              外部订单 API
   │                    │
   └──────┬─────────────┘
          ▼
订单/成交/持仓对账 → 风险状态 → 审计与告警
```

Broker 适配器只能位于执行层；策略和 Agent 不得持有 Broker 客户端、API key 或订单发送权限。所有下单请求必须先通过同一个服务端风险引擎，并且把 `strategy_id`、版本、组合、风险决定、client order id 一起写入审计记录。

## 必须先完成的准入门槛

1. 订单状态机：`INTENT → SUBMITTED → ACKNOWLEDGED → PARTIALLY_FILLED/FILLED/REJECTED/CANCELLED`，每次状态转移可重放且不可伪造。
2. 对账：周期性拉取 Broker 的订单、成交、现金和持仓，与本地账本逐项匹配；任何不一致自动禁止新单。
3. 凭证隔离：凭证只存在 worker 的 secret store，API、前端、Agent、日志和错误响应都不可读取；必须支持轮换和撤销。
4. 幂等和重试：网络超时不能重复下单；重试前必须用 client order id 和 Broker 查询确认原请求状态。
5. Kill switch：数据库状态、worker 进程和 Broker 端撤单都要有独立停机路径；停机后默认只允许平仓或人工恢复。
6. 人工审批：策略、版本、组合、账户、额度和交易时段需要一次性审批快照；配置变化立即失效。
7. 灾难演练：Broker 不可用、网络分裂、部分成交、时钟漂移、重复 webhook、凭证泄露和数据库恢复都要有演练记录。
8. 观测门槛：订单延迟、拒单率、未对账数量、暴露、现金、kill-switch 状态和最后一次 Broker 心跳必须进入 `/health`、`/metrics` 和审计告警。

## 推荐的实施顺序

先继续完善纸面环境的订单状态和对账演练，再做一个只读 Broker sandbox adapter；完成契约测试后才允许极小额度、单策略、单账户的人工批准灰度。任何阶段都不能通过设置 `STREET_LIVE_ENABLED=true` 单独绕过 Broker 实现和对账门槛。

## 本阶段明确不做

- 不安装或选择具体 Broker SDK。
- 不增加 API key、secret、账户号或外部网络调用。
- 不创建真实订单、持仓、成交或 Broker webhook 接口。
- 不把 Live 页面改成“已可用”。Live 继续显示未开放并由服务端 fail-closed。
