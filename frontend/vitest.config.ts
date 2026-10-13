import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.join(import.meta.dirname, "."),
      "server-only": path.join(import.meta.dirname, "test", "stubs", "server-only.ts"),
    },
  },
  test: {
    environment: "node",
    include: ["lib/__tests__/**/*.test.ts"],
  },
});
