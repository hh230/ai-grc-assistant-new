// ESLint 9 flat config. Replaces .eslintrc.json — ESLint 9 looks for this file by default and
// does not fall back to legacy .eslintrc.* config on its own. FlatCompat bridges
// eslint-config-next's legacy-style "extends" config into flat config; same ruleset as
// before (next/core-web-vitals), nothing added or removed.
import { FlatCompat } from "@eslint/eslintrc";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  // `next lint` excluded these automatically; plain `eslint` (see package.json's "lint"
  // script) does not, so it must be told explicitly — otherwise it lints compiled/minified
  // build output as if it were source.
  { ignores: [".next/**", "node_modules/**"] },
  ...compat.extends("next/core-web-vitals"),
];

export default eslintConfig;
