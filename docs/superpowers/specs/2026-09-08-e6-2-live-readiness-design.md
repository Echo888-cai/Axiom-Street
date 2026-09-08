# E6-2 Live Readiness Guard 设计

## 目标

提供一个只读、可审计的 Live 准入检查，以及一个永远 fail-closed 的激活入口。当前仓库没有真实 Broker 实现，因此任何激活请求都必须返回 `409 live_not_ready`，不能创建任务、改变策略状态或触碰外部网络。

## 准入证据

对指定策略的最新版本检查：

1. 策略状态必须是 `APPROVED`。
2. 八个验证闸门在该版本上都必须有最新 `COMPLETED + passed=true + error=null` 记录。
3. 策略 `config.risk_limits` 必须能通过现有 `parse_risk_limits`，不能用缺省或客户端覆盖。
4. 必须存在最新 `PaperReconciliation`，且状态为 `MATCHED`。
5. 服务端 `live_enabled` 开关必须显式为 true。
6. Broker 实现必须存在；当前常量为 false，故当前永远拒绝。

每一项都输出稳定 reason code 和证据值；检查失败不是异常，而是正常的安全结果。

## API

- `GET /api/v1/live/readiness?strategy_id=...`：返回 `{ready, reasons, evidence}`，只读。
- `POST /api/v1/live/activate`：接受策略 ID，重复执行 readiness；未 ready 返回 409，且不 enqueue、不改状态。当前没有成功分支。

## 边界

纯策略函数放在 `quant/execution/readiness.py`；API 只拼装数据库证据。没有 Live Broker、凭证、订单发送代码，也不通过配置开关绕过 `broker_implemented=false`。
