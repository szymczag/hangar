/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { ensureAPITrailingSlash, normalizeAPIRequestURL } from "./url";

describe("ensureAPITrailingSlash", () => {
  it.each([
    ["/api/foo", "/api/foo/"],
    ["/api/foo/", "/api/foo/"],
    ["/api/foo?x=1", "/api/foo/?x=1"],
    ["/api/foo#frag", "/api/foo/#frag"],
    ["", ""],
    ["/", "/"],
    ["/api/foo/?x=1", "/api/foo/?x=1"],
    ["https://h/api/foo", "https://h/api/foo/"],
  ])("turns %j into %j", (input, expected) => {
    expect(ensureAPITrailingSlash(input)).toBe(expected);
  });
});

describe("normalizeAPIRequestURL", () => {
  it("leaves signed upload URLs unchanged when baseURL is empty", () => {
    const signedUrl = "https://bucket.s3.amazonaws.com/path?X-Amz-Signature=abc";
    expect(normalizeAPIRequestURL(signedUrl, "")).toBe(signedUrl);
  });

  it("leaves signed upload URLs unchanged when origin is not the API baseURL", () => {
    const signedUrl = "https://bucket.s3.amazonaws.com/path?X-Amz-Signature=abc";
    expect(normalizeAPIRequestURL(signedUrl, "https://api.plane.so")).toBe(signedUrl);
  });

  it("leaves already-slashed relative Django paths unchanged", () => {
    expect(normalizeAPIRequestURL("/api/assets/v2/workspaces/acme/", "https://api.plane.so")).toBe(
      "/api/assets/v2/workspaces/acme/"
    );
  });

  it("adds a trailing slash to relative Django paths", () => {
    expect(normalizeAPIRequestURL("/api/assets/v2/workspaces/acme", "https://api.plane.so")).toBe(
      "/api/assets/v2/workspaces/acme/"
    );
  });

  it("adds a trailing slash to same-origin absolute Django URLs", () => {
    expect(normalizeAPIRequestURL("https://api.plane.so/api/foo", "https://api.plane.so")).toBe(
      "https://api.plane.so/api/foo/"
    );
  });
});

describe("normalizeAPIRequestURL (Hangar guards)", () => {
  const base = "https://hangar.example.com";

  it.each([
    ["/api/workspaces/acme/stickies/1?x=1", "/api/workspaces/acme/stickies/1/?x=1"],
    ["/api/workspaces/acme/stickies/1#top", "/api/workspaces/acme/stickies/1/#top"],
    ["/api/workspace-slug-check/?slug=acme", "/api/workspace-slug-check/?slug=acme"],
    ["/api/workspaces/acme/export-issues", "/api/workspaces/acme/export-issues/"],
    ["/auth/sign-in", "/auth/sign-in/"],
  ])("slashes the API path %j as %j", (input, expected) => {
    expect(normalizeAPIRequestURL(input, base)).toBe(expected);
  });

  it.each([
    ["", base],
    ["/", base],
    ["/robots.txt", base],
    ["/static/logo.png?v=2", base],
    ["/api/assets/v2/static/report.pdf#page=2", base],
    ["https://cdn.example.org/api/foo", base],
    ["//cdn.example.org/api/foo", base],
    ["https://hangar.example.com:8443/api/foo", base],
    ["blob:https://hangar.example.com/1234", base],
    ["data:text/plain,hello", base],
    ["https://hangar.example.com/uploads?X-Amz-Signature=abc&X-Amz-Credential=key", base],
    ["/uploads/bucket/key?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=abc", base],
    ["https://storage.googleapis.com/bucket/key?X-Goog-Signature=abc", ""],
    ["https://hangar.example.com/api/foo", ""],
  ])("leaves %j unchanged (baseURL %j)", (input, baseURL) => {
    expect(normalizeAPIRequestURL(input, baseURL)).toBe(input);
  });

  it("slashes protocol-relative URLs on the API host", () => {
    expect(normalizeAPIRequestURL("//hangar.example.com/api/foo", base)).toBe("//hangar.example.com/api/foo/");
  });

  it("resolves relative paths when baseURL is empty (same-origin API)", () => {
    expect(normalizeAPIRequestURL("/api/users/api-tokens/1", "")).toBe("/api/users/api-tokens/1/");
  });

  it("does not double an existing slash before a query", () => {
    expect(normalizeAPIRequestURL("/api/foo/?a=1&b=2", base)).toBe("/api/foo/?a=1&b=2");
  });
});
