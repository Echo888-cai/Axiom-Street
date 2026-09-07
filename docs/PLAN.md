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

## 2. 现状诚实评估(2026-09-06 复核;09-07 RC-W4 收尾更新见 §2.3/§8.1/附录 A)

| 维度 | 09-04 评 | **09-06 复核** | 证据 |
|------|---------|--------------|------|
| 架构边界 | A− | **A−** | `grep` 确认 `quant/` 零 import FastAPI/Celery/SQLAlchemy/services;Controller 不碰 LEAN 内部;import 扫描锁测试已随 RC-W2 落地(§6.6 W2-2) |
| 结果真实性 | A− | **A−** | 真实 LEAN Docker + golden test 锁数字 |
| 统计验证 | A− | **A−** | 8 闸门全部落地且阻塞式;`validation-gates.md` 成文 |
| 任务编排 | B+ | **B+** | Celery + 真取消 + 超时 + 孤儿回收 + Beat |
| 工程基建 | B | **B** | 后端测试未见减少(~349);CI + nightly golden;9 个 Alembic migration |
| 指标正确性 | A− | **A−** | P0-1/2/3 已修;对账测试在 |
| 数据工程 | B+ | **B+** | 内容寻址快照、fail-closed quality、双源对账、PIT universe、增量摄取、限速 |
| **前端质量** | C+ | **C+→B−** | 令牌与测试有进步(hex 0、43 用例、E2E 规格齐),但仍有表单未接线、i18n 未迁移、E2E 未进 CI、3 个组件 >400 行。**仍是当前唯一明显落后维度** |

### 2.1 前端残余短板(审计量化)

> **09-07 复核**:下表问题已全部解决——「对比表」一行随 RC-W4 关闭(09-07,§8.1;测试 65 用例),其余随 RC-W3 关闭(§7.2):E2E 按需 workflow、单一 spec 驱动表单接线、产品源码零 CJK、组件全部 ≤400 行、codegen 混合别名换用。下表保留为 09-06 审计记录。

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
| 范围 | RC-W4 超出 §8.1 原列的收尾:golden 数字冻结在 20260827 快照,09-01 例行刷新后该快照消失(provider 追溯调整 2018–2020 历史)→ 复跑失败需处置;CI 自 09-04 起 12 次 push 全红(测试依赖本地数据 + node 20 webidl error) | 09-07 产品拍板并入本轮(处置记录见 §8.1);nightly golden 在 CI runner 上无 Docker skip-pass 记为缺口 |
| 验证判定死代码(09-07 P5-1 开工审计发现) | `services/api/services/validation_spec.py:681` `gate_check_for` 全仓无调用方(疑似死代码);实际判定来自 quant 层 `result.passed`,worker 直接写 run.passed | **只记录不修**——改判定路径属验证链高危区,不在 P5-1 代码范围;登记待后续工作包裁决 |
| 闸门口径文档漂移(09-07 P5-1 开工审计发现) | `docs/validation-gates.md:137-143` 指向 `quant/validation/pbo.py`,实际实现是 `quant/metrics/pbo.py`(文档 PBO 小节路径不符) | **只记录不修**——文档与实现口径需对照原文复核后再改文档,不在 P5-1 代码范围 |
| 路由顺序缺陷(09-07 P5-1 冒烟发现,已修复) | `routers/validation.py` 的 `GET /specs` 注册在 `GET /{run_id}` 之后 → "specs" 按 UUID 解析 422,spec 驱动表单从未真连通过(W3-1 只被 vitest mock 覆盖) | 已修复(09-07 P5-1):静态路由前移到 `/{run_id}` 之前 + 回归测试 `test_validation_specs_static_route_not_swallowed_by_run_id` |
| EB-P5 观测依赖锁不可安装(09-07 P5-1 容器重建发现,已修复) | pyproject 锁 `opentelemetry-instrumentation-* >=0.49,<1`,但该系列 `<1` 全为 prerelease(最高 0.65b0)→ pip 无 stable 可解,`Dockerfile.api` 构建必败;本地 venv 因 telemetry 导入被函数内守卫而从未暴露 | 已修复(09-07 P5-1):下限改 `>=0.49b0,<1`(预发布规范符使 pip 接受 beta;未来 stable ≥0.49 出现时自动优先 stable);api 容器重建成功 |
| provider 拍板变更(09-07 P5-2 开工,用户拍板) | P5-1 收尾叙述 "P5-2 接 Anthropic 直连" 为 09-07 早先拍板;P5-2 开工用户拍板:**模型用 DeepSeek,不用 Anthropic**(档位 `deepseek-v4-flash`;DeepSeek 官方 OpenAI 兼容接口 `api.deepseek.com`,官方文档推荐 openai SDK 客户端,旧模型名 deepseek-chat/reasoner 已于 2026-07-24 停用) | 已按新决定实施,本文所有 "P5-2 Anthropic 劝停" 措辞同步为 "P5-2 模型劝停(DeepSeek)";P5-1 行保留为历史记录并加指针 |

### 2.3 执行状态仪表盘(审计后)

