/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// React Router's default Node server entry, plus the Content-Security-Policy.
// Space renders on the server with per-request loader data inlined into the
// page, so its inline scripts cannot be allowed by a build-time hash; each
// response gets a fresh nonce that React Router puts on every script it emits.

import { randomBytes } from "node:crypto";
import { PassThrough } from "node:stream";

import type { EntryContext, RouterContextProvider } from "react-router";
import { createReadableStreamFromReadable } from "@react-router/node";
import { ServerRouter } from "react-router";
import { isbot } from "isbot";
import type { RenderToPipeableStreamOptions } from "react-dom/server";
import { renderToPipeableStream } from "react-dom/server";
import {
  RUNTIME_STYLE_ELEMENTS,
  buildContentSecurityPolicy,
  hashSource,
  policyHeaderName,
  runtimeSourcesFromEnv,
  trustedTypesModeFromEnv,
  trustedTypesReportPolicy,
} from "@plane/csp";

export const streamTimeout = 5_000;

// The environment the server was started with. `define` in vite.config.ts
// replaces every `process.env` in the bundle, server code included, with the
// VITE_* values known at build time, so the deployment's variables are only
// visible through globalThis. Every @plane/csp call below is given this object
// explicitly for the same reason: its default parameter is `process.env`.
const runtimeEnv = (): Record<string, string | undefined> =>
  (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env ?? {};

// A public board can be embedded; by default only by the instance itself.
// HANGAR_SPACE_FRAME_ANCESTORS lists the origins allowed to frame it.
const frameAncestors = (env: Record<string, string | undefined>) =>
  env.HANGAR_SPACE_FRAME_ANCESTORS?.trim() || "'self'";

const contentSecurityPolicy = (nonce: string, env: Record<string, string | undefined>) =>
  buildContentSecurityPolicy({
    ...runtimeSourcesFromEnv(env),
    scriptSources: [`'nonce-${nonce}'`],
    styleElementSources: RUNTIME_STYLE_ELEMENTS.map(hashSource),
    frameAncestors: frameAncestors(env),
  });

export default function handleRequest(
  request: Request,
  responseStatusCode: number,
  responseHeaders: Headers,
  routerContext: EntryContext,
  _loadContext: RouterContextProvider
) {
  const env = runtimeEnv();
  const nonce = randomBytes(16).toString("base64");
  responseHeaders.set(policyHeaderName(env), contentSecurityPolicy(nonce, env));
  // Trusted Types measurement: its own policy, always report-only, appended so
  // it sits beside a report-only main policy instead of replacing it.
  const trustedTypes = trustedTypesReportPolicy({
    reportUri: runtimeSourcesFromEnv(env).reportUri,
    mode: trustedTypesModeFromEnv(env),
  });
  if (trustedTypes) responseHeaders.append("Content-Security-Policy-Report-Only", trustedTypes);

  // https://httpwg.org/specs/rfc9110.html#HEAD
  if (request.method.toUpperCase() === "HEAD") {
    return new Response(null, {
      status: responseStatusCode,
      headers: responseHeaders,
    });
  }

  return new Promise((resolve, reject) => {
    let shellRendered = false;
    const userAgent = request.headers.get("user-agent");

    // Ensure requests from bots and SPA Mode renders wait for all content to load before responding
    const readyOption: keyof RenderToPipeableStreamOptions =
      (userAgent && isbot(userAgent)) || routerContext.isSpaMode ? "onAllReady" : "onShellReady";

    // Abort the rendering stream after the `streamTimeout` so it has time to
    // flush down the rejected boundaries
    let timeoutId: ReturnType<typeof setTimeout> | undefined = setTimeout(() => abort(), streamTimeout + 1000);

    const { pipe, abort } = renderToPipeableStream(
      <ServerRouter context={routerContext} url={request.url} nonce={nonce} />,
      {
        nonce,
        [readyOption]() {
          shellRendered = true;
          const body = new PassThrough({
            final(callback) {
              // Clear the timeout to prevent retaining the closure and memory leak
              clearTimeout(timeoutId);
              timeoutId = undefined;
              callback();
            },
          });
          const stream = createReadableStreamFromReadable(body);

          responseHeaders.set("Content-Type", "text/html");

          pipe(body);

          resolve(
            new Response(stream, {
              headers: responseHeaders,
              status: responseStatusCode,
            })
          );
        },
        onShellError(error: unknown) {
          reject(error);
        },
        onError(error: unknown) {
          responseStatusCode = 500;
          // Log streaming rendering errors from inside the shell. Don't log
          // errors encountered during initial shell rendering since they'll
          // reject and get logged in handleDocumentRequest.
          if (shellRendered) {
            console.error(error);
          }
        },
      }
    );
  });
}
