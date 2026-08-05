/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it, vi } from "vitest";
import { env } from "@/env";
import { requireSecretKey } from "@/lib/auth-middleware";

vi.hoisted(() => {
  process.env.API_BASE_URL = "http://api.test";
  process.env.LIVE_SERVER_SECRET_KEY = "unit-test-live-secret";
});

const request = (secret?: string) =>
  ({
    headers: secret ? { "live-server-secret-key": secret } : {},
    path: "/convert-document/",
    method: "POST",
    ip: "127.0.0.1",
  }) as never;

const response = () => {
  const json = vi.fn();
  const status = vi.fn(() => ({ json }));
  return { value: { status } as never, status, json };
};

describe("requireSecretKey", () => {
  it("allows the configured Live shared secret", () => {
    const res = response();
    const next = vi.fn();

    requireSecretKey(request(env.LIVE_SERVER_SECRET_KEY), res.value, next);

    expect(next).toHaveBeenCalledOnce();
    expect(res.status).not.toHaveBeenCalled();
  });

  it("rejects missing and invalid secrets", () => {
    for (const secret of [undefined, "incorrect-secret"]) {
      const res = response();
      const next = vi.fn();
      requireSecretKey(request(secret), res.value, next);
      expect(next).not.toHaveBeenCalled();
      expect(res.status).toHaveBeenCalledWith(401);
    }
  });
});
