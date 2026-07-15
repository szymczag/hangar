/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): work-item type dropdown for the create/update modal,
// backed by the project's custom issue types.

import { useParams } from "next/navigation";
import type { Control, Path, PathValue } from "react-hook-form";
import { Controller } from "react-hook-form";
// plane imports
import type { EditorRefApi } from "@plane/editor";
import { CustomSearchSelect } from "@plane/ui";
// types
import type { TBulkIssueProperties, TIssue } from "@plane/types";
// plane web
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";

export type TIssueFields = TIssue & TBulkIssueProperties;

export type TIssueTypeDropdownVariant = "xs" | "sm";

export type TIssueTypeSelectProps<T extends Partial<TIssueFields>> = {
  control: Control<T>;
  projectId: string | null;
  editorRef?: React.MutableRefObject<EditorRefApi | null>;
  disabled?: boolean;
  variant?: TIssueTypeDropdownVariant;
  placeholder?: string;
  isRequired?: boolean;
  renderChevron?: boolean;
  dropDownContainerClassName?: string;
  showMandatoryFieldInfo?: boolean; // Show info about mandatory fields
  handleFormChange?: () => void;
};

export function IssueTypeSelect<T extends Partial<TIssueFields>>(props: TIssueTypeSelectProps<T>) {
  const { control, projectId, disabled = false, placeholder, handleFormChange } = props;
  // router
  const { workspaceSlug } = useParams();
  // data
  const { issueTypes } = useIssueTypes(workspaceSlug?.toString(), projectId);
  // derived values
  const availableTypes = (issueTypes ?? []).filter((type) => type.is_active);

  if (!projectId || availableTypes.length === 0) return <></>;

  const options = availableTypes.map((type) => ({
    value: type.id,
    query: type.name,
    content: type.name,
  }));

  return (
    <Controller
      control={control}
      name={"type_id" as Path<T>}
      render={({ field: { value, onChange } }) => (
        <CustomSearchSelect
          value={(value as string | null) ?? null}
          onChange={(next: string | null) => {
            onChange(next as PathValue<T, Path<T>>);
            handleFormChange?.();
          }}
          options={options}
          label={availableTypes.find((type) => type.id === value)?.name ?? (placeholder || "Work item type")}
          disabled={disabled}
          buttonClassName="h-7"
        />
      )}
    />
  );
}