| 包 | 状态 | 一句话 |
|----|------|--------|
| **W0** 文档融合 | ✅ 已关闭(09-04) | ROADMAP 删除;`validation-gates.md` 落地;阶段单一声明 |
| **W1** 垃圾清除 | ✅ 主体已关闭(09-05) | terminal/risk/packages/duckdb 删除;无合成回测模块;两处残余(ingest shim、SPY.parquet 跟踪)已随 RC-W2 收口(§6.6) |
| **W2** 架构整理 | ✅ 后端主体(09-06)+ 残余 W2-1…4 已收口;W2-5 codegen 转 RC-W3 | `ValidationSpec` 注册表 + `GET /specs`;`validation.py` 1161→629;worker 拆包完成,单文件 ≤500;quant 边界锁测试在;测试 346 全绿 |
| **W3** 前端 UI v2 | ✅ 已关闭主体(09-07);方向已锁 White Studio | **W3-1…W3-5 ✅、W2-5 基建 ✅、W3-2 组件迁移 ✅**(产品 tsx 零 CJK,zh/en +600 键);**W3-6 codegen 换用 ✅**(09-07 混合别名方案,§7.2);tsc 0 · vitest 63 · build ✓ |
| **W4** Phase 4 收尾 | ✅ 已关闭(09-07) | compare/equity 契约修复(GET-only + series 内嵌 7-key metrics)、对比表全列真值、面板死控件删除;golden re-freeze 到 20260831 快照;CI 修复并入;pytest 349 · vitest 65/12(记录 §8.1) |
| **EB-P5** Phase 5 前置工程债 | ✅ 已关闭(09-07) | 可观测性接入(OTel→Jaeger 单 tracer + API /metrics 聚合队列/心跳 + Sentry 错误门控)、默认口令 env 注入、CORS 收紧同源(不加认证);docker-logs/prune 核对为已落地;pytest 354 · golden 2 · vitest 65(记录 §8.5) |
| **P5-1** Copilot 底座 | ✅ 已关闭(09-07,当日开工关闭) | Phase 5 首个工作包(§8.2):AI 写路径隔离锁 4 条 + `GET /copilot/context` 只读聚合 + provider 骨架(noop,未知名 fail loud)+ 全局右栏确定性事实面板(试验/闸门/dup/supersede,诚实空态)。产品拍板(09-07):底座先行、P5-2 接 Anthropic 直连(provider 于 P5-2 开工改 DeepSeek,§2.2)、出站仅聚合统计、面板全局窄栏。无 LLM 调用、无聊天框、无写端点、无新表。pytest **370**(354+15+1 路由回归)· golden 2 · vitest 73/14 · tsc 0 · build ✓ · 真实栈 chromium 核查。另修两处潜伏缺陷:GET /validation/specs 被 /{run_id} 吞掉 422(前移+回归测试)、EB-P5 观测依赖锁在 3.11 不可安装(pyproject 改 0.49b0 下限)——记录见 §2.2 |
| **P5-2** 模型劝停 | ✅ 已关闭(09-07,当日开工关闭) | Phase 5 第二包(§8.2):**DeepSeek 直连**(09-07 用户拍板不用 Anthropic,§2.2)worker synthesize 任务(`copilot.synthesize`,超时 60s/重试 2,单行单提交落 `copilot_insights` 新表,alembic 9→10)+ API 只 enqueue(`POST /copilot/synthesize`,202/404/503;`GET /copilot/insights` 按策略倒序)+ **仅聚合统计**出站(`STREET_DEEPSEEK_API_KEY` 无 key 即关闭;默认模型 `deepseek-v4-flash`;官方 OpenAI 兼容接口+openai SDK 客户端,新增依赖 1)+ 面板「Copilot 评估」块(手动触发、轮询至新行、DONE/FAILED/禁用诚实态、隐私行)。隔离锁修订:copilot 禁一切写面,**仅放开 worker 任务 `_record_insight` 写自身台账**(AST 锁)。无聊天框、无自动触发。pytest **387**(+17)· vitest **78/15**(+5)· 真实栈 chromium 4/4 · console 零错误 |
| **P5-3** 建议动作 | ✅ 已关闭(09-07,当日开工关闭) | Phase 5 第三包(§8.2,用户拍板:**纪律+补闸门动作、卡内确认即执行、确定式候选为真值 + LLM 只在候选内挑优先级**)。确定性候选推导 `suggestions.py`(专扫 copilot 源外,读版本 code 判扫描类可执行性)+ `GET /copilot/suggestions` 每次现算 + `POST /copilot/suggest` enqueue-only + worker `copilot.suggest`(模型 JSON 候选内 pick,候选外一律拒,落 `copilot_suggestions` 新表,alembic 10→11)+ `GET /copilot/suggestions/recommendation` + 面板「建议动作」块(确定式卡恒显示、guide/discipline 信息行、采纳→确认框→现有 `POST /validation`,provider 启用时「让 Copilot 排序」)。出站边界不变:模型只见候选元数据,永不见源码/参数值/行情。隔离锁扩为 `_record_insight`/`_record_suggestion` 双豁免 + suggestions 模块只读锁(卡片键白名单)。pytest **421**(387+34:推导 11 + suggest 14 + provider suggest 6 + 隔离锁 3)· vitest **85/16**(+7)· tsc 0 · lint 0(1 既有 warning)· build ✓ · codegen 幂等 |

---

## 3. 执行总览(RC-W2/3/4、EB-P5、P5-1、P5-2 与 P5-3 已关闭;下一包 P5-4 聊天框形态待评估)

