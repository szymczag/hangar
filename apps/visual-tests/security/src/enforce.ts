/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readFileSync } from "node:fs";
import { expect, test, type BrowserContext, type Page, type TestInfo } from "@playwright/test";
import { TRUSTED_TYPES_MEASUREMENT } from "@plane/csp";
import { TRUSTED_TYPES_META_NAME, type TTrustedTypesMode } from "@plane/csp/trusted-types";

type TViolation = { directive: string; disposition: string; blocked: string; sample: string; source: string };
export type TObservation = Record<string, string>;

/**
 * The policy a frontend image sends, from the template its build produced,
 * with the deployment variables at their same-origin defaults.
 */
const builtPolicy = (app: "web" | "admin") =>
  /add_header \$\{HANGAR_CSP_HEADER\} "([^"]+)"/
    .exec(
      readFileSync(new URL(`../../../${app}/build/csp/security-headers.conf.template`, import.meta.url), "utf8")
    )![1]
    .replace("${HANGAR_CSP_FRAME_SRC}", "'none'")
    .replace(/\$\{HANGAR_CSP_[A-Z_]+\}/g, "");

/** The Trusted Types mode of the running project ("report" or "enforce"). */
export const trustedTypesMode = (): TTrustedTypesMode =>
  (test.info().project.metadata as { trustedTypes?: TTrustedTypesMode }).trustedTypes ?? "report";

const META = new RegExp(`(<meta name="${TRUSTED_TYPES_META_NAME}" content=")[a-z]*(")`);

/**
 * Which requests are routed at all: anything that can be a document. Routing
 * every request made a page's many module requests wait on the suite, and
 * Chromium failed some with ERR_INSUFFICIENT_RESOURCES.
 */
const mayBeDocument = (url: URL) =>
  !/^\/(api|live|uploads)\//.test(url.pathname) &&
  !/\.(js|mjs|css|map|json|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|txt|webmanifest)$/.test(url.pathname);

/**
 * Enforces, on every document the context loads, the application's policy and
 * Trusted Types (the measurement policy's directives, enforced instead of
 * reported). Web and admin get the policy their build generated, as nginx
 * would send it; space keeps the one its server sent (enforced on vr-space).
 * The Trusted Types header is added as a second policy in the same header,
 * and the page is told the mode through its meta tag, as nginx and space do.
 */
export async function enforceContentSecurityPolicy(context: BrowserContext) {
  const policies = { web: builtPolicy("web"), admin: builtPolicy("admin") };
  const mode = trustedTypesMode();
  await context.route(mayBeDocument, async (route) => {
    const request = route.request();
    if (request.resourceType() !== "document") return route.fallback();
    const path = new URL(request.url()).pathname;
    // The browser follows redirects itself, as it would without the suite: a
    // form post's redirect is what form-action is checked against, and the
    // document it leads to must get the policy of the app it belongs to.
    const response = await route.fetch({ maxRedirects: 0 });
    const headers = response.headers();
    let policy: string;
    if (path.startsWith("/spaces")) {
      policy = headers["content-security-policy"];
      expect(policy, "space sends an enforced policy of its own").toContain("'nonce-");
    } else {
      policy = policies[path.startsWith("/god-mode") ? "admin" : "web"];
    }
    const body = (await response.text()).replace(META, `$1${mode}$2`);
    await route.fulfill({
      response,
      body,
      headers: {
        // The edge's report-only Trusted Types header is replaced by the
        // enforced one, in the same header as the policy.
        ...Object.fromEntries(
          Object.entries(headers).filter(([name]) => name !== "content-security-policy-report-only")
        ),
        "content-security-policy": `${policy}, ${TRUSTED_TYPES_MEASUREMENT}`,
      },
    });
  });
  await context.addInitScript(() => {
    const store: unknown[] = [];
    (window as unknown as { __cspViolations: unknown[] }).__cspViolations = store;
    document.addEventListener("securitypolicyviolation", (event) => {
      store.push({
        directive: event.effectiveDirective,
        disposition: event.disposition,
        blocked: event.blockedURI,
        sample: event.sample,
        source: `${event.sourceFile}:${event.lineNumber}:${event.columnNumber}`,
      });
    });
  });
}

const isPolicyError = (text: string) => /Trusted ?Type|TrustedHTML|TrustedScript|Content Security Policy/i.test(text);

export const readViolations = (page: Page) =>
  page.evaluate(() => (window as unknown as { __cspViolations?: TViolation[] }).__cspViolations ?? []);

// What the page reported so far, attached to a failed test: a page that never
// renders has to say whether the policy stopped it or it was only slow.
const diagnostics = new WeakMap<Page, () => Record<string, unknown>>();

export async function attachDiagnostics(page: Page, testInfo: TestInfo) {
  if (testInfo.status === testInfo.expectedStatus) return;
  const collected = diagnostics.get(page)?.() ?? {};
  const violations = await readViolations(page).catch((error: Error) => `unreadable: ${error.message}`);
  await testInfo.attach("csp-diagnostics", {
    body: JSON.stringify({ url: page.url(), violations, ...collected }, null, 2),
    // Plain text, which the list reporter prints: CI logs show it inline.
    contentType: "text/plain",
  });
}

/** What a page reports while it is used. */
export function watch(page: Page) {
  const policyErrors: string[] = [];
  const observations: TObservation[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  diagnostics.set(page, () => ({ policyErrors, observations, pageErrors, failedRequests }));
  page.on("pageerror", (error) => {
    pageErrors.push(error.message);
    if (isPolicyError(error.message)) policyErrors.push(`pageerror: ${error.message}`);
  });
  page.on("requestfailed", (request) => {
    failedRequests.push(`${request.failure()?.errorText ?? "failed"} ${request.url()}`);
  });
  page.on("console", (message) => {
    if (message.type() === "error" && isPolicyError(message.text())) policyErrors.push(message.text());
  });
  page.on("request", (request) => {
    if (!request.url().includes("/api/csp-report/")) return;
    try {
      const report = JSON.parse(request.postData() ?? "{}")["csp-report"] ?? {};
      if (report["effective-directive"] === "trusted-types-default-policy") observations.push(report);
    } catch {
      observations.push({ unparsed: request.postData() ?? "" });
    }
  });
  return {
    observations,
    /** No violation, enforced or reported, and no Trusted Types error. */
    async expectNoViolations() {
      const violations = await readViolations(page);
      expect(violations, "Content-Security-Policy / Trusted Types violations").toEqual([]);
      expect(policyErrors, "Trusted Types or CSP errors in the page").toEqual([]);
    },
    /** The above, on a page the suite served: its policies and mode in place. */
    async expectClean() {
      await this.expectNoViolations();
      expect(
        await page.evaluate(
          () =>
            (window as unknown as { trustedTypes?: { defaultPolicy?: { name: string } } }).trustedTypes?.defaultPolicy
              ?.name
        ),
        "the default Trusted Types policy is installed"
      ).toBe("default");
      // Without this a page that lost its meta tag would run the enforce
      // project in report mode, and pass.
      expect(
        await page.evaluate(
          (name) => document.head.querySelector(`meta[name="${name}"]`)?.getAttribute("content"),
          TRUSTED_TYPES_META_NAME
        ),
        "the page was told the Trusted Types mode under test"
      ).toBe(trustedTypesMode());
    },
  };
}
