/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { AxiosAdapter } from "axios";
import { AxiosError } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { APIService } from "./api.service";

class TestService extends APIService {
  constructor() {
    super("http://api.test");
  }
}

const unauthorized: AxiosAdapter = async (config) => {
  const response = { data: {}, status: 401, statusText: "Unauthorized", headers: {}, config };
  throw new AxiosError("Unauthorized", AxiosError.ERR_BAD_REQUEST, config, null, response);
};

describe("APIService 401 handling", () => {
  const replace = vi.fn();

  const setPath = (pathname: string) => {
    vi.stubGlobal("window", { location: { pathname, replace } });
  };

  beforeEach(() => {
    replace.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends a private route to sign-in with its path as next_path", async () => {
    setPath("/workspace/projects/");

    await expect(new TestService().get("/users/me/", {}, { adapter: unauthorized })).rejects.toBeInstanceOf(AxiosError);

    expect(replace).toHaveBeenCalledWith("/?next_path=%2Fworkspace%2Fprojects%2F");
  });

  it("encodes reserved characters in next_path", async () => {
    setPath("/a&b=c");

    await expect(new TestService().get("/users/me/", {}, { adapter: unauthorized })).rejects.toThrow();

    expect(replace).toHaveBeenCalledWith("/?next_path=%2Fa%26b%3Dc");
  });

  // The entry page fetches the current user on mount. Redirecting it to
  // itself on that 401 reloaded the page forever instead of showing sign-in.
  it("does not redirect the entry page to itself", async () => {
    setPath("/");

    await expect(new TestService().get("/users/me/", {}, { adapter: unauthorized })).rejects.toThrow();

    expect(replace).not.toHaveBeenCalled();
  });
});