顺序即依赖:**先关后端残余 → 再接前端接缝 → 再 W4 收尾验收 → Phase 4 关闭 → EB-P5 工程债 → Phase 5**。任何一步都不得越过验证闸门测试与对应 Phase 边界。EB-P5 于 09-07 关闭,Phase 5 前置门槛已清。

| 包 | 内容 | 依赖 | 为什么在这个位置 |
|----|------|------|----------------|
| **RC-W2** | 后端残余收口:worker 拆包、quant 边界锁、清 ingest shim、SPY untrack | ✅ 已关闭(2026-09-06) | W2-1…4 完成;W2-5 OpenAPI codegen 转 RC-W3 前端接线前 |
| **RC-W3** | 前端接缝:ValidationRunForm 接线、i18n 迁移、E2E 进 CI、测试 43→60、压超线组件、White Studio 收口、OpenAPI codegen 换用 | ✅ 已关闭(2026-09-07) | W3 六项全部收口;对比表字段与 compare/equity 契约漂移交 RC-W4(§8.1) |
| **RC-W4** | Phase 4 收尾验收:对比表补字段、compare/equity 契约漂移修复、golden、README/状态同步、关闭 Phase 4(§8.1) | ✅ 已关闭(2026-09-07) | 收尾项少但必须在 Phase 5 之前关闭;golden re-freeze 与 CI 修复经拍板并入(§8.1) |
| **EB-P5** | Phase 5 前置工程债(§8.5,开 Phase 5 的门槛):可观测性 **OTel→Jaeger**(单 tracer)+ **/metrics 聚合** + **Sentry 错误门控**、默认口令 env 注入、CORS 收紧同源 | ✅ 已关闭(2026-09-07)。深度/出口产品拍板:全栈 + 本地自托管 Jaeger;CORS 按长期最优收紧、**不加认证**(D2 维持) | Phase 5 门槛已清,无前置依赖;下一包 N5 Phase 5(§8.2) |
| **P5-1** | Copilot 底座(§8.2,09-07 产品拍板):AI 写路径隔离锁 + 只读上下文 API + provider 骨架(noop)+ 全局右栏确定性事实面板 | ✅ 已关闭(2026-09-07) | Phase 5 首个工作包;无 LLM、无聊天、无写端点;下一包 P5-2 模型劝停(DeepSeek,§2.2) |
| **P5-2** | 模型劝停(§8.2,09-07 用户拍板 DeepSeek):DeepSeek synthesize 任务(超时/重试)+ API 只 enqueue + 仅聚合统计出站 + 劝停叙述块(手动触发,落 `copilot_insights` 新表) | ✅ 已关闭(2026-09-07) | Phase 5 第二包;仍无聊天框、无自动触发、无写面;出站上下文永不包含策略源码/参数 config/价格序列;下一包 P5-3 建议动作(§8.2) |
| **P5-3** | 建议动作人审闭环(§8.2,09-07 用户拍板:纪律+补闸门动作、卡内确认即执行、确定式候选为真值 + LLM 只在候选内挑优先级写理由) | ✅ 已关闭(2026-09-07) | Phase 5 第三包;确定式候选每次现算(无候选表),模型 pick 落 `copilot_suggestions`;出站边界不变、无自动执行、无策略生成;下一包 P5-4 聊天框形态(待评估) |

**Phase 4 与 EB-P5 均已关闭。** EB-P5 = §8.5 前置工程债清理,2026-09-07 开工当日关闭。开工审计把桶内两项从待办改判为**已落地**(`GET /backtests/{id}/logs` 读 docker stdout/stderr、`prune_jobs.py`);本轮交付三项:① 可观测性——`services/telemetry.py` 集中门控 SDK,OTel 为唯一 tracer(OTLP→本地 Jaeger,compose 新增 jaeger+prometheus 服务),API `/metrics` 聚合 HTTP 计数/延迟 + Celery 队列深度 + worker 心跳年龄,Prometheus 抓单 target,worker 不另起导出端口(Celery prefork 会抢端口);Sentry 仅错误、无 DSN 即 no-op,500 handler 接 capture;② 默认口令——compose/alembic/settings 三层去除 `street:street` 明文默认,`STREET_DATABASE_URL` 必填、`.env.example` 给 `openssl rand` 指引、e2e 显式传凭据;③ CORS 收紧——origins 仅 `http://localhost:3000`(删死 3001)、`allow_credentials=False`、方法最小化,浏览器同源代理零感知。nightly golden 的 CI skip-pass 缺口维持为已知缺口,自托管 runner 不排(§8.6)。验证:ruff/mypy 全绿;pytest tests/unit **354**(+5 观测测试);golden 2 passed(1 skip:缺 Polygon key);前端 tsc 0 · vitest 65;真实 Jaeger OTLP 收 span 冒烟通过。

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
| W2-5 | OpenAPI codegen | ✅ 基建已做(离线 openapi.json 基线 + `api-types.gen.ts` + CI 漂移门);整体替换手工类型归 W3-6,谨慎分批 |

**RC-W2 验收(截至 2026-09-06)**:`ruff` + `mypy quant services`(85 源文件)全绿;`pytest tests/unit` **346 passed**(新增边界锁 2 条);worker 无单文件 ≥500;`grep ingest_spy` 仅 git 历史命中;SPY.parquet 不再受控。

---

