/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { onStatelessPayload } from "@hocuspocus/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@plane/editor/lib", () => ({
  DocumentCollaborativeEvents: { lock: { client: "locked" } },
}));

import { onStateless } from "@/lib/stateless";

const send = (readOnly: boolean) => {
  const broadcastStateless = vi.fn();
  const payload = { payload: "lock", document: { broadcastStateless }, connection: { readOnly } };
  return { run: onStateless(payload as unknown as onStatelessPayload), broadcastStateless };
};

describe("onStateless", () => {
  it("relays a page event from a writable connection", async () => {
    const { run, broadcastStateless } = send(false);
    await run;
    expect(broadcastStateless).toHaveBeenCalledWith("locked");
  });

  it("does not let a read-only connection announce page events", async () => {
    const { run, broadcastStateless } = send(true);
    await run;
    expect(broadcastStateless).not.toHaveBeenCalled();
  });
});
