module.exports = {
  extends: [
    // By extending from a plugin config, we can get recommended rules without having to add them manually.
    "eslint:recommended",
    "airbnb",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended", // This line was added
    "plugin:import/recommended",
    "plugin:jsx-a11y/recommended",
    "plugin:@typescript-eslint/recommended",
    // This disables the formatting rules in ESLint that Prettier is going to be responsible for handling.
    // Make sure it's always the last config, so it gets the chance to override other configs.
    "eslint-config-prettier",
  ],
  settings: {
    react: {
      // Tells eslint-plugin-react to automatically detect the version of React to use.
      version: "detect",
    },
    // Tells eslint how to resolve imports
    "import/resolver": {
      node: {
        paths: ["src"],
        extensions: [".js", ".jsx", ".ts", ".tsx"],
      },
    },
  },
  rules: {
    // Add your own rules here to override ones from the extended configs.
  },
};
