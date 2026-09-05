# 前端重构与接手说明

## 当前实现

Axiom Street 的唯一产品前端是 `apps/web`。本次整理保留 Next.js、React Query、FastAPI 与 Python 量化核心，完成白色 White Studio 视觉系统、研究概览、新建研究、策略集合、回测集合、响应式外壳与服务网关。策略编辑、版本比较、统计验证、标的池和研究笔记继续使用真实业务接口。

原有未提交的后端与数据整理内容保持保留。本轮没有升级 Next.js 主版本，也没有改变量化计算口径、数据快照或验证闸门。

## 目录职责

```text
apps/web/src/
  app/                      路由入口、全局样式、Provider
    api/backend/[...path]/  Next.js 服务端转发入口
  components/
    brand/                  Axiom 矢量标记
    layout/                 桌面 / 手机导航、顶栏、应用外壳
    ui/                     基础控件与反馈状态
    charts/                 图表渲染
  features/
    home/                   概览、研究主视觉、路径引导、最近活动
    strategy-lab/           策略集合、新建弹窗、编辑器、版本与任务状态
    backtests/              回测集合、详情、use-backtest-analysis 派生数据
    validation/
      reports/              六类独立报告组件
      validation-status.ts  状态解释
    settings/               数据环境与数据质量诊断
    research/               研究笔记
    universes/              标的池
    experiments/            实验比较
  lib/
    api.ts                  兼容原有调用的公开 facade
    api/
      types.ts              API 数据契约
      http.ts               JSON 请求、超时、可读错误、列表解包
      proxy.ts              同源转发、下载、事件流
      strategies.ts         策略与版本接口
      backtests.ts          回测、指标、成交、导出接口
      data.ts               行情、快照、环境接口
      validation.ts         稳健性验证接口
      universes.ts          标的池接口
      research.ts           笔记接口
      code.ts               Python 语法 / 语言服务接口
    chart-tokens.ts          Canvas 的颜色适配
    tearsheet.ts            纯计算与统计变换
services/api/               routers → services → 数据模型
services/worker/            Celery 作业与 LEAN 执行
quant/                      纯 Python 量化领域逻辑
```

不为追求目录变化搬动 Python 领域包。它已经拥有 engine / data / metrics / validation 的清晰边界。以后新增页面保持薄路由，业务放在对应 feature；新增 API 放在对应 domain module。

## 启动

### 完整研究环境

项目根目录运行 `make up`，浏览器打开 http://localhost:3000。Docker Compose 内部由 Next.js 访问 `http://api:8000`，而不是浏览器访问容器或 localhost 地址。完整回测需要 PostgreSQL、Redis、Worker、Docker 与固定版本 LEAN 镜像，以及可用的行情快照。

### 本地开发

```sh
# 根目录：使用已安装的 Python 环境
make api

# 另一个终端
cp apps/web/.env.example apps/web/.env.local
npm --prefix apps/web ci
make web
```

`make` 会优先使用 `.venv/bin/python -m ...`，避免项目重命名后旧的 venv console script 指向失效目录。新机器先按根 README 安装 Python 依赖与配置数据库。

### 仅验证 UI 与 CRUD（独立数据库）

```sh
STREET_DATABASE_URL=sqlite+pysqlite:////tmp/axiom-ui.db \
STREET_SKIP_MIGRATIONS=1 \
STREET_MARKET_RECONCILE_ENABLED=false \
.venv/bin/python -m uvicorn services.api.main:app --port 8000
```

本次演示预览使用 `/tmp/axiom-white-studio-qa.db`，其中的「界面联调 · 趋势研究」是测试记录。

此模式适合界面联调和策略/版本/标的池/笔记 CRUD；不会提供可运行的 LEAN 作业环境。正式数据必须使用正常迁移流程，不使用 `STREET_SKIP_MIGRATIONS`。

## 前后端约定

1. 浏览器默认请求 `/api/backend`。例如 `/api/backend/api/v1/strategies` 转发到 FastAPI `/api/v1/strategies`。
2. 服务端环境变量 `API_BASE_URL` 指定实际后端。默认为 `http://127.0.0.1:8000`；Docker 内是 `http://api:8000`。该值运行时读取，不需要把内部地址编译进浏览器 bundle。
3. `NEXT_PUBLIC_API_URL` 保留旧版直连兼容，需要在构建时提供并配置 FastAPI CORS。常规部署建议留空，使用同源网关。
4. 网关保留 GET/POST/PATCH/PUT/DELETE、查询参数、JSON body、HTTP 状态、下载 MIME 与 Content-Disposition、X-Request-ID。限制转发目标为固定后端的 health 和 api/v1 路径。
5. SSE 直接转发 Response.body，不解析、不拼接完整响应。握手等待限制 30 秒，连接成功后不会因同一个计时器中断长任务。
6. JSON 请求默认 30 秒超时。非 2xx 的 FastAPI detail 转换为可读错误；204 删除返回 undefined；HTML 错误页不会直接显示给用户。
7. 查询结果继续由 React Query 管理。新建或保存时使相关查询失效。查询失败与空列表分别展示，不能把网络错误解释成没有研究。
8. 无时区的数据库时间按 UTC 解释，显式时区偏移保持原样，修正中国时区显示偏移八小时的问题。

## 验证与边界

本轮验收结果：前端 29 项测试通过；后端 344 项测试通过；ESLint、TypeScript、Ruff、Python 类型检查（78 个源文件）通过；Next.js 生产构建通过。生产浏览器检查覆盖概览、策略、回测、验证、标的池、实验、笔记与设置，未发现横向溢出或应用错误。

执行：`npm --prefix apps/web test`、`npm --prefix apps/web run lint`、`npm --prefix apps/web run typecheck`、`npm --prefix apps/web run build`、`.venv/bin/python -m pytest tests/unit -q`。

浏览器验收使用独立 SQLite 数据库。覆盖创建趋势研究、修改研究假设、保存 v2、桌面概览、390px 手机视图、移动导航与命令搜索。HTTP 测试覆盖网关查询/请求体/状态、SSE 透传、连接失败、非法路径、无内容删除与 UTC 时间。

- 未运行新的真实行情摄取或完整 Docker/LEAN Golden 回测；金融数值链路以现有单元测试回归为依据。
- Docker Compose 地址配置已更新；容器镜像部署需要在具备 Docker 的环境单独验证。
- 本地工作区仍为单用户产品，不应将它当作已具备身份鉴别的公网多租户服务。
- 列表保留现有 API 分页语义；概览统计对应当前加载的数据，不是跨页审计总数。
- 全量国际化、实盘、硬风控仍是后续产品阶段；本轮没有用无功能按钮伪装这些能力。

视觉规范见 `design-system/axiom-street/MASTER.md`。历史设计被保留在其 archive 目录。
