/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * The live image installs production dependencies only (apps/live/Dockerfile.live,
 * stage runtime-deps), and a workspace package whose import is satisfied in
 * development by a dev or peer dependency does not resolve there. 0.6.0-rc.1
 * shipped exactly that: the editor's server code reached @makeplane/propel,
 * whose React is a dev and peer dependency, and the server crash-looped with
 * ERR_MODULE_NOT_FOUND. No pull request check builds the image, so this test
 * repeats its install: `turbo prune live`, the built workspace packages, and
 * `pnpm install --prod --offline` from the store the development install
 * filled. It then resolves the built server's import graph in that tree with
 * apps/live/scripts/check-runtime-imports.mjs, which the image build runs too.
 *
 * Needs a built live: `pnpm turbo run build --filter=live`.
 */

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(fileURLToPath(new URL("../../..", import.meta.url)));
const CHECKER = path.join(ROOT, "apps/live/scripts/check-runtime-imports.mjs");
const ENTRY = "apps/live/dist/start.mjs";

const run = (command, args, cwd, env = {}) =>
  spawnSync(command, args, { cwd, encoding: "utf8", env: { ...process.env, ...env }, maxBuffer: 64 * 1024 * 1024 });

const check = (entry) => run(process.execPath, [CHECKER, entry], path.dirname(entry));

const write = (file, content) => {
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, content);
};

