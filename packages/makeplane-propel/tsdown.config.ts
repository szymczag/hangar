// Build configuration for the recovered @makeplane/propel 0.9.7 source.
//
// Upstream did not publish its build configuration. This one is inferred from
// the published `dist/` and is accepted only because the equivalence check
// (`node scripts/propel/compare-dist.mjs`) finds the output equivalent to the
// published package. The toolchain is pinned in package.json and
// pnpm-workspace.yaml; README.md explains each choice.
import { readdirSync } from "node:fs";

import { defineConfig } from "tsdown";

// Entry order decides the bundler's module execution order, which in unbundled
// output decides the order of each file's import statements. Upstream's order
// is reproduced by these groups in this order, each sorted by name; the sort
// also keeps the build independent of the file system's directory order.
const ENTRY_GROUPS = ["base", "elements", "components", "hooks"];

function entries(): string[] {
  const groups = ENTRY_GROUPS.flatMap((group) =>
    readdirSync(`src/${group}`, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => `src/${group}/${entry.name}/index.ts`)
      .sort()
  );
  return [...groups, "src/icons/index.ts"];
}

// Icons are plain SVG components, so upstream leaves them without the
// `"use client"` directive: an empty banner, which still emits the leading
// newline the published icon files have.
const isIconChunk = (fileName: string) => /^(?:icons|state-icons)\//.test(fileName);

export default defineConfig({
  entry: entries(),
  // One output file per source module, mirroring src/.
  unbundle: true,
  format: "esm",
  platform: "neutral",
  // No syntax lowering: the published files keep the source's syntax.
  target: false,
  sourcemap: true,
  // Declarations come from the TypeScript compiler (typescript 6), not tsgo:
  // tsgo prints literal unions sorted, which the published files are not.
  dts: { sourcemap: true },
  banner: ({ fileName }) => (isIconChunk(fileName) ? "" : '"use client";'),
  // The logo-spinner images stay imports for the consuming bundler to resolve.
  deps: { neverBundle: [/\.(?:gif|png)$/] },
  copy: [
    // Tailwind v4 sources, shipped unprocessed.
    { from: "src/styles", to: "dist" },
    { from: "src/components/logo-spinner/*.{gif,png}", to: "dist/components/logo-spinner" },
  ],
});
