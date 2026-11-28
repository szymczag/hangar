/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Request, RequestHandler, Response } from "express";
import expressWinston from "express-winston";
import type { transport } from "winston";
import { transports } from "winston";
import { loggerConfig } from "./config";
import { SENSITIVE_HEADER_NAMES } from "./redact";

/** The only request fields a request log line carries. Query strings, bodies and most headers are left out. */
export const REQUEST_LOG_FIELDS: readonly string[] = ["method", "url", "httpVersion", "headers"];

/** The only request headers a request log line carries. Cookies and credentials are never among them. */
export const REQUEST_LOG_HEADERS: readonly string[] = ["user-agent", "content-type", "content-length"];

/** The only response fields a request log line carries. Response headers (`set-cookie`) are left out. */
export const RESPONSE_LOG_FIELDS: readonly string[] = ["statusCode"];

/** The path of a request URL without its query string or fragment, which can carry tokens. */
export const stripQueryString = (url: string | undefined): string => {
  if (!url) return "";
  const end = url.search(/[?#]/);
  return end === -1 ? url : url.slice(0, end);
};

const requestPath = (req: Request): string => stripQueryString(req.originalUrl || req.url);

/** Reads one allowlisted request field for the log entry; headers are reduced to the header allowlist. */
export const filterRequestField = (req: Request, propName: string): unknown => {
  switch (propName) {
    case "method":
      return req.method;
    case "httpVersion":
      return req.httpVersion;
    case "url":
      return requestPath(req);
    case "headers": {
      const headers: Record<string, string | string[]> = {};
      for (const name of REQUEST_LOG_HEADERS) {
        const value = req.headers?.[name];
        if (value !== undefined) headers[name] = value;
      }
      return headers;
    }
    default:
      return undefined;
  }
};

/**
 * The message line for a request. express-winston compiles a message containing `{{` as a template, so braces in a
 * client-supplied path are percent-encoded before the line is returned.
 */
export const formatRequestMessage = (req: Request, res: Response): string => {
  const responseTime = (res as Response & { responseTime?: number }).responseTime;
  const line = `${req.method} ${requestPath(req)} ${res.statusCode} ${responseTime ?? 0}ms`;
  return line.replace(/\{/g, "%7B").replace(/\}/g, "%7D");
};

export const createLoggerMiddleware = (options: { transports?: transport[] } = {}): RequestHandler =>
  expressWinston.logger({
    ...loggerConfig,
    transports: options.transports ?? [new transports.Console()],
    msg: formatRequestMessage,
    expressFormat: false,
    requestWhitelist: [...REQUEST_LOG_FIELDS],
    requestFilter: filterRequestField,
    // The header allowlist already excludes these; the blacklist keeps them out if the allowlist ever widens.
    headerBlacklist: [...SENSITIVE_HEADER_NAMES],
    responseWhitelist: [...RESPONSE_LOG_FIELDS],
    bodyWhitelist: [],
  });

export const loggerMiddleware: RequestHandler = createLoggerMiddleware();
