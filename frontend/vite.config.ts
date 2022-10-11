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
<<<<<<< HEAD
        modifyVars: {
          "primary-color": "#1D1D1F",
          "link-color": "#1DA57A",
          "highlight-color": "#CCA43B",
          black: "#1D1D1F",
          white: "#F7F8FD",
          "border-radius-base": "4px",
          "typography-title-font-weight": 700,
          "height-base": "48px",
          "border-color-base": "#1D1D1F",
          "font-size-base": "14px",
          "font-family": "Inter, sans-serif",
          "heading-1-size": "32px",
          "heading-2-size": "26px",
          "heading-3-size": "16px",
          "heading-4-size": "14px",
        },
=======
>>>>>>> origin/gr/ant-theme-setup-without-vite-config
      },
    },
  },
});
