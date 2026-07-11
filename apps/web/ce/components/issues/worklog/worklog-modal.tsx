/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Pencil, Trash2 } from "lucide-react";
// plane imports
import { EUserPermissions } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { EModalPosition, EModalWidth, Input, ModalCore } from "@plane/ui";
import { renderFormattedDate } from "@plane/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useMember } from "@/hooks/store/use-member";
import { useUser, useUserPermissions } from "@/hooks/store/user";
// plane web
import { MAX_WORKLOG_MINUTES, formatWorklogDuration, parseWorklogDuration } from "@/plane-web/helpers/worklog";
import { useWorklogs } from "@/plane-web/hooks/use-worklogs";
import { worklogService } from "@/plane-web/services/worklog.service";
import type { TIssueWorklog } from "@/plane-web/types/worklog";

type TWorklogModal = {
  isOpen: boolean;
  onClose: () => void;
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  disabled?: boolean;
};

function validateDurationInput(input: string): number | null {
  const minutes = parseWorklogDuration(input);
  if (minutes === null || minutes > MAX_WORKLOG_MINUTES) return null;
  return minutes;
}

export const WorklogModal = observer(function WorklogModal(props: TWorklogModal) {
  const { isOpen, onClose, workspaceSlug, projectId, issueId, disabled = false } = props;
  // i18n
  const { t } = useTranslation();
  // state — add form
  const [durationInput, setDurationInput] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  // state — inline edit
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDurationInput, setEditDurationInput] = useState("");
  const [editDescription, setEditDescription] = useState("");
  // store hooks
  const { data: currentUser } = useUser();
  const { getUserDetails } = useMember();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const { fetchActivities } = useIssueDetail();
  // derived values
  const { worklogs, totalDuration, mutate } = useWorklogs(workspaceSlug, projectId, issueId, isOpen);
  const isAdmin = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId) === EUserPermissions.ADMIN;

  const canModify = (worklog: TIssueWorklog) => !disabled && (isAdmin || worklog.logged_by === currentUser?.id);

  const refresh = async () => {
    await mutate();
    fetchActivities(workspaceSlug, projectId, issueId, "mutate").catch(() => {});
  };

  const handleClose = () => {
    setDurationInput("");
    setDescription("");
    setEditingId(null);
    onClose();
  };

  const handleCreate = async () => {
    const minutes = validateDurationInput(durationInput);
    if (minutes === null) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Invalid duration",
        message: 'Use a format like "2h 30m", "45m" or plain minutes, up to 24h.',
      });
      return;
    }
    setIsSubmitting(true);
    try {
      await worklogService.createWorklog(workspaceSlug, projectId, issueId, {
        duration: minutes,
        description: description.trim(),
      });
      setDurationInput("");
      setDescription("");
      await refresh();
    } catch (error) {
      console.error(error);
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Failed to log time." });
    } finally {
      setIsSubmitting(false);
    }
  };

  const startEditing = (worklog: TIssueWorklog) => {
    setEditingId(worklog.id);
    setEditDurationInput(formatWorklogDuration(worklog.duration));
    setEditDescription(worklog.description ?? "");
  };

  const handleUpdate = async (worklogId: string) => {
    const minutes = validateDurationInput(editDurationInput);
    if (minutes === null) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Invalid duration",
        message: 'Use a format like "2h 30m", "45m" or plain minutes, up to 24h.',
      });
      return;
    }
    setIsSubmitting(true);
    try {
      await worklogService.updateWorklog(workspaceSlug, projectId, issueId, worklogId, {
        duration: minutes,
        description: editDescription.trim(),
      });
      setEditingId(null);
      await refresh();
    } catch (error) {
      console.error(error);
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Failed to update the entry." });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (worklogId: string) => {
    setIsSubmitting(true);
    try {
      await worklogService.deleteWorklog(workspaceSlug, projectId, issueId, worklogId);
      await refresh();
    } catch (error) {
      console.error(error);
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Failed to delete the entry." });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={handleClose} position={EModalPosition.TOP} width={EModalWidth.XL}>
      <div className="space-y-4 p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-medium text-primary">{t("time_tracking")}</h3>
          <span className="text-sm text-tertiary">
            {t("common.worklogs")}:{" "}
            <span className="font-medium text-primary">{formatWorklogDuration(totalDuration)}</span>
          </span>
        </div>

        {!disabled && (
          <div className="flex items-start gap-2">
            <Input
              value={durationInput}
              onChange={(e) => setDurationInput(e.target.value)}
              placeholder="2h 30m"
              className="w-28"
            />
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What was done? (optional)"
              className="grow"
            />
            <Button variant="primary" size="sm" onClick={handleCreate} loading={isSubmitting} disabled={isSubmitting}>
              Log time
            </Button>
          </div>
        )}

        <div className="max-h-72 space-y-1 overflow-y-auto">
          {worklogs.length === 0 && (
            <p className="text-sm py-4 text-center text-tertiary">{t("activity_empty_state.no_worklogs")}</p>
          )}
          {worklogs.map((worklog) => {
            const author = worklog.logged_by ? getUserDetails(worklog.logged_by) : undefined;
            const isEditing = editingId === worklog.id;
            return (
              <div
                key={worklog.id}
                className="group text-sm flex items-center gap-2 rounded-md border border-subtle px-3 py-2"
              >
                {isEditing ? (
                  <>
                    <Input
                      value={editDurationInput}
                      onChange={(e) => setEditDurationInput(e.target.value)}
                      placeholder="2h 30m"
                      className="w-28"
                    />
                    <Input
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      placeholder="What was done? (optional)"
                      className="grow"
                    />
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleUpdate(worklog.id)}
                      loading={isSubmitting}
                      disabled={isSubmitting}
                    >
                      Save
                    </Button>
                    <Button variant="secondary" size="sm" onClick={() => setEditingId(null)} disabled={isSubmitting}>
                      Cancel
                    </Button>
                  </>
                ) : (
                  <>
                    <span className="w-20 shrink-0 font-medium text-primary">
                      {formatWorklogDuration(worklog.duration)}
                    </span>
                    <span className="grow truncate text-secondary">{worklog.description}</span>
                    <span className="text-xs shrink-0 text-tertiary">
                      {author?.display_name ?? "—"} · {renderFormattedDate(worklog.created_at)}
                    </span>
                    {canModify(worklog) && (
                      <span className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                        <button
                          type="button"
                          onClick={() => startEditing(worklog)}
                          className="rounded p-1 text-tertiary hover:bg-layer-1 hover:text-primary"
                          aria-label="Edit worklog"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(worklog.id)}
                          className="rounded p-1 text-tertiary hover:bg-layer-1 hover:text-danger-primary"
                          aria-label="Delete worklog"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </span>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </div>

        <div className="flex justify-end">
          <Button variant="secondary" size="sm" onClick={handleClose}>
            Close
          </Button>
        </div>
      </div>
    </ModalCore>
  );
});
