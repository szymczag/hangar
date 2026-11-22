/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getEmojiDataUrl, setEmojiDataUrl } from "./data-url";
import { EmojiRoot } from "./emoji";

// Hangar: frimousse's default data source is a public CDN, which would tell a
// third party who opens the picker and which connect-src refuses. The picker
// reads the data this instance serves, under the base path the app sets.
describe("emoji picker data source", () => {
  afterEach(() => {
    setEmojiDataUrl("/emojibase");
    vi.unstubAllGlobals();
  });

  it("defaults to this origin", () => {
    expect(getEmojiDataUrl()).toBe("/emojibase");
  });

  it("fetches the emoji data from the URL the app set, never from a CDN", async () => {
    const fetchMock = vi.fn(() => Promise.reject(new Error("offline")));
    vi.stubGlobal("fetch", fetchMock);
    setEmojiDataUrl("/spaces/emojibase");

    render(<EmojiRoot onChange={vi.fn()} />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const requested = fetchMock.mock.calls.map((call: unknown[]) => String(call[0]));
    expect(requested.every((url) => url.startsWith("/spaces/emojibase/"))).toBe(true);
  });
});
