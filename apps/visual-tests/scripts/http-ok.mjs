#!/usr/bin/env node
// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only
// See the LICENSE file for details.

/**
 * Container healthcheck for the Node services of the VR stack: exits 0 when
 * the URL answers 2xx. A file rather than an inline `node -e`, because
 * podman-compose rewrites a CMD healthcheck into a shell string and loses the
 * quoting of anything with parentheses.
 */
const response = await fetch(process.argv[2]).catch(() => undefined);
process.exit(response?.ok ? 0 : 1);
