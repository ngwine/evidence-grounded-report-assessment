import { defineConfig, devices } from '@playwright/test';

// UI contract tests with a mocked API, NOT a Mongo/API integration benchmark.
export default defineConfig({
  testDir: './tests',
  testMatch: 'authenticated.auth.ts',
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  outputDir: '../../var/e2e-auth-ui',
  use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:5174', trace: 'off', screenshot: 'off', video: 'off' },
  webServer: {
    command: 'npm run dev -- --port 5174',
    env: { VITE_APP_MODE: 'authenticated' },
    url: 'http://127.0.0.1:5174', reuseExistingServer: false, timeout: 60_000,
  },
});
