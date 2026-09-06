# Axiom Street — 执行计划与状态

> **本文取代 `docs/ROADMAP.md`,是唯一的计划来源与唯一允许声明"当前阶段/已交付能力"的地方。**
>
> - 原版审计基准:2026-09-04(19 个 commit)。
> - **复核修订:2026-09-06**(HEAD `0a2e355`,316 个受版本控制文件)。本轮对照仓库真实状态做只读审计(W0–W4 各章逐项 grep/行数核实,两轮独立交叉验证),把本文从"纯计划"重写为"**计划 + 执行状态**":W0/W1 已关闭、W2–W4 部分完成,真正剩余的待办收敛到 §3 与各章【残余】小节。
>
> **文档体系(核心 6 份 + README/MASTER)**
>
> | 文档 | 职责 | 变更频率 |
> |------|------|---------|
> | `docs/VISION.md` | 产品宪法:是什么、为谁、**明确不做什么**。冲突时以它为准 | 几乎不变 |
> | `docs/PLAN.md` | **本文**:定位 + 现状 + 全部待办与顺序。唯一的计划与阶段来源 | 每个工作包完成时更新 |
> | `docs/architecture.md` | 目标架构、不可违反边界、已实现行为规格 | 随实现变更 |
> | `docs/data-sources.md` | 数据源能力与摄取契约 | 随数据层变更 |
> | `docs/validation-gates.md` | 8 个验证闸门的判定口径(唯一出处) | 随闸门口径变更 |
> | `docs/frontend-handoff.md` | 前端接手/交接说明(与 White Studio 设计系统配套) | 随前端变更 |
> | `design-system/axiom-street/MASTER.md` | 设计令牌与反模式(White Studio 单浅色主题) | 随 UI 变更 |
>
> 前一轮"收敛为恰好 5 份"的目标已按真实需要修正:多出的 `frontend-handoff.md` 是交接文档、`MASTER.md` 在 design-system 目录,二者都不与计划冲突。收敛的真正目标是"消除互相矛盾的阶段/规格声明",不是机械凑数。
>
> `.cursor/rules/axiom-street.mdc` 是施工纪律(`alwaysApply: true`),不是文档,单独维护。
>
> 阅读顺序:`VISION.md` → 本文第 1、2 章 → 当前工作包章节。

---

## 1. 定位结论(不变,已全部落地)

### 1.1 一句话

**Axiom Street 是一个让你难以自欺的量化研究环境。** 不追求最快的回测器,而是最诚实的那个。

完整信念体系见 `docs/VISION.md`,六条信念不修改。

### 1.2 三个定位问题的执行状态(原 §1.2–1.4 已落地)

| # | 问题 | 结论 | 当前执行状态 |
|---|------|------|-------------|
| **D1** | 两个前端谁是产品? | **`apps/web` 是唯一产品。** | ✅ 已执行:`apps/terminal` 整体删除;其视觉工程收割为 **White Studio 单浅色主题**(见 §7.1 决策记录),而非原计划的"双主题"——该修订由产品所有者 2026-09-05/06 明确 |
| **D2** | 单人自用还是对外产品? | **单人自用,短期不开放。** 认证不做,改为部署约束 | ✅ 已写入 README 与 `docker-compose.yml`。一旦出现第二用户,认证与 `user_id` 贯穿立刻升级为 P0,插在当期工作包之后 |
| **D3** | 语言收口 | **中文界面 + 英文对外文档。** | 🚧 部分执行:i18n 字典 `locales/zh-CN.ts`/`en.ts` 已建,**但组件迁移未完成**(71/90 个 tsx 仍硬编码中文)。残余见 §7.2 |

### 1.3 判定依据简述(为什么这些结论对)

- **D1**:`apps/terminal` 含 959 行合成回测 mock(违反"禁合成数据"铁律)、266 行假 Copilot(违反"验证基建先于 AI"),且不在任何契约里。**删代码、收视觉。** 该执行已完成。
- **D2**:不做认证的前提是永不暴露。API/Web 只绑 `127.0.0.1`;`POST /api/v1/data/ingest` 是已知可接受风险的网络+磁盘 DoS 入口,前提是不可从外部到达。
- **D3**:UI 文案最终全部走字典,预留 `en.ts`。

