/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback } from "react";
// plane types
import type { TSearchEntities } from "@plane/types";
// helpers
import { getEditorAssetSrc, parseInertHTML } from "@plane/utils";
import type { TCustomComponentsMetaData } from "@plane/utils";
// hooks
import { useMember } from "@/hooks/store/use-member";
// plane web hooks
import { useAdditionalEditorMention } from "@/hooks/use-additional-editor-mention";

type TArgs = {
  projectId?: string;
  workspaceSlug: string;
};

export const useParseEditorContent = (args: TArgs) => {
  const { projectId, workspaceSlug } = args;
  // store hooks
  const { getUserDetails } = useMember();
  // parse additional content
  const { parseAdditionalEditorContent } = useAdditionalEditorMention({
    enableAdvancedMentions: true,
  });

  /**
   * @description function to replace all the custom components from the markdown content
   * @param props
   * @returns {string}
   */
  const replaceCustomComponentsFromMarkdownContent = useCallback(
    (props: { markdownContent: string; noAssets?: boolean }): string => {
      const { markdownContent, noAssets = false } = props;
      let parsedMarkdownContent = markdownContent;
      // replace the matched mention components with [display_name](redirect_url)
      const mentionRegex =
        /<mention-component[^>]*entity_identifier="([^"]+)"[^>]*entity_name="([^"]+)"[^>]*><\/mention-component>/g;
      const originUrl = typeof window !== "undefined" && (window.location.origin ?? "");
      parsedMarkdownContent = parsedMarkdownContent.replace(mentionRegex, (_match, id, entity_type) => {
        const entityType = entity_type as TSearchEntities;
        if (!id || !entityType) return "";
        if (entityType === "user_mention") {
          const userDetails = getUserDetails(id);
          if (!userDetails) return "";
          return `[${userDetails.display_name}](${originUrl}/${workspaceSlug}/profile/${id})`;
        } else {
          const mentionDetails = parseAdditionalEditorContent({
            id,
            entityType,
          });
          if (!mentionDetails) {
            return "";
          } else {
            const { redirectionPath, textContent } = mentionDetails;
            return `[${textContent}](${originUrl}/${redirectionPath})`;
          }
        }
      });
      // replace the matched image components with <img src={src} >
      const imageComponentRegex = /<image-component[^>]*src="([^"]+)"[^>]*>[^]*<\/image-component>/g;
      const imgTagRegex = /<img[^>]*src="([^"]+)"[^>]*\/?>/g;
      if (noAssets) {
        // remove all image components
        parsedMarkdownContent = parsedMarkdownContent.replace(imageComponentRegex, "").replace(imgTagRegex, "");
      } else {
        // replace the matched image components with <img src={src} >
        parsedMarkdownContent = parsedMarkdownContent.replace(
          imageComponentRegex,
          (_match, src) => `<img src="${src}" >`
        );
      }
      // remove all issue-embed components
      const issueEmbedRegex = /<issue-embed-component[^>]*>[^]*<\/issue-embed-component>/g;
      parsedMarkdownContent = parsedMarkdownContent.replace(issueEmbedRegex, "");
      return parsedMarkdownContent;
    },
    [getUserDetails, parseAdditionalEditorContent, workspaceSlug]
  );

  const getEditorMetaData = useCallback(
    (htmlContent: string): TCustomComponentsMetaData => {
      const doc = parseInertHTML(htmlContent);
      const filesMetaData: TCustomComponentsMetaData["file_assets"] = [];
      // process image components
      const imageComponents = doc.querySelectorAll("image-component");
      imageComponents.forEach((element) => {
        const src = element.getAttribute("src");
        if (src) {
          const assetSrc = src.startsWith("http")
            ? src
            : getEditorAssetSrc({
                assetId: src,
                projectId,
                workspaceSlug,
              });
          if (assetSrc) {
            filesMetaData.push({
              id: src,
              name: src,
              url: assetSrc,
            });
          }
        }
      });
      // process user mentions
      const userMentions: TCustomComponentsMetaData["user_mentions"] = [];
      const mentionComponents = doc.querySelectorAll("mention-component");
      mentionComponents.forEach((element) => {
        const id = element.getAttribute("entity_identifier");
        if (id) {
          const userDetails = getUserDetails(id);
          const originUrl = typeof window !== "undefined" && (window.location.origin ?? "");
          const path = `${workspaceSlug}/profile/${id}`;
          const url = `${originUrl}/${path}`;
          if (userDetails) {
            userMentions.push({
              id,
              display_name: userDetails.display_name,
              url,
            });
          }
        }
      });

      return {
        file_assets: filesMetaData,
        user_mentions: userMentions,
      };
    },
    [getUserDetails, projectId, workspaceSlug]
  );

  return {
    replaceCustomComponentsFromMarkdownContent,
    getEditorMetaData,
  };
};
