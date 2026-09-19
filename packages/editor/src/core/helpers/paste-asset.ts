/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { assetDuplicationHandlers } from "@/plane-editor/helpers/asset-duplication";

/**
 * Parse pasted HTML somewhere nothing can run.
 *
 * Assigning clipboard HTML to `innerHTML` does not execute `<script>`, which is
 * what makes the pattern look safe. It does create elements that fetch:
 * `<img src=x onerror=…>` attempts its load and fires its handler even on an
 * element that was never inserted into the page. Inspecting the paste would
 * then be the very thing that executes it, and the clipboard flavour this reads
 * is one any page can set on a copy event.
 *
 * A document from `DOMParser` has no browsing context, so nothing loads and no
 * handler runs. `isPlainishHtml` in the markdown paste plugin already settled
 * this for the sibling paste path; the two agree now.
 */
const parseInertly = (htmlContent: string): Document => new DOMParser().parseFromString(htmlContent, "text/html");

// Utility function to process HTML content with all registered handlers
export const processAssetDuplication = (htmlContent: string): { processedHtml: string } => {
  let parsed = parseInertly(htmlContent);

  let processedHtml = htmlContent;

  // Process each registered component type
  for (const [componentName, handler] of Object.entries(assetDuplicationHandlers)) {
    const elements = parsed.body.querySelectorAll(componentName);

    if (elements.length > 0) {
      elements.forEach((element) => {
        const result = handler({ element, originalHtml: processedHtml });
        if (result.shouldProcess) {
          processedHtml = result.modifiedHtml;
        }
      });

      // Re-read the rewritten markup for the next handler. The result itself is
      // built by replacing strings in the original HTML rather than serialized
      // from this document, so parsing it inertly changes nothing but where the
      // elements live.
      parsed = parseInertly(processedHtml);
    }
  }

  return { processedHtml };
};
