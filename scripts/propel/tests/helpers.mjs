// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

// Build small npm-style tarballs in memory for the recovery tests.

import { gzipSync } from "node:zlib";

import { sriSha512 } from "../lib/tar.mjs";

function header(name, size, type = "0") {
  const block = Buffer.alloc(512);
  block.write(name, 0, 100, "utf8");
  block.write("0000644\0", 100);
  block.write("0000000\0", 108);
  block.write("0000000\0", 116);
  block.write(`${size.toString(8).padStart(11, "0")}\0`, 124);
  block.write("00000000000\0", 136);
  block.write("        ", 148);
  block.write(type, 156);
  block.write("ustar\0", 257);
  block.write("00", 263);
  let sum = 0;
  for (const byte of block) sum += byte;
  block.write(`${sum.toString(8).padStart(6, "0")}\0 `, 148);
  return block;
}

/** entries: Array<[path, content, type?]>; paths are written as given. */
export function makeTarball(entries) {
  const parts = [];
  for (const [name, content = "", type = "0"] of entries) {
    const body = Buffer.from(content);
    parts.push(header(name, body.length, type), body, Buffer.alloc((512 - (body.length % 512)) % 512));
  }
  parts.push(Buffer.alloc(1024));
  return gzipSync(Buffer.concat(parts));
}

export function sourceMap(file, source, content) {
  const map = { version: 3, file, names: [], sources: [source], mappings: "AAAA" };
  if (content !== undefined) map.sourcesContent = [content];
  return JSON.stringify(map);
}

/** A minimal package with one module, one barrel and one type-only module. */
export function samplePackage(overrides = {}) {
  const files = {
    "package/package.json": JSON.stringify({ name: "@makeplane/propel", version: "0.0.1" }),
    "package/LICENSE": "license text\n",
    "package/dist/elements/button/button.js": '"use client";\nfunction Button() {}\nexport { Button };\n',
    "package/dist/elements/button/button.js.map": sourceMap(
      "button.js",
      "../../../src/elements/button/button.tsx",
      'import type { Size } from "../../internal/size";\n\nexport type ButtonProps = { size: Size };\nexport function Button(_: ButtonProps) {}\n'
    ),
    "package/dist/elements/button/button.d.ts":
      '"use client";\nimport { Size } from "../../internal/size.js";\ntype ButtonProps = { size: Size };\ndeclare function Button(_: ButtonProps): void;\nexport { Button, ButtonProps };\n',
    "package/dist/elements/button/index.js":
      '"use client";\nimport { Button } from "./button.js";\nexport { Button };\n',
    "package/dist/elements/button/index.d.ts":
      '"use client";\nimport { Button, ButtonProps } from "./button.js";\nexport { Button, ButtonProps };',
    "package/dist/internal/size.d.ts":
      '"use client";\n//#region src/internal/size.d.ts\n/** A size. */\ntype Size = "sm" | "md";\n//#endregion\nexport { Size };\n//# sourceMappingURL=size.d.ts.map',
    "package/dist/internal/size.d.ts.map": sourceMap("size.d.ts", "../../src/internal/size.ts"),
    "package/dist/styles/propel.css": "@theme {}\n",
    ...overrides,
  };
  const entries = Object.entries(files)
    .filter(([, content]) => content !== null)
    .map(([path, content]) => [path, content]);
  const tarball = makeTarball(entries);
  return { tarball, integrity: sriSha512(tarball) };
}
