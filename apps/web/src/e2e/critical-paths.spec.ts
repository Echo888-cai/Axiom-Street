import { test, expect, type APIRequestContext } from "@playwright/test";

// 隔离 E2E（P1 关闭验收）：web :3200（dockerized；:3100 被遗留 next-server 占用）
// / api :8100，独立项目/端口/库，使用 data-e2e/jobs-e2e，不触碰现行研究库（axiom-street :3000/:8000）。
// 运行方式：npx playwright test --config=pw.e2e.tmp.config.ts

// 固定策略名：验收前重置隔离库（确定性），q 搜索取最新一条可容忍历史残留。
const STRATEGY_NAME = "E2E 趋势策略";
const API_BASE = "http://localhost:8100";
// 短窗口回测（<252 交易日），Bootstrap 必然失败，构成确定性闸门拒绝。
const SHORT_START = "2019-07-01";
const SHORT_END = "2019-12-31";

async function selectOptionByText(
  page: import("@playwright/test").Page,
  id: string,
  text: string,
): Promise<void> {
  // 选项文案可能是「名称 · 状态」「日期 → 日期 · Sharpe」或原始枚举，
  // 因此按文本定位 option 后取其 value 再 select，避免硬编码完整 label。
  const option = page.locator(`#${id} option`).filter({ hasText: text }).first();
  await option.waitFor({ state: "attached", timeout: 10000 });
  const value = await option.getAttribute("value");
  expect(value, `#${id} 应有包含 ${text} 的 option`).toBeTruthy();
  await page.selectOption(`#${id}`, value as string);
}

async function strategyId(request: APIRequestContext): Promise<string> {
  // request fixture 的 baseURL 是 web(:3200)，API 断言必须显式指向隔离 API。
  const res = await request.get(
    `${API_BASE}/api/v1/strategies?q=${encodeURIComponent(STRATEGY_NAME)}`,
  );
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { items: { id: string }[] };
  // 取最新一条（列表按更新时间倒序）；验收前已重置隔离库，正常唯一。
  const hit = body.items[0];
  expect(hit, `应在隔离库中找到「${STRATEGY_NAME}」`).toBeDefined();
  return hit.id;
}

test.describe("关键路径 E2E（隔离栈）", () => {
  test("① 建策略 → 跑回测 → 看 tearsheet", async ({ page }) => {
    // 进入策略实验室
    await page.goto("/strategies");
    await expect(page.getByRole("link", { name: "策略实验室" })).toBeVisible();

    // 新建研究（趋势模板，默认 SPY 200DMA）
    await page.getByRole("button", { name: /新建研究/ }).click();
    await page.locator("#research-name").fill(STRATEGY_NAME);
    await page.getByRole("button", { name: /创建并开始研究/ }).click();
    await expect(page).toHaveURL(/\/strategies\/[0-9a-f-]{8,}/);

    // 引导模式默认日期 2018-01-01 → 2020-12-31，直接运行实验
    await expect(
      page.getByRole("button", { name: /运行实验/ }),
    ).toBeEnabled({ timeout: 15000 });
    await page.getByRole("button", { name: /运行实验/ }).click();

    // 等待回测完成（LEAN 真机执行，含首次环境准备）
    await expect(page.getByText("回测完成")).toBeVisible({ timeout: 300000 });

    // 打开 tearsheet（/backtests/[id]）
    await page.getByRole("link", { name: /打开 tearsheet/ }).click();
    await expect(page).toHaveURL(/\/backtests\/[0-9a-f-]{8,}/);
    await expect(page.getByText("权益曲线")).toBeVisible();
    await expect(page.getByRole("heading", { name: "回撤" })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "诚实指标" }),
    ).toBeVisible();
    await expect(page.getByText("原始夏普", { exact: true })).toBeVisible();
    await expect(page.getByText("年化 CAGR")).toBeVisible();
  });

  test("② 验证闸门：样本不足 → 失败证据可见 → VALIDATED 不可达", async ({
    page,
    request,
  }) => {
    // 前置：复用 ① 的策略，跑一个 <252 交易日的短窗口回测（2019-07-01 → 2019-12-31）。
    // 直接经隔离 API 取 ID 进详情页，避免依赖列表渲染（列表本身由 P1.2b 单测覆盖）。
    const id = await strategyId(request);
    await page.goto(`/strategies/${id}`);
    await expect(page).toHaveURL(new RegExp(`/strategies/${id}`));

    const dateInputs = page.locator('input[type="date"]');
    await expect(dateInputs.first()).toBeVisible({ timeout: 15000 });
    await dateInputs.first().fill(SHORT_START);
    await dateInputs.nth(1).fill(SHORT_END);
    await page.getByRole("button", { name: /运行实验/ }).click();
    await expect(page.getByText("回测完成")).toBeVisible({ timeout: 300000 });

    // 发起 Bootstrap 验证（该回测不足 252 个交易日，必然“失败”，确定性闸门拒绝）
    await page.goto("/validation");
    await expect(
      page.getByRole("heading", { name: "稳健性验证" }),
    ).toBeVisible();
    await selectOptionByText(page, "vlaunch-strategy", STRATEGY_NAME);
    await selectOptionByText(page, "vlaunch-backtest", SHORT_START);
    await selectOptionByText(page, "vlaunch-kind", "BOOTSTRAP");
    await page.getByRole("button", { name: /发起验证/ }).click();

    // 失败证据：错误原因“少于 252 个交易日”在验证台可见
    await expect(page.getByText(/少于 252 个交易日/)).toBeVisible({
      timeout: 120000,
    });

    // 结论：策略仍是 BACKTESTED，客户端不能手工置为 VALIDATED（409）
    const list = await request.get(`${API_BASE}/api/v1/strategies/${id}`);
    const strategy = (await list.json()) as { status: string };
    expect(strategy.status).toBe("BACKTESTED");

    const forbid = await request.patch(`${API_BASE}/api/v1/strategies/${id}`, {
      data: { status: "VALIDATED" },
    });
    expect(forbid.status()).toBe(409);
    const payload = (await forbid.json()) as { detail?: { code?: string } };
    expect(payload.detail?.code).toBe("status_transition_forbidden");
  });

  test("③ 设置页：隔离数据底座已就绪并可读", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "设置" })).toBeVisible();

    // 行情数据卡片：就绪 + SPY（来自 data-e2e 快照）
    await expect(page.getByText("行情数据")).toBeVisible();
    await expect(page.getByText("已就绪")).toBeVisible();
    await expect(page.getByText("SPY", { exact: true })).toBeVisible();

    // 展开“数据版本与更新配置”：快照与分红/拆分核验来自隔离数据底座
    await page.getByText("数据版本与更新配置").click();
    await expect(page.getByText("快照", { exact: true })).toBeVisible();
    await expect(page.getByText("已核验")).toBeVisible();
  });
});