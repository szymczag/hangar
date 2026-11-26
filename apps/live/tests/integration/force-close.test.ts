/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { once } from "node:events";
import { HocuspocusProvider } from "@hocuspocus/provider";
import { Hocuspocus } from "@hocuspocus/server";
import { WebSocketServer } from "ws";
import * as Y from "yjs";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { logger } from "@plane/logger";
import { Database } from "@/extensions/database";
import { drainCollaborationServer } from "@/lib/drain-server";

const TOO_LARGE = "11111111-1111-4111-8111-111111111111";
const HEALTHY = "22222222-2222-4222-8222-222222222222";

// No Redis: this server runs alone, as a single live replica does.
vi.mock("@/redis", () => ({ redisManager: { getClient: () => null } }));

// Only the API boundary is replaced: the store of one page is refused with 413, as the API does for an oversized
// description, while the other page stores normally.
const api = vi.hoisted(() => ({ saved: new Set<string>() }));
vi.mock("@/services/page/handler", () => ({
  getPageService: () => ({
    fetchDescriptionBinary: () => Promise.resolve(new Uint8Array()),
    fetchDetails: () => Promise.resolve({ name: "", description_html: "<p></p>" }),
    updateDescriptionBinary: (id: string) => {
      if (id !== TOO_LARGE) {
        api.saved.add(id);
        return Promise.resolve();
      }
      return Promise.reject(
        Object.assign(new Error("Request failed with status code 413"), {
          isAxiosError: true,
          response: { status: 413, data: {} },
        })
      );
    },
  }),
}));

const write = (document: Y.Doc, text: string) => {
  const paragraph = new Y.XmlElement("paragraph");
  paragraph.insert(0, [new Y.XmlText(text)]);
  document.getXmlFragment("default").insert(0, [paragraph]);
};

describe("a store refused as too large", () => {
  let server: Hocuspocus;
  let socket: WebSocketServer;
  let url: string;
  const providers: HocuspocusProvider[] = [];
  const documents: Y.Doc[] = [];
  const notices = new Map<string, string[]>();

  const connect = (name: string) => {
    const document = new Y.Doc();
    documents.push(document);
    notices.set(name, []);
    const provider = new HocuspocusProvider({
      url,
      name,
      document,
      token: "test-token",
      onStateless: ({ payload }) => notices.get(name)!.push(payload),
    });
    providers.push(provider);
    return { document, provider };
  };

  beforeAll(async () => {
    server = new Hocuspocus({
      quiet: true,
      onAuthenticate: () =>
        Promise.resolve({ documentType: "project_page", workspaceSlug: "w", projectId: "p", userId: "u" }),
      debounce: 20,
      maxDebounce: 100,
      extensions: [new Database()],
    });
    socket = new WebSocketServer({ host: "127.0.0.1", port: 0 });
    socket.on("connection", (ws, request) => server.handleConnection(ws, request));
    await once(socket, "listening");
    url = `ws://127.0.0.1:${(socket.address() as { port: number }).port}`;
  });

  afterAll(async () => {
    for (const provider of providers) provider.destroy();
    for (const document of documents) document.destroy();
    try {
      await drainCollaborationServer(server, 10_000);
    } finally {
      for (const client of socket.clients) client.terminate();
      await new Promise<void>((resolve) => socket.close(() => resolve()));
    }
  });

  it("closes the page, unloads it once the store finishes, and leaves other pages alone", async () => {
    const errors = vi.spyOn(logger, "error");
    const tooLarge = connect(TOO_LARGE);
    const healthy = connect(HEALTHY);
    await vi.waitFor(() => expect(tooLarge.provider.isSynced && healthy.provider.isSynced).toBe(true), {
      timeout: 10_000,
    });
    // The client would reconnect after the close; the page is gone for it, as in the browser.
    tooLarge.provider.configuration.websocketProvider.shouldConnect = false;

    write(tooLarge.document, "Too large to save");
    write(healthy.document, "Saved normally");

    await vi.waitFor(() => expect(server.documents.has(TOO_LARGE)).toBe(false), { timeout: 10_000 });
    expect(notices.get(TOO_LARGE)!.map((notice) => JSON.parse(notice))).toContainEqual(
      expect.objectContaining({ type: "force_close", code: 4001 })
    );
    expect(errors).not.toHaveBeenCalledWith(expect.stringContaining("Document still in memory"));

    expect(server.documents.has(HEALTHY)).toBe(true);
    expect(healthy.provider.isSynced).toBe(true);
    await vi.waitFor(() => expect(api.saved.has(HEALTHY)).toBe(true));
    expect(notices.get(HEALTHY)).toEqual([]);
  });
});
