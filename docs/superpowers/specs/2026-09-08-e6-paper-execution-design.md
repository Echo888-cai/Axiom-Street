# E6-1 纸面执行底座设计

## 目标

建立一个只使用本地模拟价格的纸面执行闭环：订单请求进入队列后，由 Worker 从策略版本读取风险配置，重新计算账户和持仓敞口，经过现有纯 `RiskEngine` 后才允许成交；成交、持仓、现金和对账结果全部留在可审计数据库中。

## 明确不做

- 不连接 Alpaca、IBKR 或任何真实券商。
- 不允许客户端提交或覆盖 `risk_limits`、当前敞口、账户余额和风险判定结果。
- 不做策略信号生成、自动调仓、做空、融资和复杂订单类型。
- 不把 `PAPER` 结果标记成 `LIVE`，也不自动推进策略状态。

## 数据流

```text
POST /paper/orders
        │ 只提交 symbol / side / quantity / simulation_price / client_order_id
        ▼
API 读取策略存在性 ── enqueue ──► Worker
                                  │
                                  ├─ 读取 StrategyVersion.config.risk_limits
                                  ├─ 从 fills + PaperPosition 重建当前敞口
                                  ├─ RiskEngine.decide(...)
                                  │       ├─ 拒绝: PaperOrder.REJECTED
                                  │       └─ 通过/缩量: PaperBroker 全额模拟成交
                                  ├─ 写 PaperOrder + PaperFill + PaperPosition + PaperAccount
                                  └─ 更新 reconciliation 快照
```

`simulation_price` 明确表示用户选择的回放价格，不代表实时行情；因此它只能用于 PAPER 环境，API 文案和响应都要保持诚实。

## 数据模型

- `paper_accounts`: 每个策略一个模拟账户，保存 `cash`、`initial_capital`、`updated_at`。
- `paper_orders`: append-only 请求台账，`client_order_id` 唯一；记录订单方向、请求数量、模拟价格、风险结果、状态和错误。
- `paper_fills`: 只为 `FILLED` 订单生成；记录实际成交数量、价格和手续费。
- `paper_positions`: 每个策略/标的一个可重建的当前持仓快照，记录数量、均价、已实现盈亏和最新标记价格。
- `paper_reconciliations`: 保存从成交重建的持仓与快照持仓差异；`MATCHED` 才表示对账通过。

订单状态只有 `QUEUED`、`FILLED`、`REJECTED`、`FAILED`。风险拒绝是正常业务结果，不伪装成 Worker 失败。

## 风险和幂等规则

1. Worker 从最新策略版本的 `config.risk_limits` 读取配置，并使用 `parse_risk_limits`；缺失或非法配置 fail loud。
2. 当前 `gross`、`net`、`current_weight` 和账户权益均由数据库中的账户/持仓与本次模拟价格推导，客户端不能传入。
3. 第一版只允许卖出已有多头，不允许卖空；卖出数量超过持仓直接 `REJECTED`。
4. 重复 `client_order_id` 不再生成新成交；返回已经存在的订单结果。
5. 纸面成交采用全额成交，手续费为 0；后续成本模型作为独立工作包加入，不能在这里偷偷引入近似。
6. 任何 `REJECTED`/`FAILED` 订单都不能写入成交或改变现金和持仓。

## API

- `POST /api/v1/paper/orders`：只读校验策略后排队，返回 `202 {status: "queued"}`；Worker 负责写入订单结果。
- `GET /api/v1/paper/orders?strategy_id=...`：按创建时间倒序返回订单台账。
- `GET /api/v1/paper/positions?strategy_id=...`：返回当前持仓与现金。
- `GET /api/v1/paper/reconciliation?strategy_id=...`：返回最近对账快照和差异。

请求字段：`strategy_id`、`symbol`、`side`、`quantity`、`simulation_price`、`client_order_id`。数量和价格必须为有限正数，标的统一大写；客户端不能选择策略版本或风险规则。

## 边界

- `quant/execution` 是纯领域层，负责订单命令校验、风险决策输入计算和持仓重建，不导入 FastAPI、SQLAlchemy 或 Celery。
- `services/api` 只负责 HTTP schema、存在性读取和 enqueue，以及只读查询。
- `services/worker` 是唯一执行副作用的入口，负责事务性写入和幂等处理。
- 真实券商接口不创建空壳实现；Live 继续保持关闭。

## 验证

- 纯领域测试：风险上限缩量、回撤暂停、卖空拒绝、持仓重建和订单幂等输入。
- Worker 测试：允许订单生成一条 fill、更新现金/持仓/对账；风险拒绝不产生 fill；重复 key 不重复成交。
- API 测试：错误策略 404、非法数值 422、有效请求 202、列表只读返回。
- 数据库测试：Alembic 迁移可升级，唯一约束和外键生效。
