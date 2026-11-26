/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { EventEmitter } from "node:events";
import { OutgoingMessage } from "@hocuspocus/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminCommand, CloseCode, ForceCloseReason } from "@/types/admin-commands";

vi.mock("@/redis", async () => {
  const { EventEmitter: Emitter } = await import("node:events");
  const createClient = (): EventEmitter =>
    Object.assign(new Emitter(), {
      options: { db: 0 },
      duplicate: () => createClient(),
      publish: () => Promise.resolve(1),
      subscribe: () => Promise.resolve(1),
      unsubscribe: () => Promise.resolve(1),
      disconnect: () => undefined,
    });
  return { redisManager: { getClient: () => createClient() } };
});

const { loggerError } = vi.hoisted(() => ({ loggerError: vi.fn() }));
vi.mock("@plane/logger", () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: loggerError, debug: vi.fn() },
}));

import { Redis } from "@/extensions/redis";

// ioredis hands each message over in its own buffer. An exact-size copy reproduces the case where the bytes after
// the message are not readable, which is where the decoder throws instead of reading neighbouring memory.
const exactBuffer = (value: string | Uint8Array) => {
  const source = typeof value === "string" ? Buffer.from(value) : value;
  const buffer = Buffer.alloc(source.byteLength);
  buffer.set(source);
  return buffer;
};

const deliver = (redis: Redis, channel: string, message: Buffer) => {
  const sub = redis.sub as unknown as EventEmitter;
  const listeners = sub.listeners("messageBuffer") as ((channel: Buffer, data: Buffer) => Promise<void>)[];
  return Promise.all(listeners.map((listener) => listener(Buffer.from(channel), message)));
};

describe("Redis extension subscriber", () => {
  beforeEach(() => loggerError.mockClear());

  it("does not decode admin commands as Yjs document messages", async () => {
    const redis = new Redis();
    const documents = { get: vi.fn() };
    redis.instance = { documents } as unknown as Redis["instance"];
    const command = JSON.stringify({
      command: AdminCommand.FORCE_CLOSE,
      docId: "1b478680-6ae3-4573-a715-e3aeda03adf3",
      reason: ForceCloseReason.DOCUMENT_TOO_LARGE,
      code: CloseCode.DOCUMENT_TOO_LARGE,
      originServer: "d45afb5ddf98",
      timestamp: "2026-11-26T07:13:00.130Z",
    });

    await expect(deliver(redis, "hocuspocus:admin", exactBuffer(command))).resolves.toBeDefined();
    expect(documents.get).not.toHaveBeenCalled();
    expect(loggerError).not.toHaveBeenCalled();
  });

  it("still hands document channel messages to Hocuspocus", async () => {
    const redis = new Redis();
    const documents = { get: vi.fn() };
    redis.instance = { documents } as unknown as Redis["instance"];
    const message = new OutgoingMessage("page-id").writeBroadcastStateless("{}").toUint8Array();

    await deliver(redis, "hocuspocus:page-id", Buffer.concat([Buffer.from([0]), Buffer.from(message)]));
    expect(documents.get).toHaveBeenCalledWith("page-id");
  });

  it("logs and drops a malformed document message instead of rejecting", async () => {
    const redis = new Redis();
    redis.instance = { documents: { get: vi.fn() } } as unknown as Redis["instance"];

    await expect(deliver(redis, "hocuspocus:page-id", exactBuffer("\u0000v"))).resolves.toBeDefined();
    expect(loggerError).toHaveBeenCalledWith(
      expect.stringContaining("Dropped an undecodable message on hocuspocus:page-id"),
      expect.any(RangeError)
    );
  });
});
