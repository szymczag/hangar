/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { assetDuplicationHandlers } from "@/plane-editor/helpers/asset-duplication";

// Clipboard HTML is parsed into a DOMParser document, never assigned to
// `innerHTML` of an element created with `document.createElement`. Such an
// element belongs to the live document even while detached, so
// `<img src=x onerror=...>` would load and run its handler before the schema
// ever filters the paste. A DOMParser document has no browsing context:
// nothing loads and no handler runs.
const parseInertBody = (html: string): HTMLElement => new DOMParser().parseFromString(html, "text/html").body;

// Utility function to process HTML content with all registered handlers
export const processAssetDuplication = (htmlContent: string): { processedHtml: string } => {
  let inertBody = parseInertBody(htmlContent);

  let processedHtml = htmlContent;

  // Process each registered component type
  for (const [componentName, handler] of Object.entries(assetDuplicationHandlers)) {
    const elements = inertBody.querySelectorAll(componentName);

    if (elements.length > 0) {
      elements.forEach((element) => {
        const result = handler({ element, originalHtml: processedHtml });
        if (result.shouldProcess) {
          processedHtml = result.modifiedHtml;
        }
      });

      // Re-parse the processed HTML for the next iteration
      inertBody = parseInertBody(processedHtml);
    }
  }

  return { processedHtml };
};
