// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const sourcePath = path.join(repositoryRoot, "hangar-logo.png");
const sourceSha256 = "ca79c8de7379e70dddbf0391c964005fa9f033439662698035e2f4cd5b5cd3d8";
const isCheck = process.argv.includes("--check");

const lockupCrop = { left: 220, top: 159, width: 868, height: 258 };
const markCrop = { left: 220, top: 159, width: 305, height: 258 };
const brandBackdrop = "#171B26";

const appNames = ["web", "admin", "space"];
const outputs = new Map();

function addOutput(relativePath, contents) {
  outputs.set(relativePath, contents);
}

function createIco(png, size) {
  const header = Buffer.alloc(22);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(1, 4);
  header.writeUInt8(size === 256 ? 0 : size, 6);
  header.writeUInt8(size === 256 ? 0 : size, 7);
  header.writeUInt8(0, 8);
  header.writeUInt8(0, 9);
  header.writeUInt16LE(1, 10);
  header.writeUInt16LE(32, 12);
  header.writeUInt32LE(png.length, 14);
  header.writeUInt32LE(header.length, 18);
  return Buffer.concat([header, png]);
}

async function createIcon(mark, size) {
  const markWidth = Math.round(size * 0.78);
  const markHeight = Math.round(size * 0.72);
  const foreground = await sharp(mark)
    .resize({
      width: markWidth,
      height: markHeight,
      fit: "contain",
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .png({ compressionLevel: 9, adaptiveFiltering: true })
    .toBuffer();
  const radius = Math.round(size * 0.21);
  const backdrop = Buffer.from(
    `<svg width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg"><rect width="${size}" height="${size}" rx="${radius}" fill="${brandBackdrop}"/></svg>`
  );

  return sharp({
    create: { width: size, height: size, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } },
  })
    .composite([
      { input: backdrop, gravity: "center" },
      { input: foreground, gravity: "center" },
    ])
    .png({ compressionLevel: 9, adaptiveFiltering: true })
    .toBuffer();
}

async function buildOutputs() {
  const source = await readFile(sourcePath);
  const actualSourceSha256 = createHash("sha256").update(source).digest("hex");
  if (actualSourceSha256 !== sourceSha256) {
    throw new Error(`hangar-logo.png changed unexpectedly: expected ${sourceSha256}, received ${actualSourceSha256}`);
  }

  const lockup = await sharp(source)
    .extract(lockupCrop)
    .png({ compressionLevel: 9, adaptiveFiltering: true })
    .toBuffer();
  const mark = await sharp(source).extract(markCrop).png({ compressionLevel: 9, adaptiveFiltering: true }).toBuffer();

  addOutput("assets/branding/hangar-wordmark.png", lockup);
  addOutput("assets/branding/hangar-mark.png", mark);
  addOutput("packages/propel/public/hangar-wordmark.png", lockup);
  addOutput("packages/propel/public/hangar-mark.png", mark);

  for (const appName of appNames) {
    addOutput(`apps/${appName}/public/hangar-wordmark.png`, lockup);
    addOutput(`apps/${appName}/public/hangar-mark.png`, mark);
  }

  const iconSizes = [16, 32, 64, 180, 192, 240, 348, 512];
  const iconBuffers = await Promise.all(iconSizes.map((size) => createIcon(mark, size)));
  const icons = new Map(iconSizes.map((size, index) => [size, iconBuffers[index]]));

  for (const appName of appNames) {
    const assetFaviconRoot = `apps/${appName}/app/assets/favicon`;
    addOutput(`${assetFaviconRoot}/favicon-16x16.png`, icons.get(16));
    addOutput(`${assetFaviconRoot}/favicon-32x32.png`, icons.get(32));
    addOutput(`${assetFaviconRoot}/apple-touch-icon.png`, icons.get(180));
    addOutput(`${assetFaviconRoot}/favicon.ico`, createIco(icons.get(64), 64));

    const publicFaviconRoot = `apps/${appName}/public/favicon`;
    addOutput(`${publicFaviconRoot}/android-chrome-192x192.png`, icons.get(192));
    addOutput(`${publicFaviconRoot}/android-chrome-512x512.png`, icons.get(512));

    addOutput(`apps/${appName}/app/assets/images/logo-loader.png`, icons.get(64));
  }

  addOutput("apps/web/app/assets/icons/icon-180x180.png", icons.get(180));
  addOutput("apps/web/app/assets/icons/icon-512x512.png", icons.get(512));
  addOutput("apps/web/public/icons/icon-192x192.png", icons.get(192));
  addOutput("apps/web/public/icons/icon-348x348.png", icons.get(348));
  addOutput("apps/web/public/icons/icon-512x512.png", icons.get(512));
  addOutput("apps/api/plane/static/logos/Logo.png", icons.get(240));

  const ogLockup = await sharp(lockup)
    .resize({ width: 900, withoutEnlargement: false })
    .png({ compressionLevel: 9, adaptiveFiltering: true })
    .toBuffer();
  const ogImage = await sharp({
    create: { width: 1200, height: 630, channels: 4, background: brandBackdrop },
  })
    .composite([{ input: ogLockup, gravity: "center" }])
    .png({ compressionLevel: 9, adaptiveFiltering: true })
    .toBuffer();

  addOutput("assets/branding/hangar-og.png", ogImage);
  for (const appName of appNames) {
    addOutput(`apps/${appName}/public/hangar-og.png`, ogImage);
  }
}

async function writeOrCheckOutputs() {
  const results = await Promise.all(
    [...outputs].map(async ([relativePath, expected]) => {
      const outputPath = path.join(repositoryRoot, relativePath);
      if (isCheck) {
        let actual;
        try {
          actual = await readFile(outputPath);
        } catch {
          return `${relativePath} is missing`;
        }
        return actual.equals(expected) ? undefined : `${relativePath} is out of date`;
      }

      await mkdir(path.dirname(outputPath), { recursive: true });
      let current;
      try {
        current = await readFile(outputPath);
      } catch {
        current = undefined;
      }
      if (!current?.equals(expected)) await writeFile(outputPath, expected);
      return undefined;
    })
  );
  const mismatches = results.filter(Boolean);

  if (mismatches.length > 0) {
    for (const mismatch of mismatches) console.error(mismatch);
    console.error("Run `pnpm generate:brand-assets` and commit the generated files.");
    process.exitCode = 1;
    return;
  }

  console.log(isCheck ? `Verified ${outputs.size} generated brand assets.` : `Generated ${outputs.size} brand assets.`);
}

await buildOutputs();
await writeOrCheckOutputs();
