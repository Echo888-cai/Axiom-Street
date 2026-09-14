import { defineConfig, devices } from "@playwright/test";

// 隔离 E2E（P1 关闭验收）：打 docker 化的 e2e web（默认 :3200），
// 配套 infra/e2e/docker-compose.e2e.yml + data-e2e/jobs-e2e，独立库与端口，
// 不触碰运行中的 axiom-street 主栈。
// 运行：npx playwright test --config playwright.e2e.config.ts
export default defineConfig({
  testDir: "./src/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 300000,
  retries: 0,
  reporter: "line",
  use: {
    baseURL: process.env.E2E_WEB_URL || "http://localhost:3200",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
