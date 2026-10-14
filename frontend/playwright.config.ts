import { defineConfig } from "@playwright/test";
import path from "node:path";
const root = path.resolve(__dirname, "..");
const run = Date.now();
export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:3001",
    headless: true,
    viewport: { width: 1440, height: 1800 },
    channel: process.env.PLAYWRIGHT_CHANNEL || "chrome",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        "uv run alembic upgrade head && uv run uvicorn app.main:app --host 127.0.0.1 --port 8001",
      cwd: path.join(root, "backend"),
      url: "http://127.0.0.1:8001/health",
      reuseExistingServer: false,
      env: {
        DATABASE_URL: `sqlite:///${root}/work/e2e-${run}.db`,
        STORAGE_ROOT: `${root}/work/e2e-files-${run}`,
        OCR_PROVIDER: "mock",
      },
    },
    {
      command: "npm run start -- --port 3001",
      url: "http://127.0.0.1:3001",
      reuseExistingServer: false,
      env: { API_BASE_URL: "http://127.0.0.1:8001" },
    },
  ],
});
