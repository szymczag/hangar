/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { LoggerOptions, Logform } from "winston";
import { createLogger, format, transports } from "winston";
import { redactFormat } from "./redact";

// Redaction runs first, so no later format or transport ever sees a cookie, token or authorization value.
export const logFormat: Logform.Format = format.combine(
  redactFormat(),
  format.timestamp({
    format: "YYYY-MM-DD HH:mm:ss:ms",
  }),
  format.json()
);

export const loggerConfig: LoggerOptions = {
  level: process.env.LOG_LEVEL || "info",
  format: logFormat,
  transports: [new transports.Console()],
};

export const logger = createLogger(loggerConfig);
