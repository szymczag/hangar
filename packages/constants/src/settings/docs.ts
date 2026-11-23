/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Help-center pages that settings headings link to with a "Docs" button.
 *
 * Fork (see FORK.md): upstream points every entry at its own hosted help
 * center. Hangar ships no per-topic help pages, and a link there would send
 * people to a third party's site, so every entry is empty and the settings
 * headings render no "Docs" button. `SettingsDocsLink` is also gated by
 * `showExternalLinks`, so a value added here later stays behind the switch.
 */
export const SETTINGS_DOCS_URLS: Record<
  "exports" | "webhooks" | "states" | "labels" | "estimates" | "cycles" | "modules" | "views" | "pages" | "intake",
  string
> = {
  // workspace
  exports: "",
  webhooks: "",
  // project
  states: "",
  labels: "",
  estimates: "",
  cycles: "",
  modules: "",
  views: "",
  pages: "",
  intake: "",
};
