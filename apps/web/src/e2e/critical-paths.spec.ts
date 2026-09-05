import { test, expect } from "@playwright/test";

test.describe("关键路径 E2E", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("① 建策略 → 跑回测 → 看 tearsheet", async ({ page }) => {
    // 进入策略实验室
    await page.click('text="策略"');
    await expect(page).toHaveURL(/.*strategies/);

    // 新建策略
    await page.click('text="新建策略"');
    await page.fill('input[name="name"]', "E2E Test Strategy");
    await page.fill('textarea[name="description"]', "E2E test");
    await page.click('button:has-text("创建")');

    // 编辑策略代码
    await page.waitForSelector(".monaco-editor");
    // 在 Monaco 编辑器中输入简单的 SPY 200DMA 策略
    const editor = page.locator(".monaco-editor");
    await editor.click();
    await page.keyboard.type("class E2EStrategy:\n    def Initialize(self):\n        self.sma = self.SMA('SPY', 200)\n");
    await page.keyboard.press("Control+s");

    // 提交版本
    await page.click('button:has-text("提交版本")');
    await page.fill('textarea[name="commit_message"]', "Initial version");
    await page.click('button:has-text("确认")');

    // 运行回测
    await page.click('text="回测"');
    await page.click('button:has-text("新建回测")');
    await page.selectOption('select[name="strategy_version_id"]', { label: "E2E Test Strategy v1" });
    await page.fill('input[name="start_date"]', "2018-01-01");
    await page.fill('input[name="end_date"]', "2020-12-31");
    await page.click('button:has-text("运行")');

    // 等待回测完成
    await expect(page.locator('text="已完成"')).toBeVisible({ timeout: 120000 });

    // 查看 tearsheet
    await page.click('text="查看详情"');
    await expect(page).toHaveURL(/.*backtests\/.*/);

    // 验证 tearsheet 关键元素
    await expect(page.locator("text=净值曲线")).toBeVisible();
    await expect(page.locator("text=回撤")).toBeVisible();
    await expect(page.locator("text=月度收益")).toBeVisible();
    await expect(page.locator("text=总收益")).toBeVisible();
    await expect(page.locator("text=夏普比率")).toBeVisible();
    await expect(page.locator("text=最大回撤")).toBeVisible();
  });

  test("② 发起验证 → 闸门失败 → VALIDATED 不可达", async ({ page }) => {
    // 前置：已有完成回测的策略
    await page.goto("/strategies");
    await page.click('text="E2E Test Strategy"');
    await page.click('text="版本历史"');
    await page.click('text="v1"');

    // 发起 PBO 验证（使用过拟合参数）
    await page.goto("/validation");
    await page.click('button:has-text("发起验证")');
    await page.selectOption('select[name="kind"]', "pbo");
    await page.fill('textarea[name="values"]', "[5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]");
    await page.click('button:has-text("发起")');

    // 等待验证完成
    await expect(page.locator('text="PBO"')).toBeVisible({ timeout: 120000 });

    // 验证 PBO > 0.5 (过拟合)
    const pboRow = page.locator('tr:has-text("PBO")').first();
    await expect(pboRow.locator('text=/PBO.*>.*0.5/')).toBeVisible();

    // 尝试手动标记为 VALIDATED 应该失败
    await page.goto("/strategies");
    await page.click('text="E2E Test Strategy"');
    // 尝试修改状态为 VALIDATED
    await page.click('button:has-text("编辑")');
    await page.selectOption('select[name="status"]', "VALIDATED");
    await page.click('button:has-text("保存")');

    // 应该返回 409 错误
    await expect(page.locator("text=409")).toBeVisible();
    await expect(page.locator("text=客户端不能把策略标成已验证")).toBeVisible();
  });

  test("③ 摄取数据 → 质量报告可见", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.locator("text=数据状态")).toBeVisible();

    // 发起增量摄取
    await page.click('button:has-text("拉取行情")');
    await page.fill('input[name="symbols"]', "SPY,QQQ");
    await page.selectOption('select[name="mode"]', "incremental");
    await page.click('button:has-text("开始")');

    // 等待摄取完成
    await expect(page.locator('text="已完成"')).toBeVisible({ timeout: 120000 });

    // 查看质量报告
    await page.click('text="质量报告"');
    await expect(page.locator("text=质量报告")).toBeVisible();

    // 验证关键指标
    await expect(page.locator("text=数据行数")).toBeVisible();
    await expect(page.locator("text=覆盖日期")).toBeVisible();
    await expect(page.locator("text=分红/拆分已验证")).toBeVisible();

    // 验证双源对账可见
    await page.click('text="双源对账"');
    await expect(page.locator("text=可疑 Bar")).toBeVisible();
  });
});