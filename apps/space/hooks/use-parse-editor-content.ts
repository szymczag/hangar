/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback } from "react";
// helpers
import { parseInertHTML } from "@plane/utils";
import type { TCustomComponentsMetaData } from "@plane/utils";
// helpers
import { getEditorAssetSrc } from "@/helpers/editor.helper";

type TArgs = {
  anchor: string;
};

export const useParseEditorContent = (args: TArgs) => {
  const { anchor } = args;

  const getEditorMetaData = useCallback(
    (htmlContent: string): TCustomComponentsMetaData => {
      const doc = parseInertHTML(htmlContent);
      const imageMetaData: TCustomComponentsMetaData["file_assets"] = [];
      // process image components
      const imageComponents = doc.querySelectorAll("image-component");
      imageComponents.forEach((element) => {
        const src = element.getAttribute("src");
        if (src) {
          const assetSrc = src.startsWith("http") ? src : getEditorAssetSrc(anchor, src);
          if (assetSrc) {
            imageMetaData.push({
              id: src,
              name: src,
              url: assetSrc,
            });
          }
        }
      });
      // User mentions are not resolved to names: a published board does not publish the
      // project's members (FORK.md, S30), so an exported mention carries no name.
      return {
        file_assets: imageMetaData,
        user_mentions: [],
      };
    },
    [anchor]
  );

  return {
    getEditorMetaData,
  };
};
