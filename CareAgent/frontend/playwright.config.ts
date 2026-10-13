import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests", fullyParallel: false, workers: 1,
  use: {baseURL: process.env.E2E_BASE_URL || "http://localhost:3000", trace: "retain-on-failure",
        channel: process.env.PLAYWRIGHT_CHANNEL || undefined},
  timeout: 240000,
});