## 7. W3 — 前端 UI v2【部分完成;方向已锁 White Studio】

### 7.1 设计方向决策记录(覆盖原"双主题收割")

- **2026-09-05**:产品所有者明确"白色、轻盈、克制、玻璃质感"方向,MASTER.md 重写为 **White Studio 单浅色主题**(面板 `#ffffff`/画布 `#f5f6f8`、玻璃表面 74% 白 24px 模糊、圆角 12/20/24px、强调色 `#4167ac`、克制的红绿)。
- **2026-09-06 复核拍板**:锁定 White Studio 单浅色为 v1,**不再承诺正式双主题**。原 W3a"浅+深双主题收割 terminal"叙述作废;`globals.css` 里整套深色 `@media (prefers-color-scheme)` 覆盖为"尽力跟随系统",不做手动切换、不进 MASTER 承诺。旧双主题设计文件 `archive/v2.md` 已删除,git 历史即归档。
- **产品收口(2026-09-06 拍板,已解决)**:设计实现真值以 White Studio `MASTER.md` 为准(主色 `#4167ac`,玻璃质感仅限其令牌预算内面板);VISION 信念六措辞已同步(不再写死 `#1677FF`,玻璃以 MASTER 为限)。`.cursor/rules` 早已对齐。

### 7.2 【残余】RC-W3 前端接缝清单

> **2026-09-06 推进**:✅ **W3-1**(/validation 与 /experiments 收敛到单一 spec 驱动表单,删 7 个旧表单);✅ **W3-5**(ValidationRunForm 424→282、strategy-lab 548→381、backtest-studio 601→316,**全部 ≤400 行**);✅ **W3-4**(测试 43→**63**,含 truth-strip 排序锁);✅ **W3-3**(e2e 脚本 + 按需全栈 workflow,label `e2e`/手动,不阻塞普通 CI);✅ **W2-5 基建**(离线导出 openapi.json 基线、`api-types.gen.ts` 生成、CI 漂移门);✅ **W3-2 组件迁移**(字典按域拆 `zh/en/{11 域}.ts`,四簇并行迁移,**产品 tsx 组件零 CJK**,zh/en 各 +600 余键)。另修复 W4 提交遗留的潜伏 tsc/类型债。验证:tsc 0 · vitest 63 · next build ✓。下表为剩余收尾项。
>
> **2026-09-07 W3-6 收尾**:开工审计发现「整体替换 types.ts」不净(裸 dict/匿名响应、~60 读点报错、compare/equity 漂移),拍板范围见 W3-6 行;实现完成,RC-W3 关闭。

| # | 项 | 现状 |
|---|----|------|
| W3-2 | i18n 收尾 | ✅ 完成:**产品源码(tsx+ts)零 CJK**(组件并行迁移 + 10 个 .ts 集中库经 `tr()` 查字典;方向判定改语义 `isSellTrade`,消除文本耦合);仅 e2e 测试含中文(不计产品)。新增同步读取器 `lib/translate.ts` |
| W3-6 | codegen 换用 | ✅ 完成(2026-09-07)。开工前审计确认「整体替换」不干净:OpenAPI 对 error/rules/result/data 等字段是裸 dict,且 data/status、snapshots、ingest job、compare equity、constituents、sync-delistings 六个响应在 spec 里是匿名对象——整替丢精度、~60 读点报错;产品所有者拍板 **前端混合别名校验** 范围(不动后端)。落地:`lib/api/types.ts` 改写为**契约别名层**——18 个 spec 已建模形状直接别名 `api-types.gen.ts`(CI 漂移门唯一真值);4 个窄化读模型(`Backtest`/`ValidationRun`/`Universe`/`TrialStats` + `ValidationGates`,Omit 裸 dict 字段后按后端真实写入键收窄);spec 完全未建模域(DataStatus/IngestJob/DataSnapshot/CompareEquityResponse/Page)保留本地读模型并在文件尾加 30+ 行结构断言(别名 ⊆ schema、Page ⊆ XxxPage、匿名响应端点 pin),断言随 `tsc --noEmit`/CI 执行。消费侧按 spec 真实可选性补空安全(~100 读点 `?? {}`/`?.`,顺带修掉 FAILED run 读 `result` 的潜在空指针)。tsc 0 · vitest 63 · build ✓。**残余**:请求体/query 参数仍未 ops 级接线——与 RC-W4 的 compareEquity 修复合并成「请求层批」(§8.1) |

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
| compare/equity 契约漂移 + 对比表字段 | ✅ 已完成(09-07)。审计:前端 POST body {ids,normalized,period} vs 后端 GET-only(query ids/normalized)→ 405 级漂移、零测试、面板不可用;响应无 metrics → 表列恒"—"。处置:① 前端改 GET,ids/normalized 从 gen operations 接线(spec-wired query 类型;请求层批仅此漂移闭环,其余 23 个 requestBody ops 有意不做,不再安排);② 后端 `compare_equity` 移到 router 顶部静态段(GET-only),每条 series 内嵌 7-key metrics(final_equity/total_return/cagr/sharpe/max_drawdown/volatility/trade_count),表列全走后端真值;③ 删死控件 period 选择器与重复的 normalized 复选框(保留单一 normalized 开关,GET 支持)。验证:后端 compare 3 单测、前端 2 vitest(真值格式、metrics=null 兜底"—"、两选才发查询)、真实 chromium 核查通过 |
| golden 复跑(Phase 4 关闭验收) | ✅ 已完成(09-07):复跑失败根因 = 数据快照轮转(09-01 例行刷新后 20260827 快照消失,provider 追溯调整 2018–2020 历史:24→28 笔、净收益 +3.98%→+0.09%;SPY 现货抽查为真,非回归)→ **拍板重新冻结** `expectations.json` 到 20260831-1209a3(snapshot sha 锁定;golden 2 passed),同步 `test_validation_pipeline` 属性锁。golden 绑定 snapshot sha 的设计即预期快照轮转时 re-freeze |
| CI 修复包(拍板并入本轮) | ✅ 已完成(09-07):CI 自 09-04 起 12 次 push 全红 → ① research-notes 测试改 ORM direct-seed(CI runner 无市场数据,`data/` 被 gitignore),空 `STREET_DATA_ROOT` 下验证通过;② ci.yml web job node 20→22(jsdom/undici webidl error)。**残余缺口**:nightly golden 在 GitHub runner 上无 Docker → skip-pass 无真锁;自托管 runner 不排(转 §8.6 后续) |
| README/状态同步 + MASTER/.cursor 复核 | ✅ 已完成(09-07):README 阶段行与免责条款更新;.cursor 的 Phase 5 gate 规则无冲突(§10 条目未变);MASTER 令牌预算无变化 |

