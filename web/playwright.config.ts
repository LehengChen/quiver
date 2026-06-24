import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4181",
    trace: "retain-on-failure",
    screenshot: "only-on-failure"
  },
  webServer: {
    command: "python -m http.server 4181 -d ../examples/pages/geometric-analysis-narrow-v1",
    url: "http://127.0.0.1:4181",
    reuseExistingServer: true,
    timeout: 120000
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 940 } }
    },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"] }
    }
  ]
});
