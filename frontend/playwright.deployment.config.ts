import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e/deployment",
  outputDir: "./test-results/deployment-playwright",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  timeout: 15 * 60 * 1_000,
  expect: { timeout: 60_000 },
  use: {
    baseURL: "https://apps.comfforts.com",
    channel: "chrome",
    headless: false,
    // Authentication and application state are never captured as test media.
    screenshot: "off",
    // A trace may retain authenticated request metadata. Keep this live-IAP
    // qualification observable through assertions without recording a trace.
    trace: "off",
    video: "off",
  },
  projects: [
    { name: "deployed-desktop-chrome", use: { ...devices["Desktop Chrome"] } },
  ],
});
