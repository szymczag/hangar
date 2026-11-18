/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

const getInstanceInfo = vi.fn();
const getMemberInstanceInfo = vi.fn();

vi.mock("@/services/instance.service", () => ({
  InstanceService: class {
    getInstanceInfo = getInstanceInfo;
    getMemberInstanceInfo = getMemberInstanceInfo;
  },
}));

const { InstanceStore } = await import("./instance.store");

describe("InstanceStore", () => {
  beforeEach(() => {
    getInstanceInfo.mockReset();
    getMemberInstanceInfo.mockReset();
  });

  it("adds what a signed-in user is told to the public answer, keeping the public keys", async () => {
    getInstanceInfo.mockResolvedValue({
      config: { enable_signup: false, branding_name: "Corp", product: { name: "Hangar" } },
      instance: { is_setup_done: true, workspaces_exist: true },
    });
    getMemberInstanceInfo.mockResolvedValue({
      config: {
        enable_signup: false,
        branding_name: "Corp",
        default_workspace_id: "ws-1",
        product: { name: "Hangar", version: "0.1.0-rc.99" },
      },
      instance: { is_setup_done: true, current_version: "0.1.0-rc.99" },
    });
    const store = new InstanceStore();

    await store.fetchInstanceInfo();
    expect(store.config?.default_workspace_id).toBeUndefined();

    await store.fetchMemberInstanceInfo();
    expect(store.config?.default_workspace_id).toBe("ws-1");
    expect(store.config?.product.version).toBe("0.1.0-rc.99");
    expect(store.config?.branding_name).toBe("Corp");
    expect(store.instance?.current_version).toBe("0.1.0-rc.99");
    expect(store.instance?.workspaces_exist).toBe(true);
  });

  it("leaves the public answer in place when the member request fails", async () => {
    getInstanceInfo.mockResolvedValue({ config: { branding_name: "Corp" }, instance: { is_setup_done: true } });
    getMemberInstanceInfo.mockRejectedValue(new Error("offline"));
    const store = new InstanceStore();

    await store.fetchInstanceInfo();
    await expect(store.fetchMemberInstanceInfo()).rejects.toThrow("offline");
    expect(store.config?.branding_name).toBe("Corp");
  });
});
