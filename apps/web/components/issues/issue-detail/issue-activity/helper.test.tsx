/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * An image pasted into a comment that is not saved yet has no comment to belong
 * to. It used to be uploaded with an empty entity_identifier, which the asset API
 * refuses with 400, so the paste failed (#518). It is now uploaded under the work
 * item the comment is written on and bound to the comment once that is created;
 * a saved comment still names itself.
 */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { TCommentsOperations } from "@plane/types";

const state = vi.hoisted(() => ({
  uploadEditorAsset: vi.fn(),
  duplicateEditorAsset: vi.fn(),
}));

vi.mock("@plane/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("@plane/blocks/toast", () => ({ setToast: vi.fn() }));
vi.mock("@plane/utils", () => ({
  copyUrlToClipboard: vi.fn(),
  formatTextList: vi.fn(),
  generateWorkItemLink: vi.fn(),
}));
vi.mock("@plane/types", () => ({ EFileAssetType: { COMMENT_DESCRIPTION: "COMMENT_DESCRIPTION" } }));
vi.mock("@/hooks/store/use-editor-asset", () => ({
  useEditorAsset: () => ({
    uploadEditorAsset: state.uploadEditorAsset,
    duplicateEditorAsset: state.duplicateEditorAsset,
  }),
}));
vi.mock("@/hooks/store/use-issue-detail", () => ({
  useIssueDetail: () => ({
    commentReaction: {
      getCommentReactionsByCommentId: vi.fn(),
      commentReactionsByUser: vi.fn(),
      getCommentReactionById: vi.fn(),
    },
    createComment: vi.fn(),
    updateComment: vi.fn(),
    removeComment: vi.fn(),
    createCommentReaction: vi.fn(),
    removeCommentReaction: vi.fn(),
    issue: { getIssueById: () => undefined },
  }),
}));
vi.mock("@/hooks/store/use-member", () => ({ useMember: () => ({ getUserDetails: vi.fn() }) }));
vi.mock("@/hooks/store/use-project", () => ({ useProject: () => ({ getProjectById: () => undefined }) }));
vi.mock("@/hooks/store/user", () => ({ useUser: () => ({ data: undefined }) }));

import { commentAssetEntityId, useWorkItemCommentOperations } from "./helper";

function operationsFor(issueId: string | undefined): TCommentsOperations {
  let operations: TCommentsOperations | undefined;
  function Probe() {
    operations = useWorkItemCommentOperations("acme", "project-1", issueId);
    return null;
  }
  renderToStaticMarkup(<Probe />);
  if (!operations) throw new Error("operations were not built");
  return operations;
}

const file = new File(["png"], "pasted.png", { type: "image/png" });

describe("comment image entity", () => {
  beforeEach(() => {
    state.uploadEditorAsset.mockReset().mockResolvedValue({ asset_id: "asset-1" });
    state.duplicateEditorAsset.mockReset().mockResolvedValue({ asset_id: "asset-2" });
  });

  it("names the comment once it exists, and the work item before", () => {
    expect(commentAssetEntityId("comment-1", "issue-1")).toBe("comment-1");
    expect(commentAssetEntityId(undefined, "issue-1")).toBe("issue-1");
    expect(commentAssetEntityId("", "issue-1")).toBe("issue-1");
    expect(commentAssetEntityId(undefined, undefined)).toBeUndefined();
  });

  it("uploads an image of a new comment under its work item, never with an empty id", async () => {
    await operationsFor("issue-1").uploadCommentAsset("block-1", file);

    expect(state.uploadEditorAsset).toHaveBeenCalledWith(
      expect.objectContaining({
        projectId: "project-1",
        workspaceSlug: "acme",
        data: { entity_identifier: "issue-1", entity_type: "COMMENT_DESCRIPTION" },
      })
    );
  });

  it("uploads an image of a saved comment under the comment", async () => {
    await operationsFor("issue-1").uploadCommentAsset("block-1", file, "comment-1");

    expect(state.uploadEditorAsset).toHaveBeenCalledWith(
      expect.objectContaining({
        data: { entity_identifier: "comment-1", entity_type: "COMMENT_DESCRIPTION" },
      })
    );
  });

  it("duplicates an image into a new comment under its work item", async () => {
    await operationsFor("issue-1").duplicateCommentAsset("source-asset");

    expect(state.duplicateEditorAsset).toHaveBeenCalledWith(
      expect.objectContaining({ assetId: "source-asset", entityId: "issue-1", entityType: "COMMENT_DESCRIPTION" })
    );
  });

  it("refuses to upload when there is nothing to anchor the image to", async () => {
    await expect(operationsFor(undefined).uploadCommentAsset("block-1", file)).rejects.toThrow();
    expect(state.uploadEditorAsset).not.toHaveBeenCalled();
  });
});
