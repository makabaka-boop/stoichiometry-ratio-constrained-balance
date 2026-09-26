import { defineConfig } from "@playwright/test";

// Assumes the workbench is already running:
//   docker compose up --build   (web published on http://localhost:8080)
// or locally:
//   uvicorn app.main:app --port 8000   +   npm run dev (web on :5173)
// Override with BASE_URL=http://localhost:8080 npx playwright test.
const BASE_URL = process.env.BASE_URL ?? "http://localhost:5173";

export default defineConfig({
  testDir: ".",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
  },
});
