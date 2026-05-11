import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.PW_BASE_URL ?? 'http://localhost:5173'

export default defineConfig({
  testDir: process.env.PW_TEST_DIR ?? './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',

  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],

  webServer: process.env.PW_NO_SERVER
    ? undefined
    : {
        command: process.env.PW_DEV_CMD ?? 'bun run dev',
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
})
