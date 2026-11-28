/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Cause, HashMap, Logger } from "effect";
import type { LogLevel } from "effect";
import { logger } from "@plane/logger";

const WINSTON_LEVELS: Record<LogLevel.Literal, string> = {
  All: "silly",
  Trace: "silly",
  Debug: "debug",
  Info: "info",
  Warning: "warn",
  Error: "error",
  Fatal: "error",
  None: "silly",
};

/**
 * Effect logger that writes through the shared winston logger, so Effect's log lines (the PDF export) get the same
 * JSON shape and the same credential redaction as every other live log line. `Effect.log("message", data)` becomes
 * the entry's message and a `details` field.
 */
export const winstonEffectLogger = Logger.make(({ logLevel, message, annotations, cause }) => {
  const parts = Array.isArray(message) ? message : [message];
  const [first, ...rest] = parts;
  const text = typeof first === "string" ? first : "";
  const details = typeof first === "string" ? rest : parts;

  const entry: Record<string, unknown> = { level: WINSTON_LEVELS[logLevel._tag], message: text };
  if (details.length === 1) entry.details = details[0];
  else if (details.length > 1) entry.details = details;
  if (HashMap.size(annotations) > 0) entry.annotations = Object.fromEntries(annotations);
  if (!Cause.isEmpty(cause)) entry.cause = Cause.pretty(cause);

  logger.log(entry as { level: string; message: string });
});

/** Replaces Effect's default console logger with `winstonEffectLogger`. */
export const WinstonEffectLoggerLive = Logger.replace(Logger.defaultLogger, winstonEffectLogger);
