/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import { Search, X } from "lucide-react";
// Hangar imports
import { EUserPermissions } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { Input } from "@plane/ui";
// hooks
import { useProject } from "@/hooks/store/use-project";

type Props = {
  onSelect: (projectId: string) => void;
  onCancel: () => void;
};

/**
 * Choose an existing project to start a new one from.
 *
 * Only projects the user administers are offered, because that is what the
 * duplicate endpoint requires: the copy re-links the source's custom work item
 * types, and a type can be edited by an admin of any project linking it.
 */
export const ProjectSourcePicker = observer(function ProjectSourcePicker(props: Props) {
  const { onSelect, onCancel } = props;
  const [query, setQuery] = useState("");
  const { t } = useTranslation();
  const { joinedProjectIds, getProjectById } = useProject();

  const candidates = useMemo(() => {
    const term = query.trim().toLowerCase();
    return joinedProjectIds
      .map((id) => getProjectById(id))
      .filter((project) => !!project && !project.archived_at && project.member_role === EUserPermissions.ADMIN)
      .filter((project) => !term || `${project!.name} ${project!.identifier}`.toLowerCase().includes(term));
  }, [joinedProjectIds, getProjectById, query]);

  return (
    <div className="flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-16 font-medium text-primary">{t("start_from_an_existing_project")}</h3>
        <button type="button" onClick={onCancel} aria-label={t("cancel")} className="text-placeholder">
          <X className="size-4" />
        </button>
      </div>

      <p className="text-13 text-secondary">{t("choose_a_project_to_copy")}</p>

      <div className="relative">
        <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-placeholder" />
        <Input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("search")}
          className="w-full pl-8"
          autoComplete="off"
        />
      </div>

      <div className="max-h-72 overflow-y-auto">
        {candidates.length === 0 ? (
          <p className="py-6 text-center text-13 text-placeholder">{t("no_projects_to_copy")}</p>
        ) : (
          candidates.map((project) => (
            <button
              key={project!.id}
              type="button"
              onClick={() => onSelect(project!.id)}
              className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left hover:bg-layer-1"
            >
              <span className="grid size-5 flex-shrink-0 place-items-center">
                <Logo logo={project!.logo_props} size={16} />
              </span>
              <span className="truncate text-13 text-primary">{project!.name}</span>
              <span className="ml-auto flex-shrink-0 text-11 text-placeholder">{project!.identifier}</span>
            </button>
          ))
        )}
      </div>

      <div className="flex justify-end">
        <Button variant="secondary" size="sm" onClick={onCancel}>
          {t("cancel")}
        </Button>
      </div>
    </div>
  );
});
