import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// build เป็นไฟล์ธรรมดาใน redbook/static/app — แอปเดิม (FastAPI) เสิร์ฟเอง ที่ origin เดียวกัน
// ไม่มีสคริปต์/สไตล์ฝังในหน้า (CSP: script-src 'self'; style-src 'self') · ไม่โหลดอะไรจากอินเทอร์เน็ต
export default defineConfig({
  base: "/static/app/",
  plugins: [svelte({ compilerOptions: { css: "external" } })],
  build: {
    outDir: "../redbook/static/app",
    emptyOutDir: true,
    assetsInlineLimit: 0,
    modulePreload: { polyfill: false },
    target: "es2022",
  },
  server: { proxy: { "/api": "http://127.0.0.1:8644", "/static": "http://127.0.0.1:8644",
                     "/trial": "http://127.0.0.1:8644", "/pdfpair": "http://127.0.0.1:8644" } },
});
