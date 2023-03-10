import { defineConfig } from "cypress";

export default defineConfig({
  pageLoadTimeout: 2000000,
  e2e: {
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
  },
});
