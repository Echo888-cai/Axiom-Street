# E8-1 Portfolio Attribution 设计

## 目标

建立组合、策略配置和单期归因快照的最小闭环。归因只使用显式传入且可追溯的策略期间收益与基准收益；系统不生成行情、不声称实时风控，也不把研究结果自动变成投资建议。

## 模型

- `portfolios`: 组合名称、基础货币、生命周期状态和初始资金。
- `portfolio_allocations`: 组合在某个有效期内对策略的目标权重；同一组合/策略/生效日唯一，权重必须非负。
- `portfolio_attributions`: `as_of` 单期快照，保存组合收益、基准收益、allocation / selection / interaction / active effect，以及用于重建的输入 JSON。

## 归因定义

对 N 个已配置策略，以等权基准 `b_i = 1/N`，配置权重为 `w_i`，策略收益为 `r_i`，各自基准收益为 `m_i`：

```text
benchmark_return = Σ b_i m_i
allocation_effect = Σ (w_i - b_i) m_i
selection_effect  = Σ b_i (r_i - m_i)
interaction_effect = Σ (w_i - b_i) (r_i - m_i)
portfolio_return  = Σ w_i r_i
active_return     = portfolio_return - benchmark_return
active_return     = allocation + selection + interaction
```

权重总和必须为 1（误差不超过 `1e-9`），策略不能重复，所有输入必须为有限数。任何不完整输入都失败，不用 0 填充。

## 边界

- `quant/portfolio/attribution.py` 只负责纯计算和校验，不导入数据库或 Web 框架。
- `services/api` 负责组合/配置写入和快照查询；归因 API 读取数据库权重，将收益输入交给纯函数，再写入一条不可变快照。
- 不接入外部因子供应商；`factor_exposures` 留给后续包，避免伪造因子暴露。
- 组合配置不会修改策略状态，不会触发 Live 执行。

## API

- `POST /api/v1/portfolios`、`GET /api/v1/portfolios`
- `POST /api/v1/portfolios/{portfolio_id}/allocations`
- `POST /api/v1/portfolios/{portfolio_id}/attribution`
- `GET /api/v1/portfolios/{portfolio_id}/attribution`

归因请求只携带 `as_of` 和每个已配置策略的 `strategy_return` / `benchmark_return`；权重从服务端配置读取。

## 验证

- 纯函数测试完整分解恒等式、权重和、重复策略、缺失/NaN 输入。
- API 测试组合与配置 CRUD、未知策略拒绝、归因快照写入和查询。
- Alembic migration、OpenAPI codegen、全仓库测试和构建必须通过。
