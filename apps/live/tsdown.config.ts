import { defineConfig } from "tsdown";

export default defineConfig({
  entry: ["src/start.ts"],
  outDir: "dist",
  format: ["esm"],
  dts: false,
  clean: true,
  sourcemap: false,
  exports: {
    // The PDF exporter resolves its bundled emoji font as `live/assets/fonts/...`,
    // so the same lookup works from the sources, the build and the image.
    customExports: (exports) => ({ ...exports, "./assets/fonts/*": "./assets/fonts/*" }),
  },
});
