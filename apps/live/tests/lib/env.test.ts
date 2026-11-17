/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

vi.hoisted(() => {
  process.env.API_BASE_URL = "http://api.test";
  process.env.LIVE_SERVER_SECRET_KEY = "unit-test-live-secret";
});

const original = { ...process.env };

// env.ts validates on import and exits on failure; load it afresh with the
// given environment and report whether it tried to exit.
const load = async (overrides: Record<string, string | undefined>) => {
  vi.resetModules();
  process.env = { ...original, ...overrides };
  const exit = vi.spyOn(process, "exit").mockImplementation((() => {
    throw new Error("process.exit");
  }) as never);
  const error = vi.spyOn(console, "error").mockImplementation(() => undefined);
  try {
    await import("@/env");
    return { exited: false, message: "" };
  } catch {
    return { exited: exit.mock.calls.length > 0, message: String(error.mock.calls[0]?.[0] ?? "") };
  }
};

// The module itself, loaded with a valid environment.
const envModule = async () => {
  vi.resetModules();
  process.env = { ...original };
  return import("@/env");
};

afterEach(() => {
  process.env = { ...original };
  vi.restoreAllMocks();
});

describe("LIVE_SERVER_SECRET_KEY", () => {
  it("starts with a real secret", async () => {
    expect((await load({ LIVE_SERVER_SECRET_KEY: "a-long-random-value-0123456789" })).exited).toBe(false);
  });

  it.each(["", "  ", "change-this-key-on-deployment", "secret-key", "htbqvBJAgpm9bzvf3r4urJer0ENReatceh"])(
    "refuses the empty or template secret %j",
    async (secret) => {
      const result = await load({ LIVE_SERVER_SECRET_KEY: secret });
      expect(result.exited).toBe(true);
      expect(result.message).toContain("LIVE_SERVER_SECRET_KEY");
    }
  );

  it("refuses a missing secret", async () => {
    expect((await load({ LIVE_SERVER_SECRET_KEY: undefined })).exited).toBe(true);
  });

  it("lists the values the templates shipped", async () => {
    const { INSECURE_LIVE_SERVER_SECRET_KEYS } = await envModule();
    expect(INSECURE_LIVE_SERVER_SECRET_KEYS).toEqual(
      expect.arrayContaining(["change-this-key-on-deployment", "secret-key"])
    );
  });

  it("lets a development stack opt out, and only with exactly 1", async () => {
    expect((await load({ LIVE_SERVER_SECRET_KEY: "secret-key", HANGAR_ALLOW_INSECURE_DEFAULTS: "1" })).exited).toBe(
      false
    );
    expect((await load({ LIVE_SERVER_SECRET_KEY: "secret-key", HANGAR_ALLOW_INSECURE_DEFAULTS: "true" })).exited).toBe(
      true
    );
  });
});
