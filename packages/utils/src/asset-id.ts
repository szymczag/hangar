/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

const ASSET_ID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * @description whether a value is an asset id the API issued (a UUID). Editor
 * content is user-controlled, and an image `src` is interpolated into API
 * paths for display, delete, restore and duplicate requests; anything but a
 * UUID (e.g. `../../other/endpoint`) must never become such a path.
 * @param {unknown} value
 * @returns {boolean}
 */
export const isAssetId = (value: unknown): value is string => typeof value === "string" && ASSET_ID_REGEX.test(value);
