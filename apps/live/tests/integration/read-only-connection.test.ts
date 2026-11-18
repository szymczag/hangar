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

// Only the API boundary is replaced: the real onAuthenticate decides each socket's access from that socket's
// own cookie, and the real Hocuspocus 3 server enforces it (FORK.md, "Security invariants", S19).
const { currentUser, getPageAccess } = vi.hoisted(() => ({ currentUser: vi.fn(), getPageAccess: vi.fn() }));
vi.mock("@/services/user.service", () => ({
  UserService: class {
    currentUser = currentUser;
    getPageAccess = getPageAccess;
  },
}));

import { onAuthenticate } from "@/lib/auth";
import { onStateless } from "@/lib/stateless";

const PAGE_ID = "22222222-2222-4222-8222-222222222222";

const bodyText = (document: Y.Doc) => document.getXmlFragment("default").toJSON();

describe("a read-only connection on Hocuspocus 3", () => {
  let server: Hocuspocus;
  let socket: WebSocketServer;
  let url: string;
  const providers: HocuspocusProvider[] = [];
  const documents: Y.Doc[] = [];
  const stateless = new Map<string, string[]>();

  const connect = (user: "editor" | "guest") => {
    const document = new Y.Doc();
    documents.push(document);
    stateless.set(user, []);
    const provider = new HocuspocusProvider({
      url,
      name: PAGE_ID,
      document,
      token: JSON.stringify({ id: user, cookie: `session=${user}` }),
      onStateless: ({ payload }) => stateless.get(user)!.push(payload),
    });
    providers.push(provider);
    return { document, provider };
  };

  const serverDocument = () => server.documents.get(PAGE_ID)!;

  beforeAll(async () => {
    currentUser.mockImplementation((cookie: string) => Promise.resolve({ id: cookie.slice(8), display_name: "U" }));
    getPageAccess.mockImplementation((cookie: string) =>
      Promise.resolve({ project_id: "project", read_only: cookie === "session=guest" })
    );

    server = new Hocuspocus({
      quiet: true,
      onAuthenticate,
      onStateless,
      // The page starts with one paragraph, as if loaded from the API.
      onLoadDocument: ({ document }) => {
        const paragraph = new Y.XmlElement("paragraph");
        paragraph.insert(0, [new Y.XmlText("Original")]);
        document.getXmlFragment("default").insert(0, [paragraph]);
        return Promise.resolve(document);
      },
    });
    socket = new WebSocketServer({ host: "127.0.0.1", port: 0 });
    socket.on("connection", (ws, request) => server.handleConnection(ws, request));
    await once(socket, "listening");
    const { port } = socket.address() as { port: number };
    url = `ws://127.0.0.1:${port}/?documentType=project_page&workspaceSlug=ws`;
  });

  afterAll(async () => {
    for (const provider of providers) provider.destroy();
    for (const document of documents) document.destroy();
    for (const client of socket.clients) client.terminate();
    await new Promise<void>((resolve) => socket.close(() => resolve()));
  });

  it("drops a guest's update while an editor on the same page stays writable", async () => {
    const editor = connect("editor");
    const guest = connect("guest");
    await vi.waitFor(() => expect(editor.provider.isSynced && guest.provider.isSynced).toBe(true), {
      timeout: 10_000,
    });
    expect(getPageAccess).toHaveBeenCalledWith("session=guest", "ws", PAGE_ID, "view");
    expect(bodyText(guest.document)).toContain("Original");

    // The guest edits its local copy; the server must refuse it and keep it from the editor.
    const guestText = (guest.document.getXmlFragment("default").get(0) as Y.XmlElement).get(0) as Y.XmlText;
    guestText.insert(0, "guest edit ");

    // The editor's own change is applied and reaches the guest, which proves the guest's update had its turn.
    const editorText = (editor.document.getXmlFragment("default").get(0) as Y.XmlElement).get(0) as Y.XmlText;
    editorText.insert(editorText.length, " editor edit");
    await vi.waitFor(() => expect(bodyText(guest.document)).toContain("editor edit"));
    await vi.waitFor(() => expect(bodyText(serverDocument())).toContain("editor edit"));

    expect(bodyText(serverDocument())).not.toContain("guest edit");
    expect(bodyText(editor.document)).not.toContain("guest edit");
    expect(guest.provider.hasUnsyncedChanges).toBe(true);
  });

  it("does not relay a page event from the guest, but relays the editor's", async () => {
    const [editor, guest] = providers;
    guest.sendStateless("lock");
    editor.sendStateless("unlock");
    await vi.waitFor(() => expect(stateless.get("guest")).toContain("unlocked"));
    expect(stateless.get("editor")).not.toContain("locked");
    expect(stateless.get("guest")).not.toContain("locked");
  });
});