### 8.2 Phase 5 — AI Copilot(4–5 周)

**前置条件(不可跳过)**:RC-W2/RC-W3/RC-W4 全部关闭。理由不是流程洁癖——AI 会以人类无法企及的速度批量生产过拟合策略,而验证代码路径在重构中期最脆弱。

五条不可妥协约束(不变):AI 不得改风控限额 / 不得改验证状态 / 生成策略走完整验证无快速通道 / 每次试验写入试验台账 / 无真实能力不上聊天框。

**工作包分解(2026-09-07 P5-1 开工拍板登记)**:

| 包 | 内容 | 边界 |
|----|------|------|
| **P5-1** 底座 | ✅ 已关闭(09-07) | AI 写路径代码级隔离(锁测试 4 条)+ 只读上下文 API(`GET /copilot/context`)+ provider 适配器骨架(noop,env 门控,未知名 fail loud)+ 全局右栏确定性事实面板(试验计数/闸门/重复参数/快照 supersede,诚实空态)。无 LLM 调用、无聊天框、无写端点、无新表 |
| P5-2 模型劝停 | ✅ 已关闭(09-07,当日开工关闭) | **DeepSeek**(09-07 用户拍板,不用 Anthropic,§2.2):worker synthesize 任务(超时 60s/重试 2,API 只 enqueue)+ **仅聚合统计**出站组装(OpenAI 兼容接口 `api.deepseek.com`,官方推荐 openai SDK 客户端,新增依赖 1;`STREET_DEEPSEEK_API_KEY` 后端 env,无 key 即关闭;默认模型 `deepseek-v4-flash`,`STREET_COPILOT_MODEL` 可覆盖)+ 劝停叙述块(面板手动触发、轮询、诚实态)。叙述落新表 `copilot_insights`(alembic 9→10,worker 单行单提交);隔离锁修订:copilot 源码仍禁 import 写面/ORM 写,仅放开 worker 任务单函数 `_record_insight` 写自身台账表(锁测试细化 5 条);发给 provider 的上下文永不包含策略源码/参数 config/价格序列(列级锁扩至 worker 任务文件)。下一包 P5-3 建议动作(人审闭环,无自动执行) |
| P5-3 建议动作人审闭环 | ✅ 已关闭(09-07,当日开工关闭) | 用户拍板:**纪律+补闸门动作**(不做数值参数建议)、**卡内确认即执行**、**确定式候选为可执行真值 + LLM 只在候选内挑优先级写理由**。确定式推导 `services/api/services/suggestions.py`(放 copilot 包**外**:需读 `StrategyVersion.code` 判 PBO/SENSITIVITY/COST 可执行性——扫描目录内禁止;只读锁 + 卡片键白名单测试承重)+ `GET /copilot/suggestions`(每次现算,候选无表)+ `POST /copilot/suggest`(enqueue-only,镜像 synthesize 的 202/404/503)+ worker `copilot.suggest`(JSON 回复,fence/越界/超长一律拒,落 `copilot_suggestions` 新表,alembic 10→11)+ `GET /copilot/suggestions/recommendation` + 面板「建议动作」块(确定式卡恒显示、卡内确认即调现有 `POST /validation`,kind/version/backtest/spec 默认网格载荷;guide/discipline 信息行不可执行;provider 启用时「让 Copilot 排序」轮询回流)。出站边界**不变**:模型只见候选元数据(key/action/kind/version),永不见源码/参数值/行情;隔离锁扩为 `_record_insight`+`_record_suggestion` 双豁免(worker 写仍只在这两个 helper)+ suggestions 模块只读锁。无自动执行、无策略生成、无聊天框。下一包 P5-4 聊天框形态(待评估,约束五) |
| P5-4 聊天框形态 | 仅在 P5-2/3 真实能力落地后才评估(约束五) | — |

