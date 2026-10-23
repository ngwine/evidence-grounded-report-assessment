import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests', testMatch: 'authenticated.mongo.ts', timeout: 90_000, workers: 1,
  reporter: 'list', outputDir: '../../var/e2e-auth-mongo',
  use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:5173',
    trace: 'off', screenshot: 'off', video: 'off' },
  webServer: [
    { command: '../../.venv-research/bin/python ../../scripts/run_authenticated_mongo_e2e.py',
      url: 'http://127.0.0.1:8001/api/v1/auth/me', ignoreHTTPSErrors: false,
      reuseExistingServer: false, timeout: 60_000,
      env: { KLTN_RUN_AUTH_MONGO_E2E: '1', HF_HUB_OFFLINE: '1', TRANSFORMERS_OFFLINE: '1' } },
    { command: 'npm run dev -- --port 5173', env: { VITE_APP_MODE: 'authenticated' },
      url: 'http://127.0.0.1:5173', reuseExistingServer: false, timeout: 60_000 },
  ],
});