describe("check-runtime-imports", () => {
  // A miniature pnpm layout: an app, a workspace package linked into its
  // node_modules, and a third-party package.
  const fixture = () => {
    const dir = mkdtempSync(path.join(tmpdir(), "hangar-runtime-imports-"));
    write(path.join(dir, "node_modules/dep/package.json"), JSON.stringify({ name: "dep", main: "index.js" }));
    // Not followed: pnpm installed a third-party package's own dependencies.
    write(path.join(dir, "node_modules/dep/index.js"), 'require("not-installed-either");\n');
    write(
      path.join(dir, "packages/ws/package.json"),
      JSON.stringify({
        name: "@x/ws",
        type: "module",
        exports: { ".": "./dist/index.js", "./server": "./dist/server.js" },
      })
    );
    write(path.join(dir, "packages/ws/dist/index.js"), 'export { a } from "./chunk.js";\n');
    write(path.join(dir, "packages/ws/dist/chunk.js"), 'import "dep";\nexport const a = 1;\n');
    write(
      path.join(dir, "packages/ws/dist/server.js"),
      'import {\n  a,\n  b as c\n} from "./chunk.js";\nimport "node:fs";\nimport "fs/promises";\n'
    );
    mkdirSync(path.join(dir, "app/node_modules/@x"), { recursive: true });
    symlinkSync(path.join(dir, "packages/ws"), path.join(dir, "app/node_modules/@x/ws"), "dir");
    symlinkSync(path.join(dir, "node_modules/dep"), path.join(dir, "app/node_modules/dep"), "dir");
    write(path.join(dir, "app/package.json"), JSON.stringify({ name: "app", type: "module" }));
    return dir;
  };

  it("passes when every import resolves from its importer", () => {
    const dir = fixture();
    try {
      write(path.join(dir, "app/start.mjs"), 'import { a } from "@x/ws";\nimport "@x/ws/server";\n');
      const result = check(path.join(dir, "app/start.mjs"));
      assert.equal(result.status, 0, result.stderr);
      assert.match(result.stdout, /4 workspace files, every import resolves/);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("finds a dependency a workspace package reaches but does not install", () => {
    const dir = fixture();
    try {
      // The 0.6.0-rc.1 shape: resolvable from the app, not from the package.
      symlinkSync(path.join(dir, "node_modules/dep"), path.join(dir, "app/node_modules/react"), "dir");
      write(path.join(dir, "packages/ws/dist/icons.js"), 'import { jsx } from "react";\nexport const Icon = jsx;\n');
      write(
        path.join(dir, "packages/ws/dist/index.js"),
        'export { a } from "./chunk.js";\nexport * from "./icons.js";\n'
      );
      write(path.join(dir, "app/start.mjs"), 'import "react";\nimport { a } from "@x/ws";\n');
      const result = check(path.join(dir, "app/start.mjs"));
      assert.equal(result.status, 1);
      assert.match(result.stderr, /1 imports do not resolve/);
      assert.match(result.stderr, /react {2}\(ERR_MODULE_NOT_FOUND\) {2}in .*packages\/ws\/dist\/icons\.js/);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("follows dynamic imports and bundled require calls", () => {
    const dir = fixture();
    try {
      write(path.join(dir, "app/lazy.mjs"), 'import "missing-lazy";\n');
      write(path.join(dir, "app/start.mjs"), 'const m = () => import("./lazy.mjs");\n__require("missing-cjs");\n');
      const result = check(path.join(dir, "app/start.mjs"));
      assert.equal(result.status, 1);
      assert.match(result.stderr, /missing-lazy .* in .*lazy\.mjs/);
      assert.match(result.stderr, /missing-cjs .* in .*start\.mjs/);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
  it("resolves require.resolve lookups, as the PDF exporter's font directory", () => {
    const dir = fixture();
    try {
      write(
        path.join(dir, "app/start.mjs"),
        [
          'import { createRequire } from "node:module";',
          "const require = createRequire(import.meta.url);",
          'const ok = require.resolve("dep/package.json");',
          'const fontDir = require.resolve("@fontsource/missing/package.json");',
          'const bundled = __require.resolve("missing-bundled");',
          "",
        ].join("\n")
      );
      const result = check(path.join(dir, "app/start.mjs"));
      assert.equal(result.status, 1);
      assert.match(result.stderr, /2 imports do not resolve/);
      assert.match(result.stderr, /@fontsource\/missing\/package\.json .* in .*start\.mjs/);
      assert.match(result.stderr, /missing-bundled .* in .*start\.mjs/);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe("the built live server under a production-only install", () => {
  it("resolves every import the server reaches", { timeout: 10 * 60_000 }, () => {
    assert.ok(
      existsSync(path.join(ROOT, ENTRY)),
      `${ENTRY} is missing: build it first with pnpm turbo run build --filter=live`
    );
    const work = mkdtempSync(path.join(tmpdir(), "hangar-live-prod-"));
    try {
      // apps/live/Dockerfile.live, stage builder.
      const out = path.join(work, "out");
      const prune = run("pnpm", ["exec", "turbo", "prune", "live", "--docker", "--out-dir", out], ROOT, {
        TURBO_TELEMETRY_DISABLED: "1",
      });
      assert.equal(prune.status, 0, prune.stderr || prune.stdout);

      // Stage runtime-deps: the pruned manifests and lockfile, the built
      // workspace packages without their node_modules, and live's own build.
      const app = path.join(work, "app");
      cpSync(path.join(out, "json"), app, { recursive: true });
      cpSync(path.join(out, "pnpm-lock.yaml"), path.join(app, "pnpm-lock.yaml"));
      for (const name of readdirSync(path.join(out, "json/packages"))) {
        cpSync(path.join(ROOT, "packages", name), path.join(app, "packages", name), {
          recursive: true,
          filter: (source) => !/[/\\](?:node_modules|\.turbo)$/.test(source),
        });
      }
      cpSync(path.join(ROOT, "apps/live/dist"), path.join(app, "apps/live/dist"), { recursive: true });

      // pnpm keeps one store per filesystem, and the temporary directory may
      // be on another one than the checkout: name the store the development
      // install filled.
      const store = run("pnpm", ["store", "path", "--silent"], ROOT);
      assert.equal(store.status, 0, store.stderr);
      const install = run(
        "pnpm",
        [
          "install",
          "--offline",
          "--frozen-lockfile",
          "--prod",
          "--ignore-scripts",
          `--store-dir=${store.stdout.trim()}`,
          "--config.confirm-modules-purge=false",
        ],
        app,
        { CI: "true", NODE_ENV: "production" }
      );
      assert.equal(install.status, 0, install.stderr || install.stdout);

      const result = check(path.join(app, ENTRY));
      assert.equal(result.status, 0, `${result.stdout}${result.stderr}`);
    } finally {
      rmSync(work, { recursive: true, force: true });
    }
  });
});
