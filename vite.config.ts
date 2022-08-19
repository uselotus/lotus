import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import vitePluginImp from "vite-plugin-imp";
import { splitVendorChunkPlugin } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

// https://vitejs.dev/config/
export default defineConfig({
  build: {
    manifest: true,
    outDir: "../static/dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: "./src/main.tsx",
      },
      output: {
        chunkFileNames: undefined,
      },
    },
  },
  server: {
    host: "localhost",
    port: 3000,
    open: false,
    watch: {
      usePolling: true,
      disableGlobbing: false,
    },
  },
  base: process.env.mode === "production" ? "./" : "./",
  publicDir: "public",
  root: "./src/",
  resolve: {
    extensions: [".js", ".json", ".jsx", ".ts", ".tsx"],
  },

  plugins: [
    react(),
    splitVendorChunkPlugin(),
    tsconfigPaths(),
    vitePluginImp({
      optimize: true,
      libList: [
        {
          libName: "antd",
          libDirectory: "es",
          style: (name) => `antd/es/${name}/style`,
        },
      ],
    }),
  ],
  css: {
    preprocessorOptions: {
      less: {
        javascriptEnabled: true, //
      },
    },
  },
});