可抢救设计(已记录,P5-2 起逐步实现):Copilot 的**交互形态**——右侧常驻上下文面板(P5-1 先落确定性事实层),感知当前页面与策略版本。最有价值功能仍是**劝用户停下来**("你已在此数据快照上试了 47 次"),试验台账已提供数字。

### 8.3 Phase 6 / 7 — Paper 与 Live

前置项(不变):风控引擎实体化(W1 已删装饰性 stub,此处从零实现单标的/杠杆/熔断/回撤/集中度/速率限额,链路 `Strategy → Risk → Execution → Broker`)、认证与多用户(D2 到期)、容器加固(任意 Python 容器内执行)、**回测–实盘对账(北极星的唯一实现方式,必做)**。

### 8.4 Phase 8 — 组合与归因

多策略相关性与组合构建(等权/风险平价/均值方差/HRP)、组合层回撤归因、**Fama-French 三/五因子 + 动量回归**、Brinson 归因。若确需列式扫描,重新引入 DuckDB(W1 删除理由为"未接线",非"不该用")。

### 8.5 贯穿性工程债(EB-P5,2026-09-07 已关闭)

> **2026-09-07 开工并当日关闭**(记录见 §3)。可观测性出口产品拍板**本地自托管 Jaeger**(OTel 单 tracer、不开 sentry tracing 免双埋点);CORS 按长期最优收紧、**不加认证**(D2 维持——认证随 Phase 6/7 容器加固整体做)。

| 项 | 状态 |
|----|------|
| Docker stdout/stderr 经 API 可读 | ✅ 已落地:`quant/engine/lean.py` Popen 抓 stdout/stderr 写 `jobs/<id>/docker_stdout.log`/`docker_stderr.log`,`GET /backtests/{id}/logs` 回读(services/api/services/backtests.py `get_logs`) |
| `jobs/` 保留策略 | ✅ 已落地:`services/api/prune_jobs.py` + Makefile `prune-jobs` |
| 可观测性(Phase 5 前,AI 批量试验让队列深度首次成问题) | ✅ 已落地:新增 `services/telemetry.py`(settings 门控、幂等);OTel SDK + fastapi/sqlalchemy/celery/httpx 埋点,OTLP→Jaeger;API `/metrics` 聚合 HTTP 计数/延迟 + `axiom_celery_queue_depth` + `axiom_worker_heartbeat_age_seconds`(scrape 时读 Redis broker/worker 心跳,worker 不另起端口);compose 新增 jaeger(`all-in-one:1.57`,OTLP 4317/4318,UI 16686)+ prometheus(抓 api:8000/metrics,UI 9090);Sentry 错误-only(`STREET_SENTRY_DSN` 空即 no-op),500 handler + celery 接错误。测试 `tests/unit/test_observability.py` 5 条(/metrics 200 空、enabled 含 axiom_ 系列、OTel/Sentry no-op、空 URL 拒绝、CORS 单 origin)。真实 Jaeger OTLP 收 span 冒烟通过 |
| 默认口令 `street:street` 改环境变量注入 | ✅ 已落地:compose 三层 `:?` 必填(`POSTGRES_*`/DB URL)、`alembic.ini`/`settings.database_url` 去明文默认(`STREET_DATABASE_URL` 必填,空值拒绝)、`.env.example` 给 `openssl rand -hex 16` 指引;e2e 显式传凭据;`git grep street:street` 仅剩说明性注释 |
| CORS 与认证同清 | ✅ 已落地:CORS origins 仅 `http://localhost:3000`(删死 3001)、`allow_credentials=False`、方法最小化;浏览器同源代理(3000→/api/backend)零感知;不加认证 |

### 8.6 贯穿性工程债(后续,非 EB-P5 范围)

nightly golden 的 CI skip-pass 缺口(§8.1):GitHub runner 无 Docker → 维持已知缺口,自托管 runner 不排。Phase 5 前置门槛以 §8.5 EB-P5 为界,不含此项。

---

## 9. 里程碑

| 里程碑 | 内容 | 累计 | 完成后的能力 |
|--------|------|------|-------------|
| N0 | W0 文档融合 | 已关(09-04) | 单一计划来源,零矛盾声明 |
| N1 | W1 垃圾清除 | 已关主体(09-05) | 仓库无合成回测数据 |
| **N2** | **RC-W2 后端残余收口** | ✅ 完成(09-06) | worker 拆包 + 边界锁 + 无 shim/漂移类型;`pytest tests/unit` 346 passed;mypy/ruff 全绿 |
| **N3** | RC-W3 前端接缝 | ✅ 已关闭(09-07) | 表单接线、codegen 混合别名、i18n 零 CJK、测试 63、E2E 按需、组件 ≤400 |
| **N4** | RC-W4 Phase 4 关闭 | ✅ 已关闭(2026-09-07) | compare/equity 契约修复 + 对比表真值 + golden re-freeze + CI 修复;Phase 4 关闭 |
| **EB-P5** | Phase 5 前置工程债 | ✅ 已关闭(2026-09-07) | §8.5 全栈可观测性(OTel→Jaeger + /metrics + Sentry 错误门控)+ 默认口令注入 + CORS 收紧;Phase 5 门槛已清,下一里程碑 N5 |
| N5 | Phase 5 AI Copilot(§8.2:P5-1 底座 → P5-2 模型劝停(DeepSeek)→ P5-3 建议动作 → P5-4 聊天框待议) | P5-1 ✅ 已关闭(09-07);P5-2 ✅ 已关闭(09-07);P5-3 ✅ 已关闭(09-07);下一包 P5-4 聊天框形态(待评估) | AI 加速研究(受闸门约束) |
| N6 | Phase 6/7 Paper+Live | +~16 周 | 研究到执行闭环 + 回测实盘对账(北极星可测) |
| N7 | Phase 8 组合归因 | +~20 周 | 多策略组合与真 alpha 判定 |

