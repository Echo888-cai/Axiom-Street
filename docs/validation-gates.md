# Axiom Street — 8 个验证闸门的完整判定规则

> 这是唯一的闸门判定来源。源自 `docs/ROADMAP.md` §5.2.1–5.2.8 的「已交付」注记，经 2026-09-04 审计抢救而来。

---

## 1. Walk-Forward（滚动样本外）

| 项目 | 规则 |
|------|------|
| **评分方式** | 拼接样本外 Sharpe（**不是**折 Sharpe 的均值） |
| **塌缩判定** | 样本内 Sharpe 均值 > 0.5 **且** 拼接 OOS Sharpe < 0 → 过拟合塌缩 |
| **闸门** | 未通过 Walk-Forward 者不得进入 `VALIDATED` |
| **模式** | Anchored（扩张窗口）与 Rolling（固定窗口）均支持 |
| **前端** | 每个 fold IS/OOS Sharpe 条形图 + OOS 拼接净值曲线 |

---

## 2. Deflated Sharpe Ratio (DSR)

| 项目 | 规则 |
|------|------|
| **参考文献** | Bailey & López de Prado (2014), *The Deflated Sharpe Ratio* |
| **输入** | 观测 Sharpe、试验次数 N（来自 `experiment_trials` 同 `(data_snapshot_id, strategy_family)` 计数）、试验间 Sharpe 方差、收益序列偏度/峰度、样本长度 T |
| **输出** | 经多重检验与非正态修正后的 Sharpe、该 Sharpe 为真的概率 |
| **闸门** | **DSR ≥ 95%** → 通过 |
| **展示** | Tearsheet 最顶部，视觉优先级高于原始 Sharpe |

---

## 3. PBO（过拟合概率）via CSCV

| 项目 | 规则 |
|------|------|
| **参考文献** | Bailey et al. (2015), *The Probability of Backtest Overfitting* |
| **方法** | Combinatorially Symmetric Cross-Validation：收益序列切成 S 份，枚举 C(S, S/2) 种训练/测试划分，取样本内最优配置观察样本外排名；PBO = 样本内最优在样本外落入中位数以下的比例 |
| **S 的选择** | 能整除 T 的最大偶数 ∈ {16, 14, 12, 10, 8, 6, 4}，且每份 ≥ 10 根交易日；否则**失败而非丢交易日** |
| **闸门** | **PBO ≤ 0.5** → 通过；PBO > 0.5 = 过拟合红色警示 |
| **策略要求** | 必须 `GetParameter("lookback")`；净值无法区分则拒绝 |
| **记录** | 每个格子写 `Backtest` + `experiment_trials` |

---

## 4. 参数敏感性与稳健性

| 项目 | 规则 |
|------|------|
| **方法** | 对参数做网格扰动，绘制 Sharpe 响应曲面 |
| **核心判定** | 最优点是**孤峰**（knife-edge，过拟合）还是**高原**（plateau，稳健） |
| **高原标准** | 峰值周围**连续 ≥ 3 个点**落在 **0.5 Sharpe 带宽**内 = 高原 |
| **闸门** | **必须为高原** → 通过；净值无法区分则失败 |
| **默认扫描** | `lookback` 参数 |

---

## 5. 成本敏感性与盈亏平衡成本

| 项目 | 规则 |
|------|------|
| **方法** | 逐步提高单边成本（全部计入 `slippage_bps`，`fee_usd=0`），对 `alpha_capm` 线性插值求临界 bps |
| **网格要求** | **必须包含 0 bps** |
| **真实成本基线** | 默认 5 bps（与填单约定一致） |
| **闸门** | **临界成本 > 真实成本** → 通过；临界 ≤ 真实成本 → 判死 |
| **策略要求** | 必须 `GetParameter("slippage_bps")` |

---

## 6. Stationary Bootstrap 置信区间

| 项目 | 规则 |
|------|------|
| **参考文献** | Politis & Romano (1994) geometric blocks；块长用 Politis & White (2004) AR(1) plug-in |
| **禁用** | 简单 iid 重抽样 |
| **输出** | Sharpe、CAGR、MaxDD 的 95% 分位区间 |
| **闸门** | **Sharpe 95% 区间下界 > 0** → 通过；≤ 0 不能进入 `VALIDATED` |
| **最小样本** | **< 252 个交易日失败**，而非报窄区间 |
| **扫描回测** | 不写 BOOTSTRAP 结果，避免短窗污染闸门 |
| **自动写入** | 回测完成时自动写入（仅全样本回测） |

