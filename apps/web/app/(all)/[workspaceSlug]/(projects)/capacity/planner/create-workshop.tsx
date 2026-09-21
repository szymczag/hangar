// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CreateUpdateIssueModal } from "@/components/issues/issue-modal/modal";
import { useProject } from "@/hooks/store/use-project";
import { issueTypeService } from "@/plane-web/services/issue-type.service";
import { CapacityService } from "@/services/capacity.service";
import type { TPlanIssue } from "@/services/capacity.service";

const capacityService = new CapacityService();

/**
 * Give a brand-new workshop the subtasks its workspace always wants.
 *
 * Best effort on purpose. A workspace with no default template answers 404, and
 * a workshop without a checklist is a perfectly good workshop -- neither is a
 * reason to fail the creation the person actually asked for. Only a partial
 * result is worth interrupting them about, because an assignee the template
 * names but the project cannot hold is something only they can fix.
 */
async function applyDefaultChecklist(workspaceSlug: string, projectId: string, issueId: string) {
  try {
    const result = await capacityService.applyChecklist(workspaceSlug, projectId, issueId);
    if (result.skipped_assignees.length > 0) {
      setToast({
        type: TOAST_TYPE.WARNING,
        title: "Checklist added, some assignees skipped",
        message: "Some people named by the template cannot be assigned work in this project.",
      });
    }
  } catch {
    // No default template, or the feature is off. Nothing to say.
  }
}

export const CreateWorkshop = observer(function CreateWorkshop({
  workspaceSlug,
  title,
  disabled,
  onCreated,
}: {
  workspaceSlug: string;
  title: string;
  disabled: boolean;
  onCreated: (issue: TPlanIssue) => void;
}) {
  const { joinedProjectIds, getProjectById } = useProject();
  const [projectId, setProjectId] = useState("");
  const [open, setOpen] = useState(false);
  const { data: types, error } = useSWR(projectId ? ["planner-workshop-types", workspaceSlug, projectId] : null, () =>
    issueTypeService.getIssueTypes(workspaceSlug, projectId)
  );
  const workshop = types?.find((type) => type.system_key === "workshop");
  return (
    <div className="space-y-2">
      <label className="block text-body-xs-medium">
        Create a new workshop in
        <select
          aria-label="Workshop project"
          disabled={disabled}
          value={projectId}
          onChange={(event) => setProjectId(event.target.value)}
          className="mt-1 h-9 w-full rounded border border-subtle bg-surface-1 px-2"
        >
          <option value="">Choose a project</option>
          {joinedProjectIds.map((id) => (
            <option key={id} value={id}>
              {getProjectById(id)?.name}
            </option>
          ))}
        </select>
      </label>
      <Button variant="secondary" size="sm" disabled={disabled || !workshop} onClick={() => setOpen(true)}>
        Create workshop
      </Button>
      {error && (
        <p role="alert" className="text-body-xs-regular text-danger-primary">
          Workshop types could not be loaded. Choose the project again to retry.
        </p>
      )}
      {projectId && types && !workshop && (
        <p className="text-body-xs-regular text-secondary">
          This project does not offer Workshops. A project administrator can turn them on in the project&apos;s work
          item type settings.
        </p>
      )}
      {open && workshop && (
        <CreateUpdateIssueModal
          isOpen
          onClose={() => setOpen(false)}
          isProjectSelectionDisabled
          allowedProjectIds={[projectId]}
          modalTitle="Create workshop"
          data={{ name: title, project_id: projectId, type_id: workshop.id }}
          onSubmit={async (issue) => {
            await applyDefaultChecklist(workspaceSlug, projectId, issue.id);
            onCreated({
              id: issue.id,
              name: issue.name,
              sequence_id: issue.sequence_id,
              project_id: projectId,
              project_identifier: getProjectById(projectId)?.identifier ?? "",
            });
            setOpen(false);
          }}
        />
      )}
    </div>
  );
});
