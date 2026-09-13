# 后端可靠性交接计划

> 执行方式：使用 executing-plans 按任务顺序推进，每次只处理一个任务；不需要并行代理。保留工作区现有修改。

**目标：** 先确认运行环境对应当前代码，再补齐跨页统计与异步任务恢复的验收证据，使界面呈现的状态与实际研究结果一致。

**架构：** 保持 FastAPI → services → 数据层、Celery → quant/LEAN 的现有边界。浏览器只访问同源网关；Agent 只提供受限建议；Live 继续关闭。

**技术栈：** FastAPI、SQLAlchemy、PostgreSQL、Celery、Redis、LEAN；前端 Next.js 与 React Query。

**依据：** `docs/architecture.md`、`docs/validation-gates.md`、`docs/frontend-handoff.md`。此文是 `docs/PLAN.md` 的执行附件，不替代当前状态台账。

## 已确认事实与边界（2026-09-13）

- 当前源码已有健康聚合、Worker 心跳、孤儿任务回收、Paper 幂等与对账；不要重写现成能力。
- 本机 `127.0.0.1:8000/health` 返回 `status=ok`，但仅见 postgres/redis/docker，没有当前 `services/api/health.py` 定义的 worker/security 检查项；Docker 为 false。运行实例可能来自较早版本或另一部署，尚未定位。不能据此断言整个系统健康，也不能直接重启未知实例。
- 策略列表服务端返回 `items/total/limit/offset`，默认 100 条；前端 `strategiesApi.listStrategies` 经 `unwrapList` 丢弃分页元数据，首页和策略摘要按所加载的数组计数。因此超过一页时存在统计范围限制。
- 本轮只调整视觉并编写计划。已有回测数据可读不等于本轮完成真实回测；没有执行新的 Docker/LEAN Golden 或 Paper 下单。

## 任务 1：对齐运行版本并验收一条真实研究链路（最高优先级）

**涉及文件：** `services/api/health.py`、`services/api/main.py`、`services/worker/health.py`、`services/worker/celery_app.py`、`Makefile`、`docker-compose.yml`、`tests/unit/test_health_monitoring.py`、`tests/golden/test_spy_200dma_golden.py`。

- [ ] 只读定位 8000 端口所属进程、目录、镜像和数据库目标，记录源码版本与运行版本；不要输出凭据。
- [ ] 先执行 `.venv/bin/python -m pytest tests/unit/test_health_monitoring.py -q`，确认源码健康接口的基线。若发现缺口，先补失败测试再修改。
- [ ] 在独立测试库和隔离端口启动当前 API/Worker，使用正常迁移；正式验证不使用 `STREET_SKIP_MIGRATIONS=1`。确认缺失/过期 Worker 心跳、Redis 不可用、沙箱检查失败都显示真实降级状态。
- [ ] 使用已固定镜像和已有合法数据快照运行 `.venv/bin/python -m pytest tests/golden/test_spy_200dma_golden.py -q`。缺少环境条件时记录阻塞，不把跳过当通过。
- [ ] 通过前端验证：创建测试研究 → 保存版本 → 回测排队 → Worker 执行 → 指标/曲线/试验记录 → 稳健性验证。仅用测试数据，并记录策略版本、快照、回测 ID 和输出证据。
- [ ] 验收：运行环境检查字段匹配当前契约；一次真实作业完成且产物可追溯。将命令、结果、限制记入 `docs/PLAN.md`。

## 任务 2：让概览统计独立于列表分页

**新增：** `services/api/services/overview.py`、`services/api/routers/overview.py`、`tests/unit/test_overview_api.py`、`apps/web/src/lib/api/overview.ts`。

**修改：** `services/api/schemas.py`、`services/api/main.py`、`apps/web/src/lib/api.ts`、`apps/web/src/lib/api/types.ts`、`apps/web/src/app/page.tsx`、`apps/web/src/features/home/home-dashboard.tsx`、`apps/web/src/features/strategy-lab/strategy-collection.tsx`、`apps/web/src/features/strategy-lab/research-brief.tsx`、OpenAPI 与生成类型。

- [ ] 新增失败测试：创建超过 100 条策略，覆盖 DRAFT/BACKTESTED/VALIDATED，验证总数与各状态计数基于完整库；另测空库和无已完成回测。
- [ ] 新增只读 `GET /api/v1/overview`，建议字段为 `strategy_count`、`strategy_counts_by_status`、`latest_completed_backtest`、`as_of`。返回状态分布而非累计通过率；最新回测排序含稳定的 ID 次序。
- [ ] 数据库聚合查询产生计数，沿用已有回测字段与指标口径；不要通过加载全部分页来拼统计，也不要修改试验台账或收益算法。
- [ ] 前端通过独立查询消费摘要，卡片列表仍独立分页；保存/删除/任务完成后使摘要查询失效。加载时显示占位，失败时显示不可用，不能归零。
- [ ] 增加前端行为测试：列表只有 100 条、摘要为 137 时显示 137；状态分布和接口失败状态正确。
- [ ] 同步 OpenAPI 快照及生成类型。执行 Python 新接口测试、相关前端测试、类型检查与构建，记录验收。

## 任务 3：验证任务恢复与重复投递边界

**涉及文件：** `services/worker/tasks/backtests.py`、`services/worker/tasks/validation.py`、`services/worker/tasks/paper.py`、`services/worker/tasks/copilot.py`、`services/api/status_machine.py`、`tests/unit/test_execute_backtest.py`、`tests/unit/test_paper_worker.py`、`tests/unit/test_paper_ledger.py`、`tests/unit/test_copilot_chat.py`。

- [ ] 先阅读现有孤儿回收、事务、幂等键和单测，仅为未覆盖行为新增失败测试。
- [ ] 验证排队超时、执行时 Worker 中断、重复投递、同一作业并发执行。确保试验计数与终态一致；Paper 不重复生成成交或扣款；Agent 不重复记录回复。
- [ ] 若存在多 Worker 部署，专门检验某个 Worker 启动时是否误把另一 Worker 的活跃任务标为孤儿；只在失败测试证明后调整任务归属/心跳判断。
- [ ] 为证实的缺口实施最小修复。不得给所有写操作统一自动重试，也不得删除已记录试验来“修正”指标。
- [ ] 运行上述聚焦测试，再在隔离环境做一次中断恢复演练。确认前端给出真实失败原因和明确的重新运行入口。

## 成本与交接要求

每轮只读取对应任务的文件、相关测试和必要文档。先做聚焦测试，任务完成时再运行全量回归；不反复扫描仓库或重复安装依赖。库/API 用法遵循项目 Context7 规则；不在文档查询中提交私密数据。

每个任务单独交付：改动文件、测试证据、环境限制、下一步。后端改动收尾执行 `.venv/bin/python -m pytest tests/unit -q`；涉及前端契约时再执行 `npm --prefix apps/web test`、`npm --prefix apps/web run lint`、`npm --prefix apps/web run build`。提交时只包含本任务文件，不打包已有无关修改。

多用户鉴权、真实券商和因子模型另立需求；本计划不开放 Live。不要为完成当前任务重构全栈。
