// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";

const RULES = [
  { name: "product-name", pattern: /\bPlane\b/g },
  { name: "plane-domain", pattern: /(?:[\w.-]+\.)?plane\.so\b/gi },
  { name: "upstream-repository", pattern: /github\.com\/makeplane(?:\/|\b)/gi },
  { name: "plane-email", pattern: /[\w.+-]+@plane\.so\b/gi },
];

const TEXT_FILE = /(?:^|\/)(?:[^/.]+|.*\.(?:cjs|css|env|html|js|json|jsx|md|mjs|py|sh|svg|ts|tsx|txt|yaml|yml))$/i;

function isAllowed(allowlist, file, line, rule) {
  return allowlist.some((entry) => {
    if (!entry.rules.includes(rule)) return false;
    if (!new RegExp(entry.pathPattern).test(file)) return false;
    return !entry.linePattern || new RegExp(entry.linePattern).test(line);
  });
}

export function findViolationsInText(file, content, allowlist = []) {
  const violations = [];

  for (const [index, line] of content.split(/\r?\n/).entries()) {
    for (const rule of RULES) {
      rule.pattern.lastIndex = 0;
      if (rule.pattern.test(line) && !isAllowed(allowlist, file, line, rule.name)) {
        violations.push({ file, line: index + 1, rule: rule.name, text: line.trim() });
      }
    }
  }

  return violations;
}

export function checkBranding({ cwd = process.cwd(), files = [], allowlist } = {}) {
  const resolvedAllowlist =
    allowlist ?? JSON.parse(readFileSync(new URL("./branding-allowlist.json", import.meta.url), "utf8"));
  return files
    .filter((file) => TEXT_FILE.test(file))
    .flatMap((file) => {
      try {
        return findViolationsInText(file, readFileSync(`${cwd}/${file}`, "utf8"), resolvedAllowlist);
      } catch {
        return [];
      }
    });
}

const invokedPath = process.argv[1] ? pathToFileURL(process.argv[1]).href : "";
if (import.meta.url === invokedPath) {
  const files = process.argv.includes("--stdin")
    ? readFileSync(0, "utf8").split("\n").filter(Boolean)
    : process.argv.slice(2);
  const violations = checkBranding({ files });
  if (violations.length > 0) {
    for (const violation of violations) {
      console.error(`${violation.file}:${violation.line} [${violation.rule}] ${violation.text}`);
    }
    console.error(`Found ${violations.length} disallowed upstream branding reference(s).`);
    process.exitCode = 1;
  } else {
    console.log("Branding check passed.");
  }
}
