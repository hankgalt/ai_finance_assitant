import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  base: "/finance_assistant/",
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5174,
    proxy: {
      "/finance_assistant/api": {
        target: "http://127.0.0.1:8000",
        rewrite: (path) => path.replace(/^\/finance_assistant/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    exclude: ["e2e/**", "node_modules/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      reportsDirectory: "../backend/artifacts/quality/frontend-coverage",
      // Measure every application module, including ones no test imports.
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/test/**", "src/vite-env.d.ts"],
      thresholds: {
        lines: 90,
        statements: 90,
      },
    },
  },
});
