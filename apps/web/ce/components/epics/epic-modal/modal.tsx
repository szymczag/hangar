/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TIssue } from "@plane/types";
import { EIssuesStoreType } from "@plane/types";
import { EModalPosition, EModalWidth, Input, ModalCore, TextArea } from "@plane/ui";
import { sanitizeHTML } from "@plane/utils";
// hooks
import { useIssues } from "@/hooks/store/use-issues";
// plane web
import { epicService } from "@/plane-web/services/epic.service";

export interface EpicModalProps {
  data?: Partial<TIssue>;
  isOpen: boolean;
  onClose: () => void;
  beforeFormSubmit?: () => Promise<void>;
  onSubmit?: (res: TIssue) => Promise<void>;
  fetchIssueDetails?: boolean;
  primaryButtonText?: {
    default: string;
    loading: string;
  };
  isProjectSelectionDisabled?: boolean;
}

const descriptionToHtml = (description: string): string => {
  const escaped = description
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
  return `<p>${escaped.replaceAll("\n", "<br>")}</p>`;
};

export const CreateUpdateEpicModal = observer(function CreateUpdateEpicModal(props: EpicModalProps) {
  const { data, isOpen, onClose, beforeFormSubmit, onSubmit, primaryButtonText } = props;
  // router
  const { workspaceSlug: routerWorkspaceSlug, projectId: routerProjectId } = useParams();
  const workspaceSlug = routerWorkspaceSlug?.toString();
  const projectId = (data?.project_id ?? routerProjectId)?.toString();
  // state
  const [name, setName] = useState(data?.name ?? "");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  // store hooks
  const { issues } = useIssues(EIssuesStoreType.EPIC);
  // derived values
  const isUpdate = Boolean(data?.id);

  useEffect(() => {
    if (!isOpen) return;
    setName(data?.name ?? "");
    setDescription(sanitizeHTML(data?.description_html ?? ""));
  }, [data?.description_html, data?.id, data?.name, isOpen]);

  const handleClose = () => {
    setName("");
    setDescription("");
    onClose();
  };

  const handleSubmit = async () => {
    if (!workspaceSlug || !projectId || !name.trim()) return;
    setIsSubmitting(true);
    try {
      await beforeFormSubmit?.();
      const payload: Partial<TIssue> = { name: name.trim() };
      if (description.trim()) payload.description_html = descriptionToHtml(description.trim());
      const response =
        data?.id !== undefined
          ? await epicService.updateEpic(workspaceSlug, projectId, data.id, payload)
          : await epicService.createEpic(workspaceSlug, projectId, payload);
      await issues?.fetchIssuesWithExistingPagination?.(workspaceSlug, projectId, "mutation");
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Success!",
        message: isUpdate ? "Epic updated successfully." : "Epic created successfully.",
      });
      await onSubmit?.(response);
      handleClose();
    } catch (error) {
      console.error(error);
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error!",
        message: isUpdate ? "Failed to update the epic." : "Failed to create the epic.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={handleClose} position={EModalPosition.TOP} width={EModalWidth.XXL}>
      <div className="flex flex-col gap-4 p-5">
        <h3 className="text-18 font-medium">{isUpdate ? "Update epic" : "Create epic"}</h3>
        <Input
          id="epic-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Epic title"
          className="w-full"
        />
        <TextArea
          id="epic-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
          className="min-h-24 w-full"
        />
        <div className="flex items-center justify-end gap-2">
          <Button variant="secondary" size="base" onClick={handleClose}>
            Cancel
          </Button>
          <Button variant="primary" size="base" onClick={handleSubmit} loading={isSubmitting} disabled={!name.trim()}>
            {isSubmitting
              ? (primaryButtonText?.loading ?? "Saving")
              : (primaryButtonText?.default ?? (isUpdate ? "Update epic" : "Create epic"))}
          </Button>
        </div>
      </div>
    </ModalCore>
  );
});