---

## 2. 现状诚实评估(2026-09-06 复核)

| 维度 | 09-04 评 | **09-06 复核** | 证据 |
|------|---------|--------------|------|
| 架构边界 | A− | **A−** | `grep` 确认 `quant/` 零 import FastAPI/Celery/SQLAlchemy/services;Controller 不碰 LEAN 内部(注:尚无 import 扫描锁测试,见 §6.6) |
| 结果真实性 | A− | **A−** | 真实 LEAN Docker + golden test 锁数字 |
| 统计验证 | A− | **A−** | 8 闸门全部落地且阻塞式;`validation-gates.md` 成文 |
| 任务编排 | B+ | **B+** | Celery + 真取消 + 超时 + 孤儿回收 + Beat |
| 工程基建 | B | **B** | 后端测试未见减少(~349);CI + nightly golden;9 个 Alembic migration |
| 指标正确性 | A− | **A−** | P0-1/2/3 已修;对账测试在 |
| 数据工程 | B+ | **B+** | 内容寻址快照、fail-closed quality、双源对账、PIT universe、增量摄取、限速 |
| **前端质量** | C+ | **C+→B−** | 令牌与测试有进步(hex 0、43 用例、E2E 规格齐),但仍有表单未接线、i18n 未迁移、E2E 未进 CI、3 个组件 >400 行。**仍是当前唯一明显落后维度** |

### 2.1 前端残余短板(审计量化)

| 问题 | 现状 |
|------|------|
| 测试覆盖 | Vitest **43 用例/9 文件**(基线 18);组件测试仅 2 个文件。目标 ≥60 |
| E2E | 3 条关键路径规格已在 `src/e2e/critical-paths.spec.ts`,**未进 CI**、package.json 无脚本 |
| 表单收敛 | 单一 `ValidationRunForm.tsx`(424 行)已写**但未接入任何页面**;/validation 仍是 7 份旧表单,/experiments 自带 PBO 表单 |
| i18n | 字典已建,**71/90 个 tsx 仍硬编码中文**(`nav.ts` 11 个标签未抽) |
| 体积 | 新增功能造出超线组件:`backtest-studio.tsx` 601、`strategy-lab.tsx` 548、`ValidationRunForm.tsx` 424(上限 400) |
| 对比表 | 跨策略多曲线可用,但表列(CAGR/Sharpe 等)后端未回传 → 多为"—" |

### 2.2 与原计划的偏差记录(不隐藏)

| 偏差 | 事实 | 处置 |
|------|------|------|
| 顺序 | 计划要求 W0→W1→W2→W3→W4;实际 commit 顺序 **W0(09-04)→W1(09-05)→W4 特性(09-05)→W2(09-06)** | 侥幸未伤闸门;W3a 令牌与 W4 特性相互独立,风险可控。本文按真实状态重排,不再假装原顺序成立 |
| 设计方向 | 原 W3a 写"浅+深双主题收割 terminal";落地改为 **White Studio 单浅色玻璃**(产品所有者拍板),`globals.css` 残留深色 media query | 已锁定 White Studio,见 §7.1;残留深色 CSS 一并清理 |
| 附录基线 | 以 304 文件为基准预测 316→~250;实际文件增加(测试/i18n/E2E 资产合法新增) | 附录 A 已按 09-06 实测重估 |
| 治理残留 | `docs/superpowers/plans/2026-09-05-white-studio.md`(某模型施工计划,grep 零引用) | 随本轮删除,git 历史即归档 |

### 2.3 执行状态仪表盘(审计后)