---

## 7. 制度（Regime）稳定性

| 项目 | 规则 |
|------|------|
| **切分轴** | 牛/熊、高/低波动、加息/降息、压力窗口（2008、2020-03、2022） |
| **牛熊定义** | **基准** 20% 峰谷（不是策略自身曲线） |
| **波动定义** | 21 日实现波动 vs 样本中位数 |
| **利率周期** | FOMC 加息/降息**生效日**（不是实时利率源） |
| **最小窗口** | **各轴 ≥ 60 个交易日**，否则拒绝判定 |
| **压力窗口** | 只报告，**不闸门** |
| **基准缺失** | 失败，而非用策略曲线冒充市场 |
| **互补制度** | 互补制度 Sharpe 为负 → 不能进入 `VALIDATED`；edge 集中但互补 ≥ 0 → 通过并标注 |
| **扫描回测** | 不写 REGIME，避免短窗污染闸门 |
| **自动写入** | 回测完成时自动写入（仅全样本回测） |

---

## 8. 多重检验校正 — Hansen SPA_c

| 项目 | 规则 |
|------|------|
| **参考文献** | White (2000) *A Reality Check*；Hansen (2005) *A Test for Superior Predictive Ability* |
| **方法** | 对同一家族、同一数据快照的样本内试验做**联合 stationary bootstrap**（禁止 iid） |
| **基准** | 默认相对现金（收益相对 0） |
| **闸门** | **Hansen SPA_c：p < 0.05 且 T > 0** → 通过 |
| **同时报告** | White RC、SPA_l、SPA_u |
| **最小条件** | **≥ 2 条可区分试验 + 252 个共同交易日** |
| **截断规则** | **> 64 条拒绝截断**，而非悄悄丢掉 |
| **触发时机** | 手动发起（`/validation` 页面），**不**在回测或参数扫描完成后自动写入（扫描窗口短于 252 根，K=1 全样本也不能伪造通过） |

---

## 闸门组合逻辑（策略状态机）

```
VALIDATED 要求（全部必须通过）：
├─ Walk-Forward 通过
├─ DSR ≥ 95%
├─ PBO ≤ 0.5
├─ 敏感性 = 高原
├─ 临界成本 > 真实成本
├─ Bootstrap Sharpe 下界 > 0
├─ Regime：互补制度 Sharpe ≥ 0（且各轴 ≥ 60 交易日）
└─ SPA_c：p < 0.05 且 T > 0（仅当手动触发时检查）

任一失败或新增失败 → 从 VALIDATED 降回 BACKTESTED
客户端 PATCH VALIDATED → 409 Conflict
```

---

## 实现位置速查

| 闸门 | 核心实现 | API 端点 | Celery 任务 | 前端 |
|------|----------|----------|-------------|------|
| Walk-Forward | `quant/validation/walk_forward.py` | `POST /api/v1/validation/walk-forward` | `validation.walk_forward` | `/validation` |
| DSR | `quant/metrics/deflated_sharpe.py` | 隐式（回测完成自算） | — | tearsheet 顶部 |
| PBO | `quant/validation/pbo.py` | `POST /api/v1/validation/pbo` | `validation.pbo` | `/experiments` |
| 敏感性 | `quant/validation/sensitivity.py` | `POST /api/v1/validation/sensitivity` | `validation.sensitivity` | `/validation` |
| 成本 | `quant/validation/cost.py` | `POST /api/v1/validation/cost` | `validation.cost` | `/validation` |
| Bootstrap | `quant/validation/bootstrap.py` | `POST /api/v1/validation/bootstrap` | `validation.bootstrap` | tearsheet（自动） |
| Regime | `quant/validation/regime.py` | `POST /api/v1/validation/regime` | `validation.regime` | tearsheet（自动） |
| SPA | `quant/validation/spa.py` | `POST /api/v1/validation/spa` | `validation.spa` | `/validation` |