import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import vitePluginImp from "vite-plugin-imp";
import { splitVendorChunkPlugin } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

// https://vitejs.dev/config/
export default defineConfig({
  build: {
    manifest: true,
    // outDir: "../static/dist",
    // emptyOutDir: true,
    // rollupOptions: {
    //   input: {
    //     main: "./src/index.html",
    //   },
    //   output: {
    //     chunkFileNames: undefined,
    //   },
    // },
  },
  base: process.env.mode === "production" ? "/static/" : "./",
  publicDir: "./public",
  root: "./src",
  resolve: {
    alias: [{ find: /^~/, replacement: "" }],
  },
  plugins: [
    react(),
    splitVendorChunkPlugin(),
    // tsconfigPaths(),
  ],
  server: {
    host: true,
    hmr: {
      clientPort: 3000,
    },
    port: 3000,
    open: false,
    middlewareMode: false,
    strictPort: true,
    watch: {
      usePolling: true,
    },
  },
  css: {
    preprocessorOptions: {
      less: {
        javascriptEnabled: true,
      },
    },
  },
});