| 包 | 状态 | 一句话 |
|----|------|--------|
| **W0** 文档融合 | ✅ 已关闭(09-04) | ROADMAP 删除;`validation-gates.md` 落地;阶段单一声明 |
| **W1** 垃圾清除 | ✅ 主体已关闭(09-05) | terminal/risk/packages/duckdb 删除;无合成回测模块;**残余**:ingest shim、SPY.parquet 跟踪(§6.6) |
| **W2** 架构整理 | ✅ 后端主体(09-06)+ 残余 W2-1…4 已收口;W2-5 codegen 转 RC-W3 | `ValidationSpec` 注册表 + `GET /specs`;`validation.py` 1161→629;worker 拆包完成,单文件 ≤500;quant 边界锁测试在;测试 346 全绿 |
| **W3** 前端 UI v2 | 🚧 部分完成;方向已锁 White Studio | 令牌/hex=0/i18n 结构已做;**W3-4 ✅(测试 63)、W3-3 ✅(e2e 脚本 + 按需全栈 workflow)**;修复 W4 潜伏 tsc 债(tsc 0、build 过);表单接线 W3-1、i18n 迁移 W3-2、压线 W3-5 未做(§7.2) |
| **W4** Phase 4 收尾 | 🚧 特性已提前落地(09-05) | 多回测对比 + MAE/MFE 面板已接入;对比表字段、OpenAPI codegen、验收未完成(§8) |

---

## 3. 残余执行总览

顺序即依赖:**先关后端残余 → 再接前端接缝 → 再 W4 收尾验收 → Phase 4 关闭**。任何一步都不得越过验证闸门测试与 Phase 5 边界。

| 包 | 内容 | 依赖 | 为什么在这个位置 |
|----|------|------|----------------|
| **RC-W2** | 后端残余收口:worker 拆包、quant 边界锁、清 ingest shim、SPY untrack | ✅ 已关闭(2026-09-06) | W2-1…4 完成;W2-5 OpenAPI codegen 转 RC-W3 前端接线前 |
| **RC-W3** | 前端接缝:ValidationRunForm 接线、对比表字段、i18n 迁移、E2E 进 CI、测试 43→60、压超线组件、White Studio 反模式收口、OpenAPI codegen(§7) | RC-W2 的表单部分 | 依赖注册表稳定后的统一类型 |
| **RC-W4** | Phase 4 收尾验收:对比表补字段、golden、README/状态同步、关闭 Phase 4(§8.1) | RC-W2、RC-W3 | 收尾项少但必须在 Phase 5 之前关闭 |

累计到"可以开 Phase 5"约 **3–5 周**(单人)。

---

## 4. W0 — 文档融合【2026-09-04 已关闭】

已完成:删除 `docs/ROADMAP.md`(git 历史即归档);抢救"已交付规格"成 `docs/validation-gates.md`(143 行,8 闸门口径唯一出处);缓存键语义并入 `architecture.md`;README 状态表收敛为单一行;`MASTER.md` 重写(后续演化为 White Studio,见 §7.1);`.cursor/rules` 阶段指向本文。

验收已过:`grep ROADMAP` 无活文档命中;阶段只在 README→PLAN 指向一处声明;闸门口径一处读全。

---

## 5. W1 — 垃圾代码清除【2026-09-05 主体已关闭】

已完成:删除 `apps/terminal`(4,403 行,含合成 mock);删除 `quant/risk`、`packages/`、`quant/data/duckdb_query.py` + duckdb 依赖;卸载 `@tanstack/react-table`/`date-fns`;新增 `services/api/prune_jobs.py` + Makefile `prune-jobs`;`quant/data/ingest_spy.py` → `quant/data/ingest/{__init__,snapshot,incremental,cli}.py`;补 `.gitignore` `corporate_actions` 规则。

验收:ruff/mypy/pytest/tsc/npm 全绿;golden 数字逐点不变;净删除达标。**两处残余转 §6.6**(ingest shim 未清、SPY.parquet 仍被 git 跟踪)。

---

## 6. W2 — 架构整理【主体 2026-09-06 已关,残余见 6.6】

### 6.1 核心问题:七份复制粘贴(已解决)

7 类验证检验在 API/Worker/Web 三层的重复样板已收敛。`services/api/services/validation_spec.py`(683 行)定义 `ValidationSpec` 注册表:8 种 kind 各带 `params_schema` / `step_count` / `gate_check` / `auto_on_backtest`,router 暴露 `GET /specs`。`services/api/services/validation.py` 由 1,161 → **629 行**(通用 `create_run`,单一 spec 驱动)。

