<p align="center">
  <img src="apps/web/public/axiom-mark.svg" alt="Axiom Street" width="88" height="88" />
</p>

<h1 align="center">Axiom Street</h1>

<p align="center">
  <strong>Research, with evidence.</strong><br />
  从假设出发，让证据说话。
</p>

<p align="center">
  为严肃研究而设计的量化工作台。<br />
  让想法成为规则，让实验留下证据，让每一步决策都有依据。
</p>

<p align="center">
  <a href="docs/PLAN.md"><strong>项目总规划</strong></a>
  &nbsp; · &nbsp;
  <a href="docs/PLAN.md#3-当前已经完成什么">实现现状</a>
  &nbsp; · &nbsp;
  <a href="docs/PLAN.md#4-后续六阶段路线图">建设路线</a>
  &nbsp; · &nbsp;
  <a href="docs/PLAN.md#8-需要哪些账户和-key">账户与 Key</a>
</p>

<p align="center">
  <sub>STRATEGY RESEARCH &nbsp; / &nbsp; REPRODUCIBLE EXPERIMENTS &nbsp; / &nbsp; STATISTICAL VALIDATION</sub>
</p>

---

## 研究应当留下证据

一条漂亮的净值曲线，是研究的开始。它来自什么数据、经历过多少次尝试、能否经受样本外与交易成本的检验，决定了它是否值得继续。

Axiom Street 把这些问题放进工作流程。面向个人研究者，并向小型团队演进，它将策略规则、版本、回测、验证和研究结论组织在同一个工作空间中。

<table>
  <tr>
    <td width="33%" valign="top">
      <strong>01 · 清晰的研究</strong><br /><br />
      从可读规则进入策略，以版本记录变化。必要信息始终可见，复杂参数按需展开。
    </td>
    <td width="33%" valign="top">
      <strong>02 · 可追溯的证据</strong><br /><br />
      数据快照、实验台账与结果相互关联。每个结论都应能够回到产生它的输入和过程。
    </td>
    <td width="33%" valign="top">
      <strong>03 · 有边界的决策</strong><br /><br />
      统计验证审视结果，独立风控约束执行。AI 提供协助，证据决定研究能走多远。
    </td>
  </tr>
</table>

## 一个连贯的工作空间

**提出假设 → 定义规则 → 固定版本与数据 → 运行实验 → 检验证据 → 形成结论**

| 工作区域 | 关注的问题 |
|---|---|
| **策略研究** | 交易规则是什么？本次修改改变了什么？ |
| **回测分析** | 收益、风险与成本如何？相对基准的差异来自哪里？ |
| **稳健性验证** | 样本外表现如何？是否过拟合？参数和成本有多敏感？ |
| **研究记录** | 哪些证据支持结论？哪些限制还没有解决？ |
| **模拟与风控** | 执行是否符合预期？账户、订单和风险是否一致？ |

产品采用明亮、克制的 **Research Studio** 视觉语言：清晰排版、对齐的财务数字、安静的颜色和真实的数据反馈。研究内容始终处于中心。

从持续模拟到受控实盘、从单人研究到团队协作，后续建设以逐阶段验收推进。**各模块的已实现范围、限制和下一步，统一以[项目总规划](docs/PLAN.md)为准。**

## 简洁的架构，明确的职责

```text
apps/web          研究界面 · Next.js / TypeScript
services/api      接口与应用服务 · FastAPI / PostgreSQL
services/worker   异步执行与恢复 · Celery / Redis
services/agent    研究助手 · 聚合事实与受限建议
quant             数据 / LEAN 引擎 / 指标 / 验证 / 风控
```

浏览器通过同源网关访问后端；长任务交给 Worker；量化计算留在独立领域模块。策略与券商解耦，研究助手与风险写入隔离。

架构契约、视觉规范、测试要求与阶段验收集中维护在[总规划](docs/PLAN.md)，让接手者从一个入口理解整个工程。

## 开始研究

开发基线：**Python 3.11 · Node.js 22 · Docker / Colima**。

1. 仅在配置文件不存在时，从 `.env.example` 和 `apps/web/.env.example` 创建对应本地配置。
2. 安装依赖，设置数据库凭据和后端地址；按需要配置行情与研究助手。
3. 按[启动说明](docs/PLAN.md#10-启动和交接)启动服务。完整回测需要数据库、Redis、Worker 和 LEAN 环境。

| 操作 | 命令 |
|---|---|
| 启动本地前端 | `make web` |
| 启动本地 API | `make api` |
| 启动完整开发栈 | `make up` |
| 执行常规质量检查 | `make test-all` |

> **部署边界** · 当前项目尚无实际用户鉴权，Compose 发布端口也尚未限制到本机地址。启动完整栈前先按总规划处理开发网络边界，不直接作为公网服务部署。真实密钥和研究运行产物留在本地或受控存储中。

---

<p align="center">
  <strong>少一点噪音，多一点依据。</strong><br />
  <sub>Axiom Street · A workspace for deliberate quantitative research.</sub>
</p>

第三方组件包括 QuantConnect LEAN 与 TradingView Lightweight Charts，均采用 Apache-2.0；相关声明与图表署名要求见 [NOTICE](NOTICE)。统计验证与回测结果不构成未来收益承诺。
