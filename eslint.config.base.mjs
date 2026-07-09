// Shared ESLint 9 flat config for internal @grc/* packages that are not Next.js apps
// (packages/ui, packages/contracts, packages/i18n). apps/web has its own config built on
// eslint-config-next instead — see apps/web/eslint.config.mjs.
import js from "@eslint/js";
import tseslint from "@typescript-eslint/eslint-plugin";

export default [
  { ignores: ["dist/**", "node_modules/**"] },
  js.configs.recommended,
  ...tseslint.configs["flat/recommended"],
];