**仍处于重构期、未完成收敛的是 Web 层表单(§7.2)与 worker 层任务(§6.6)。**

### 6.2 ValidationSpec 目标形态(实现依据,保持)

```
ValidationSpec
├─ kind              WALK_FORWARD | DSR | PBO | SENSITIVITY | COST | BOOTSTRAP | REGIME | SPA
├─ params_schema     Pydantic model(前端表单由它生成)
├─ step_count(params)  进度条步数
├─ runner            quant/validation/ 里的纯函数入口
├─ gate              判定规则(口径来自 docs/validation-gates.md)
└─ auto_on_backtest  bool(bootstrap / regime 为真,SPA 必须为假)
```

**风险控制(在 RC-W2 拆包时继续遵守)**:`tests/unit/test_validation_pipeline.py`(故意过拟合策略必须 PBO>0.5、DSR 不过 95%、客户端 PATCH `VALIDATED` 仍 409)必须在重构前后逐字节相同断言下通过;7 个 `test_execute_*.py`(加回测共 8 个)全部保留。先走通一个检验再迁其余,不做一次性大爆炸。

### 6.3 `ingest_spy.py` 拆分(已做)

已拆成 `quant/data/ingest/` 四模块。**残余**:`__init__.py` 内仍保留 `ingest_spy()` 兼容 shim,与"删 shim、调用点走通用函数"指令相悖;`routers/data.py` 端点与 2 个测试仍引用 shim。转 §6.6。

### 6.4 其余架构项

| 项 | 状态 |
|----|------|
| `settings/page.tsx` 411 行 | ✅ 已收敛为 5 行,逻辑移 `features/settings/settings-desk.tsx` |
| `quant/` 零 web-import 边界锁**测试** | ❌ 不变式仍成立,但无 import 扫描测试(转 §6.6) |
| `packages/` | ✅ 已删,不重建;类型产物落地于 `apps/web/src/lib/api/`(转 §6.6 codegen) |

### 6.5 OpenAPI codegen(未完成,转 §6.6)

`lib/api.ts` 685 行已手工拆为 `lib/api/{types,http,…}.ts`,`types.ts` 手工维护且**无 generated 标记**。镜像 `schemas.py` 的"双真值静默漂移"风险仍在。目标:`openapi-typescript` 从 `/openapi.json` 生成,CI 加 `git diff --exit-code` 漂移即失败。

### 6.6 【残余→已收口】RC-W2 后端收口清单(2026-09-06 完成 W2-1…W2-4)