**如果只能做三件事**(09-07 随 EB-P5 关闭修订):① ~~Phase 5 前置工程债~~ —— **EB-P5 已关闭(09-07)**,Phase 5 门槛已清(nightly golden 的 CI 缺口为 §8.6 已知项);② **N5 Phase 5 AI Copilot**(受 §8.2 约束)——**P5-1 底座、P5-2 模型劝停(DeepSeek)与 P5-3 建议动作人审闭环均已关闭(09-07)**,下一包 P5-4 聊天框形态(待评估,约束五);③ N6 的回测–实盘对账(唯一能验证北极星的功能)。

---

## 10. 施工纪律(.cursor/rules 应长期体现,逐包同步)

`.cursor/rules/axiom-street.mdc`(`alwaysApply: true`,不是文档,单独维护)必须长期体现以下条目,并在**每个工作包关闭时同步其 `Current scope` 相位指针**。2026-09-07 审计:UI(White Studio 单浅色)、禁合成数据、单一真值三条目已在文件中落地;但 **`Current scope` 未随 P5-1/P5-2 关闭翻页**(仍写 "P5-1 in progress / 未开 P5-2(Anthropic)"),与 §2.3 冲突——已同步为 **P5-3 待开工**,并于 P5-3 当日关闭时再次翻至 **P5-4 待评估**。条目与落地状态:

1. **禁合成数据,改为约束"存在"**:仓库内不得存在合成回测数据的模块(合成价格序列、合成指标、合成成交)。可 `grep` 检查。→ ✅ 已落地
2. **单一真值声明**:「当前阶段」「已交付能力」全仓库只允许在 `docs/PLAN.md` 声明一处;`.cursor/rules` 的 `Current scope` 只保留最小相位指针并指向本文 §2.3/§8.2,不自行复述状态表。→ ✅ 已落地(本次同步遵循)
3. **UI 规则同步 White Studio**:主色 `#4167ac` 等令牌以 `MASTER.md` 为准;"双主题"措辞已删(原 §10 L68–69 冲突已随 RC-W3/§7.1 拍板消解);玻璃质感以 MASTER 的令牌预算为限(禁大面积强调色/发光/凭空收益);财务数字用等宽/`tabular-nums`。→ ✅ 已落地
4. **工作包收尾同步(新增强化)**:每个工作包关闭时,必须:① 把本文 §2.3 仪表盘与附录 A 更新到真实状态;② 同步 `.cursor/rules` 的 `Current scope` 相位指针(开工登记翻至新包、关闭翻至下一包);③ `grep` 复查本文与 .cursor 无残留指向已关闭包的旧措辞。开工前先读本文,不据旧记忆施工。
5. (不变)单个组件 ≤400 行;验证状态只由验证流水线改;AI 边界见 §8.2。→ ✅ 已在 `.cursor/rules` Every PR / AI boundaries 节体现

---

## 附录 A:量化基线(2026-09-06 复核)

| 指标 | 09-04 基线 | **09-06 实测** | 目标(Phase 4 关闭) |
|------|-----------|---------------|-------------------|
| 受版本控制文件 | 304 | **316** | 不再硬追 250(测试/i18n/E2E 资产合法新增);以"无死代码、无未接线模块"为准 |
| Python 行数(quant+services) | 14,797 | 实测为主 | RC-W2 后 ≤ 现值,worker 拆包不增行 |
| 前端行数(web/src) | 9,133 | 实测为主 | ≤400 行/组件;总行数收敛与新增测试抵消 |
| 第二前端(terminal) | 4,403 | **0** | 0 |
| Python 测试 | 349 | **421(09-07 P5-3 收尾实测;387 + 34:推导 11 + suggest 14 + provider suggest 6 + 隔离锁细化 3)** | ≥ 现测,不允许减少 |
| 前端测试 | 18 | **85 / 16 文件(09-07 P5-3 收尾实测)** | ≥ 60 + 3 E2E(按需 workflow,不阻塞普通 CI) |
| 最大单文件(Python) | `worker/tasks.py` 1,336 | **拆包完成,无单文件 ≥500(最大 `validation.py` 493)** | ≤ 500(✅) |
| 次大单文件(Python) | `api/services/validation.py` 1,161 | **629** | ≤ 400 |
| 最大单文件(前端) | `validation-desk.tsx` 668 | **backtest-studio 601** | ≤ 400 |
| 硬编码 hex(web/src) | 34 处/12 文件 | **0** | 0 |
| 未使用 npm 依赖 | 2 | **0** | 0 |
| 死模块 | 3 | **0** | 0 |
| 计划/交接文档 | 7 份/1,390 行 | **6 份核心 + README + MASTER** | 见 §0 文档表 |
| 阶段声明来源 | 3 处矛盾 | **1 处** | 1 |
| API 端点/路由文件 | 60/9 | **65/9(09-07 P5-3:+GET /copilot/suggestions、GET /copilot/suggestions/recommendation、POST /copilot/suggest)** | 不变 |
| Alembic migration | 9 | **11(09-07 P5-3:+0011_copilot_suggestions)** | 随 schema 变更 |

