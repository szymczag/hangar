/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): filter sub-work items by their custom type.

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { WorkItemsOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
// components
import { FilterSubmenu } from "@/components/common/filters/filter-submenu";
// plane web
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";

type Props = {
  appliedFilters: string[] | null;
  handleUpdate: (val: string) => void;
  /** The parent work item's project, whose types are offered. */
  projectId: string | undefined;
};

/**
 * The "Work item type" row of a filters menu: one checkable value per active
 * type of the project. Renders nothing while the project has none, as before.
 */
export const FilterIssueTypes = observer(function FilterIssueTypes(props: Props) {
  const { appliedFilters, handleUpdate, projectId } = props;
  // router
  const { workspaceSlug } = useParams();
  // plane hooks
  const { t } = useTranslation();
  // data
  const { issueTypes } = useIssueTypes(workspaceSlug?.toString(), projectId);
  // derived values
  const options = (issueTypes ?? [])
    .filter((type) => type.is_active)
    .map((type) => ({
      value: type.id,
      label: type.name,
      icon: <WorkItemsOutline className="h-3.5 w-3.5 text-tertiary" aria-hidden="true" />,
    }));

  if (options.length === 0) return null;

  return (
    <FilterSubmenu
      label={t("issue.display.properties.issue_type")}
      options={options}
      appliedFilters={appliedFilters}
      onToggle={handleUpdate}
      searchable
    />
  );
});