| # | 项 | 状态 |
|---|----|------|
| W2-1 | worker `tasks.py` 拆包 | ✅ 完成:`services/worker/tasks/` 包。`_common`(84) / `backtests`(402) / `scans`(241) / `validation`(493) / `validation_post`(227) / `data`(20) / `__init__` 兼容层。**单文件 ≤500**;Celery 任务名、Beat、API 引用不变;测试的 `monkeypatch("services.worker.tasks.*")` 因运行时经包命名空间取依赖仍全部命中;344+ 测试通过、mypy/ruff 全绿 |
| W2-2 | quant 边界扫描锁测试 | ✅ 完成:`tests/unit/test_quant_isolation.py`(AST 扫全部 quant/*.py,禁 fastapi/celery/sqlalchemy/redis/uvicorn/starlette/services;附带 vacuous 守卫)。随 `pytest tests/unit` 进 CI |
| W2-3 | 清 ingest shim | ✅ 完成:删 `ingest_spy()`/`load_spy_parquet()`(quant/data/ingest/__init__.py);3 个测试改走通用 `ingest(symbols=["SPY"],…)`/`load_symbol_parquet`;`routers/data.py` SPY 端点改名 `ingest_single_symbol_endpoint`(仅命名清理,路由不变)。`grep ingest_spy` 代码内零命中 |
| W2-4 | SPY.parquet 解除跟踪 | ✅ 完成:`git rm --cached`;文件留盘,`.gitignore` 已盖 |
| W2-5 | OpenAPI codegen | ⏳ 未做(归 RC-W3 前端接线前,见 §6.5) |

**RC-W2 验收(截至 2026-09-06)**:`ruff` + `mypy quant services`(85 源文件)全绿;`pytest tests/unit` **346 passed**(新增边界锁 2 条);worker 无单文件 ≥500;`grep ingest_spy` 仅 git 历史命中;SPY.parquet 不再受控。

---

## 7. W3 — 前端 UI v2【部分完成;方向已锁 White Studio】

### 7.1 设计方向决策记录(覆盖原"双主题收割")

- **2026-09-05**:产品所有者明确"白色、轻盈、克制、玻璃质感"方向,MASTER.md 重写为 **White Studio 单浅色主题**(面板 `#ffffff`/画布 `#f5f6f8`、玻璃表面 74% 白 24px 模糊、圆角 12/20/24px、强调色 `#4167ac`、克制的红绿)。
- **2026-09-06 复核拍板**:锁定 White Studio 单浅色为 v1,**不再承诺正式双主题**。原 W3a"浅+深双主题收割 terminal"叙述作废;`globals.css` 里整套深色 `@media (prefers-color-scheme)` 覆盖为"尽力跟随系统",不做手动切换、不进 MASTER 承诺。旧双主题设计文件 `archive/v2.md` 已删除,git 历史即归档。
- **遗留矛盾(需一次产品收口,不阻塞后端)**:VISION 信念六写死单一主色 `#1677FF` 且反模式含"禁玻璃拟态";MASTER 现用 `#4167ac` + 玻璃质感。两处已互斥。`.cursor/rules` 已同步为 White Studio(删双主题/禁玻璃旧条文);剩 VISION 措辞与 MASTER 令牌的一次收口。

### 7.2 【残余】RC-W3 前端接缝清单

> **2026-09-06 推进**:W3-4 ✅(测试 43 → **63**,含 truth-strip 排序锁"DSR/PBO 在原始 Sharpe 前");W3-3 ✅(补 `package.json` e2e 脚本 + 按需全栈工作流 `.github/workflows/e2e.yml`,label `e2e`/手动触发,不阻塞普通 CI);另修复 W4 提交遗留的潜伏 tsc/类型债(W4 的 compare/mae-mfe 从未通过 typecheck)——`npx tsc --noEmit` 0 错、`next build` 通过,typecheck 门恢复有效。下表仅剩未做项。

| # | 项 | 现状 |
|---|----|------|
| W3-1 | ValidationRunForm 接线 | 424 行组件写好但未接入任何页面;/validation 仍 7 份旧表单 + /experiments PBO 表单。目标单一 spec 驱动表单共用 |
| W3-2 | i18n 迁移 | 字典已建;迁移 71/90 硬编码 tsx(`nav.ts` 起),目标组件零中文字面量 |
| W3-5 | 压超线组件 | `backtest-studio` 601、`strategy-lab` 548、`ValidationRunForm` 424 → ≤400 |
| W3-6 | 白 Studio 反模式收口 | VISION 措辞 vs MASTER 令牌(主色 `#1677FF` vs `#4167ac`、玻璃表述)一次对齐;深色 media query 残留清理 |

### 7.3 已完成的 W3 资产(不再重做)

硬编码 hex **0 命中**;`as-*` 色阶已映射到 CSS 变量;深色图表令牌(尽力跟随系统时用);`tailwind.config` 令牌化;`EmptyState`/`Skeleton` 加载态一致性已做;图表层 Lightweight Charts 令牌走 `lib/chart-tokens.ts`(不直传 `var(...)`)。

### 7.4 前端测试的意义(不变)

第 ② 条 E2E 仍是产品核心承诺的唯一 UI 层证据:**"未通过验证的策略在 UI 上无法被标记为 VALIDATED"**——目前只有后端 409 测试,没有 UI 层证据。

---

## 8. 后续功能路线(全部未来,顺序不变)

### 8.1 RC-W4 — Phase 4 收尾

Phase 4 特性已提前落地(09-05):跨策略 2–6 条回测曲线叠加、MAE/MFE 与持仓周期面板、`apps/web/src` 无 TODO/FIXME 残留。**收尾剩余**:

| 项 | 现状 |
|----|------|
| 对比**表**字段 | 后端 `/compare/equity` 只回 id/label/data,前端 CAGR/Sharpe/MaxDD 等列拿不到 → 多为"—"。补后端指标字段 |
| OpenAPI codegen | 归 RC-W2 W2-5 |
| Playwright E2E 进 CI | 归 RC-W3 W3-3 |
| Phase 4 关闭验收 | golden 复跑、README/状态同步、`MASTER.md`/`.cursor` 一致性复核 |

### 8.2 Phase 5 — AI Copilot(4–5 周)

**前置条件(不可跳过)**:RC-W2/RC-W3/RC-W4 全部关闭。理由不是流程洁癖——AI 会以人类无法企及的速度批量生产过拟合策略,而验证代码路径在重构中期最脆弱。

五条不可妥协约束(不变):AI 不得改风控限额 / 不得改验证状态 / 生成策略走完整验证无快速通道 / 每次试验写入试验台账 / 无真实能力不上聊天框。

可抢救设计(已记录,不实现):Copilot 的**交互形态**——右侧常驻上下文面板,感知当前页面与策略版本。最有价值功能仍是**劝用户停下来**("你已在此数据快照上试了 47 次"),试验台账已提供数字。

### 8.3 Phase 6 / 7 — Paper 与 Live

前置项(不变):风控引擎实体化(W1 已删装饰性 stub,此处从零实现单标的/杠杆/熔断/回撤/集中度/速率限额,链路 `Strategy → Risk → Execution → Broker`)、认证与多用户(D2 到期)、容器加固(任意 Python 容器内执行)、**回测–实盘对账(北极星的唯一实现方式,必做)**。

### 8.4 Phase 8 — 组合与归因

多策略相关性与组合构建(等权/风险平价/均值方差/HRP)、组合层回撤归因、**Fama-French 三/五因子 + 动量回归**、Brinson 归因。若确需列式扫描,重新引入 DuckDB(W1 删除理由为"未接线",非"不该用")。

### 8.5 贯穿性工程债

Prometheus/Sentry/OTel 可观测性(Phase 5 前,AI 批量试验让队列深度首次成问题)、Docker stdout/stderr 经 API 可读、默认口令 `street:street` 改环境变量注入(10 分钟)、CORS 与认证同清、`jobs/` 保留策略(已排 W1 §5.7 完成)。

---

## 9. 里程碑

| 里程碑 | 内容 | 累计 | 完成后的能力 |
|--------|------|------|-------------|
| N0 | W0 文档融合 | 已关(09-04) | 单一计划来源,零矛盾声明 |
| N1 | W1 垃圾清除 | 已关主体(09-05) | 仓库无合成回测数据 |
| **N2** | **RC-W2 后端残余收口(当前)** | ✅ 完成(09-06) | worker 拆包 + 边界锁 + 无 shim/漂移类型;`pytest tests/unit` 346 passed;mypy/ruff 全绿 |
| **N3** | RC-W3 前端接缝 | +~2 周 | 表单接线、codegen、i18n 迁移、E2E 进 CI、测试 43→60、超线组件归零、White Studio 收口 |
| **N4** | RC-W4 Phase 4 关闭 | +~3 周 | **Phase 4 关闭,可以开 Phase 5** |
| N5 | Phase 5 AI Copilot | +~8 周 | AI 加速研究(受闸门约束) |
| N6 | Phase 6/7 Paper+Live | +~16 周 | 研究到执行闭环 + 回测实盘对账(北极星可测) |
| N7 | Phase 8 组合归因 | +~20 周 | 多策略组合与真 alpha 判定 |

**如果只能做三件事**:RC-W2(关掉验证路径重构期的所有开放口)、RC-W3 W3-4(前端测试——唯一没有安全网的 9,000+ 行)、N6 的回测–实盘对账(唯一能验证北极星的功能)。

---

## 10. 施工纪律(.cursor/rules 需要跟随的修订)

`.cursor/rules/axiom-street.mdc` 需同步(现 L68–69 仍写"双主题 + 禁玻璃拟态",与 §7.1 冲突):

1. **禁合成数据,改为约束"存在"**:仓库内不得存在合成回测数据的模块(合成价格序列、合成指标、合成成交)。可 `grep` 检查。
2. **单一真值声明**:「当前阶段」「已交付能力」全仓库只允许在 `docs/PLAN.md` 声明一处,其余文档只许指向。
3. **UI 规则同步 White Studio**:主色 `#4167ac` 等令牌以 `MASTER.md` 为准;删"双主题"措辞;玻璃质感以 MASTER 的令牌预算为限(禁大面积强调色/发光/凭空收益);财务数字用等宽/`tabular-nums`。
4. **新增:工作包收尾同步**:每个工作包关闭时,必须把本文 §2.3 仪表盘与附录 A 更新到真实状态。开工前先读本文,不据旧记忆施工。
5. (不变)单个组件 ≤400 行;验证状态只由验证流水线改;AI 边界见 §8.2。

---

## 附录 A:量化基线(2026-09-06 复核)

| 指标 | 09-04 基线 | **09-06 实测** | 目标(Phase 4 关闭) |
|------|-----------|---------------|-------------------|
| 受版本控制文件 | 304 | **316** | 不再硬追 250(测试/i18n/E2E 资产合法新增);以"无死代码、无未接线模块"为准 |
| Python 行数(quant+services) | 14,797 | 实测为主 | RC-W2 后 ≤ 现值,worker 拆包不增行 |
| 前端行数(web/src) | 9,133 | 实测为主 | ≤400 行/组件;总行数收敛与新增测试抵消 |
| 第二前端(terminal) | 4,403 | **0** | 0 |
| Python 测试 | 349 | **346(实测;含新增 2 条边界锁)** | ≥ 现测,不允许减少 |
| 前端测试 | 18 | **63 / 11 文件** | ≥ 60 + 3 E2E(按需 workflow,不阻塞普通 CI) |
| 最大单文件(Python) | `worker/tasks.py` 1,336 | **拆包完成,无单文件 ≥500(最大 `validation.py` 493)** | ≤ 500(✅) |
| 次大单文件(Python) | `api/services/validation.py` 1,161 | **629** | ≤ 400 |
| 最大单文件(前端) | `validation-desk.tsx` 668 | **backtest-studio 601** | ≤ 400 |
| 硬编码 hex(web/src) | 34 处/12 文件 | **0** | 0 |
| 未使用 npm 依赖 | 2 | **0** | 0 |
| 死模块 | 3 | **0** | 0 |
| 计划/交接文档 | 7 份/1,390 行 | **6 份核心 + README + MASTER** | 见 §0 文档表 |
| 阶段声明来源 | 3 处矛盾 | **1 处** | 1 |
| API 端点/路由文件 | 60/9 | 实测为主 | 不变 |
| Alembic migration | 9 | 9 | 随 schema 变更 |

## 附录 B:关键文献

统计验证实现以原始文献为准,不凭记忆推导公式。

- Bailey, D. & López de Prado, M. (2014). *The Deflated Sharpe Ratio.*
- Bailey, D., Borwein, J., López de Prado, M. & Zhu, Q. (2015). *The Probability of Backtest Overfitting.*
- Bailey, D. et al. (2014). *Pseudo-Mathematics and Financial Charlatanism.*(含 Minimum Backtest Length)
- White, H. (2000). *A Reality Check for Data Snooping.*
- Hansen, P. R. (2005). *A Test for Superior Predictive Ability.*
- Politis, D. & Romano, J. (1994). *The Stationary Bootstrap.*
- Politis, D. & White, H. (2004). *Automatic Block-Length Selection.*
- López de Prado, M. (2018). *Advances in Financial Machine Learning.*(CSCV、组合构建、HRP)
