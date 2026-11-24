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
import { Select } from "@plane/blocks/select";
import type { EditorRefApi } from "@plane/editor";
// types
import type { TBulkIssueProperties, TIssue } from "@plane/types";
// components
import { IssueTypeIdentifier } from "@/components/issues/issue-detail/issue-identifier";
// plane web
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";
import type { TIssueTypeExt } from "@/plane-web/types/issue-types";

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

  return (
    <Controller
      control={control}
      name={"type_id" as Path<T>}
      render={({ field: { value, onChange } }) => {
        const selected = availableTypes.find((type) => type.id === value) ?? null;
        return (
          <Select<TIssueTypeExt>
            getValues={() => availableTypes}
            value={selected}
            onChange={(next) => {
              onChange(next as PathValue<T, Path<T>>);
              handleFormChange?.();
            }}
            getOptionValue={(type) => type.id}
            getOptionLabel={(type) => type.name}
            getOptionIcon={(type) => <IssueTypeIdentifier issueTypeId={type.id} projectId={projectId} size="xs" />}
            disabled={disabled}
            placeholder={placeholder || "Work item type"}
            // A handful of types the user picks by name: keep their order, search only when long.
            pinSelected={false}
            showSearch={availableTypes.length > 7}
          >
            <Select.Trigger<TIssueTypeExt>
              variant="pill-md"
              disabled={disabled}
              data-testid="create-work-item-type-select"
              prependIcon={(types) =>
                types[0] ? <IssueTypeIdentifier issueTypeId={types[0].id} projectId={projectId} size="xs" /> : undefined
              }
            >
              {(types) => (
                <span className="min-w-0 grow truncate text-left">
                  {types[0]?.name ?? (placeholder || "Work item type")}
                </span>
              )}
            </Select.Trigger>
          </Select>
        );
      }}
    />
  );
}