**09-07 RC-W4 收尾实测**:后端 `pytest tests/unit` 349 全绿(ruff/mypy 同绿);前端 tsc 0 · vitest 65/12 · lint 0 · `next build` ✓;golden 2 passed(1 skipped:CI runner 无 Docker,见 §8.1);`codegen:types` 幂等;真实栈 chromium 核查对比面板通过。净值/属性锁数字冻结在 20260831 数据快照(re-freeze 记录见 §8.1)。

**09-07 EB-P5 收尾实测(同日开工关闭)**:后端 `pytest tests/unit` **354** 全绿(349 + 5 条 `tests/unit/test_observability.py`;ruff/mypy 全绿 86 源文件);golden 2 passed(1 skip:缺 Polygon key,非本包);前端 tsc 0 · vitest 65/12(无回归);真实 Jaeger(`all-in-one:1.57`)OTLP 收 `axiom-api` span 冒烟通过、compose 解析 7 服务、缺 POSTGRES_* 时 fail-fast;`git grep "street:street"` 仅剩说明性注释(无凭据字面量)。API 端点 +1(`GET /metrics`);新增依赖 9(prometheus-client/opentelemetry-* /sentry-sdk,见 pyproject)。

**09-07 P5-1 收尾实测(同日开工关闭)**:后端 `pytest tests/unit` **370** 全绿(354 + 15 copilot + 1 specs 路由回归;ruff/mypy 全绿 90 源文件);golden 2 passed(1 skip:缺 Polygon key);前端 tsc 0 · vitest **73/14**(+8:copilot 面板 3 + scope 5)· lint 0 · `next build` ✓;codegen 幂等(`codegen:types` 后 `git diff --exit-code` 无新变化);真实栈 api/web 容器重建后 chromium 核查:右栏在策略详情页渲染试验台账(按快照计数/重复参数/已取代徽标)与闸门结果、`/validation` 列表页诚实空态、console 零错误、窄屏(<1280px)右栏隐藏;`GET /copilot/context` curl 200/404/422 各验一次。API 端点 +1(`GET /copilot/context`);新增文件 13(copilot 后端 5 + 测试 3 + 前端面板 7 + locales 2,见各提交)。

**09-07 P5-2 收尾实测(同日开工关闭)**:后端 `pytest tests/unit` **387** 全绿(370 + 17:copilot synthesize 9 + providers 净 +7 + 隔离锁细化 +1;ruff/mypy 全绿 93 源文件,含 openai SDK 类型);golden 2 passed + 1 skip(缺 Polygon key,非本包);前端 tsc 0 · vitest **78/15**(+5:copilot-insight 块)· lint 0(1 条既有 warning 非本包)· `next build` ✓;codegen 幂等(`codegen:types` 重跑 `git diff` 无新变化)。真实栈容器重建后(openai 依赖在 py3.11 镜像可安装):api 启动 alembic `0009 → 0010` 落真实 PG、worker 注册 `copilot.synthesize` 任务;curl:策略存在时 `POST /copilot/synthesize` **503**(无 key 即关闭,诚实文案)、未知 id 404、`GET /copilot/insights` 200 空数组、`GET /copilot/context` provider 事实 = deepseek/disabled;chromium 4/4:右栏「Copilot 评估」禁用诚实态 + 隐私边界行 + console 零错误(启用态交互由 5 条 vitest 覆盖——无 key 不出站是设计,非可绕过路径)。API 端点 +2;新表 1(`copilot_insights`)+ migration 0010;新增依赖 1(openai);新增文件:后端 prompts/insights/tasks-copilot/0010/合成测试 等、前端 copilot-insight.tsx(+测试)、compose/.env.example key 映射(见各提交)。

**09-07 P5-3 收尾实测(同日开工关闭)**:后端 `pytest tests/unit` **421** 全绿(387 + 34:推导 11 + suggest 14 + provider suggest 6 + 隔离锁细化 3;ruff/mypy 全绿);golden 2 passed + 1 skip(缺 Polygon key,非本包);前端 tsc 0 · vitest **85/16**(+7:actions-block)· lint 0(1 条既有 warning 非本包)· `next build` ✓;codegen 幂等(`codegen:types` 重跑 `git diff` 无新变化,openapi.json 基线含 3 个新 copilot 路径)。确定式候选推导 `services/api/services/suggestions.py` 单测覆盖规则全分支(缺失/已过/inflight/不可执行/无回测 guide/纪律/archived/最新版本作用域/键白名单);worker `execute_suggest` 落库 DONE/FAILED(候选外 pick 拒绝)与 API 202/404/503/guide 卡各验一次;面板 actions-block 7 条 vitest(卡渲染、采纳载荷、guide/discipline 无采纳、provider 禁用隐藏排序、模型 DONE/FAILED 回流)。真实栈容器级 chromium 未在本会话复跑(需 docker 全栈),UI 行为由 vitest 覆盖。API 端点 +3;新表 1(`copilot_suggestions`)+ migration 0011;无新依赖;新增文件:后端 suggestions/0011/suggest 任务与测试、前端 actions-block(+测试)与 locales,见各提交。

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
