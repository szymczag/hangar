/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import {
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogHeading,
  DialogMain,
  DialogTitle,
} from "@makeplane/propel/components/dialog";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { InputField } from "@makeplane/propel/components/input-field";
import { DeleteOutline, EditOutline } from "@makeplane/propel/icons";
import { ConfirmDialog } from "@plane/blocks/dialog";
import { setToast } from "@plane/blocks/toast";
import { EUserPermissions } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { renderFormattedDate } from "@plane/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useMember } from "@/hooks/store/use-member";
import { useUser, useUserPermissions } from "@/hooks/store/user";
// plane web
import {
  MAX_WORKLOG_DESCRIPTION_LENGTH,
  MAX_WORKLOG_MINUTES,
  formatWorklogDuration,
  parseWorklogDuration,
} from "@/plane-web/helpers/worklog";
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
  canViewWorklogs: boolean;
};

function validateDurationInput(input: string): number | null {
  const minutes = parseWorklogDuration(input);
  if (minutes === null || minutes > MAX_WORKLOG_MINUTES) return null;
  return minutes;
}

export const WorklogModal = observer(function WorklogModal(props: TWorklogModal) {
  const { isOpen, onClose, workspaceSlug, projectId, issueId, disabled = false, canViewWorklogs } = props;
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
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  // store hooks
  const { data: currentUser } = useUser();
  const { getUserDetails } = useMember();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const { fetchActivities } = useIssueDetail();
  // derived values
  const { worklogs, totalDuration, isLoading, mutate } = useWorklogs(
    workspaceSlug,
    projectId,
    issueId,
    isOpen && canViewWorklogs
  );
  const isAdmin = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId) === EUserPermissions.ADMIN;

  const canModify = (worklog: TIssueWorklog) => !disabled && (isAdmin || worklog.logged_by === currentUser?.id);

  if (!canViewWorklogs) return <></>;

  const refresh = async () => {
    await mutate();
    fetchActivities(workspaceSlug, projectId, issueId, "mutate").catch(() => {});
  };

  const handleClose = () => {
    setDurationInput("");
    setDescription("");
    setEditingId(null);
    setPendingDeleteId(null);
    onClose();
  };

  const handleCreate = async () => {
    const minutes = validateDurationInput(durationInput);
    if (minutes === null) {
      setToast({
        type: "error",
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
      setToast({ type: "error", title: "Error!", message: "Failed to log time." });
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
        type: "error",
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
      setToast({ type: "error", title: "Error!", message: "Failed to update the entry." });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (worklogId: string) => {
    setIsSubmitting(true);
    try {
      await worklogService.deleteWorklog(workspaceSlug, projectId, issueId, worklogId);
      setPendingDeleteId(null);
      await refresh();
    } catch (error) {
      console.error(error);
      setToast({ type: "error", title: "Error!", message: "Failed to delete the entry." });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <ConfirmDialog
        isOpen={pendingDeleteId !== null}
        handleClose={() => setPendingDeleteId(null)}
        handleSubmit={async () => {
          if (pendingDeleteId) await handleDelete(pendingDeleteId);
        }}
        isSubmitting={isSubmitting}
        title="Delete worklog"
        content="Are you sure you want to delete this time entry? This action cannot be undone."
      />
      <Dialog
        open={isOpen}
        onOpenChange={(open) => {
          if (!open) handleClose();
        }}
      >
        <DialogContent size="lg">
          <DialogMain>
            <DialogHeader>
              <DialogHeading>
                <DialogTitle>{t("time_tracking")}</DialogTitle>
                <DialogDescription>
                  {t("common.worklogs")}:{" "}
                  <span className="text-body-sm-medium text-primary">{formatWorklogDuration(totalDuration)}</span>
                </DialogDescription>
              </DialogHeading>
            </DialogHeader>
            <DialogBody>
              <div className="flex flex-col gap-4">
                {!disabled && (
                  <div className="flex items-end gap-2">
                    <div className="w-28 shrink-0">
                      <InputField
                        size="md"
                        orientation="vertical"
                        aria-label="Duration"
                        value={durationInput}
                        onChange={(e) => setDurationInput(e.target.value)}
                        placeholder="2h 30m"
                      />
                    </div>
                    <div className="min-w-0 grow">
                      <InputField
                        size="md"
                        orientation="vertical"
                        aria-label="Description"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="What was done? (optional)"
                        maxLength={MAX_WORKLOG_DESCRIPTION_LENGTH}
                      />
                    </div>
                    <Button
                      variant="primary"
                      size="md"
                      stretch="auto"
                      label="Log time"
                      onClick={() => void handleCreate()}
                      loading={isSubmitting}
                    />
                  </div>
                )}

                <div className="flex max-h-72 flex-col gap-1 overflow-y-auto">
                  {!isLoading && worklogs.length === 0 && (
                    <p className="py-4 text-center text-body-sm-regular text-tertiary">
                      {t("activity_empty_state.no_worklogs")}
                    </p>
                  )}
                  {worklogs.map((worklog) => {
                    const author = worklog.logged_by ? getUserDetails(worklog.logged_by) : undefined;
                    const isEditing = editingId === worklog.id;
                    return (
                      <div
                        key={worklog.id}
                        className="group flex items-center gap-2 rounded-md border border-subtle px-3 py-2 text-body-sm-regular"
                      >
                        {isEditing ? (
                          <>
                            <div className="w-28 shrink-0">
                              <InputField
                                size="md"
                                orientation="vertical"
                                aria-label="Duration"
                                value={editDurationInput}
                                onChange={(e) => setEditDurationInput(e.target.value)}
                                placeholder="2h 30m"
                              />
                            </div>
                            <div className="min-w-0 grow">
                              <InputField
                                size="md"
                                orientation="vertical"
                                aria-label="Description"
                                value={editDescription}
                                onChange={(e) => setEditDescription(e.target.value)}
                                placeholder="What was done? (optional)"
                                maxLength={MAX_WORKLOG_DESCRIPTION_LENGTH}
                              />
                            </div>
                            <Button
                              variant="primary"
                              size="md"
                              stretch="auto"
                              label="Save"
                              onClick={() => void handleUpdate(worklog.id)}
                              loading={isSubmitting}
                            />
                            <Button
                              variant="secondary"
                              size="md"
                              stretch="auto"
                              label="Cancel"
                              onClick={() => setEditingId(null)}
                              disabled={isSubmitting}
                            />
                          </>
                        ) : (
                          <>
                            <span className="w-20 shrink-0 text-body-sm-medium text-primary">
                              {formatWorklogDuration(worklog.duration)}
                            </span>
                            <span className="grow truncate text-secondary">{worklog.description}</span>
                            <span className="shrink-0 text-caption-md-regular text-tertiary">
                              {author?.display_name ?? "—"} · {renderFormattedDate(worklog.created_at)}
                            </span>
                            {canModify(worklog) && (
                              <span className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
                                <IconButton
                                  variant="ghost"
                                  size="sm"
                                  icon={<Icon icon={EditOutline} />}
                                  aria-label="Edit worklog"
                                  onClick={() => startEditing(worklog)}
                                  disabled={isSubmitting}
                                />
                                <IconButton
                                  variant="ghost"
                                  size="sm"
                                  icon={<Icon icon={DeleteOutline} />}
                                  aria-label="Delete worklog"
                                  onClick={() => setPendingDeleteId(worklog.id)}
                                  disabled={isSubmitting}
                                />
                              </span>
                            )}
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </DialogBody>
          </DialogMain>
          <DialogActions>
            <Button variant="secondary" size="md" stretch="auto" label="Close" onClick={handleClose} />
          </DialogActions>
        </DialogContent>
      </Dialog>
    </>
  );
});
