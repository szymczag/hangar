/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { CustomSearchSelect, Input, ToggleSwitch } from "@plane/ui";
// components
import { MemberDropdown } from "@/components/dropdowns/member/dropdown";
// plane web
import type { TIssuePropertyExt } from "@/plane-web/types/issue-types";

type Props = {
  property: TIssuePropertyExt;
  values: string[];
  onChange: (values: string[]) => void;
  projectId: string;
  disabled?: boolean;
  hasError?: boolean;
};

export const PropertyValueInput = observer(function PropertyValueInput(props: Props) {
  const { property, values, onChange, projectId, disabled = false, hasError = false } = props;
  const value = values[0] ?? "";

  switch (property.property_type) {
    case "text":
      return (
        <Input
          id={`property-${property.id}`}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value ? [e.target.value] : [])}
          placeholder={property.display_name}
          className="w-full"
          hasError={hasError}
          disabled={disabled}
        />
      );
    case "number":
      return (
        <Input
          id={`property-${property.id}`}
          type="number"
          value={value}
          onChange={(e) => onChange(e.target.value ? [e.target.value] : [])}
          placeholder={property.display_name}
          className="w-full"
          hasError={hasError}
          disabled={disabled}
        />
      );
    case "date":
      return (
        <Input
          id={`property-${property.id}`}
          type="date"
          value={value ? value.slice(0, 10) : ""}
          onChange={(e) => onChange(e.target.value ? [e.target.value] : [])}
          className="w-full"
          hasError={hasError}
          disabled={disabled}
        />
      );
    case "boolean":
      return (
        <ToggleSwitch
          value={value === "true"}
          onChange={() => onChange([value === "true" ? "false" : "true"])}
          size="sm"
          disabled={disabled}
        />
      );
    case "select":
    case "multi_select": {
      const isMulti = property.property_type === "multi_select" && property.is_multi;
      const options = (property.options ?? [])
        .filter((option) => option.is_active)
        .map((option) => ({
          value: option.id,
          query: option.name,
          content: option.name,
        }));
      const selectedLabel = values.length
        ? (property.options ?? [])
            .filter((option) => values.includes(option.id))
            .map((option) => option.name)
            .join(", ")
        : `Select ${property.display_name}`;
      if (isMulti) {
        return (
          <CustomSearchSelect
            value={values}
            onChange={(next: string[] | null) => onChange(next ?? [])}
            options={options}
            label={selectedLabel}
            multiple
            disabled={disabled}
            buttonClassName="w-full"
          />
        );
      }
      return (
        <CustomSearchSelect
          value={value || null}
          onChange={(next: string | null) => onChange(next ? [next] : [])}
          options={options}
          label={selectedLabel}
          disabled={disabled}
          buttonClassName="w-full"
        />
      );
    }
    case "member":
      if (property.is_multi) {
        return (
          <MemberDropdown
            value={values}
            onChange={(next: string[]) => onChange(next ?? [])}
            projectId={projectId}
            multiple
            disabled={disabled}
            placeholder={property.display_name}
            buttonVariant="border-with-text"
          />
        );
      }
      return (
        <MemberDropdown
          value={value || null}
          onChange={(next: string | null) => onChange(next ? [next] : [])}
          projectId={projectId}
          multiple={false}
          disabled={disabled}
          placeholder={property.display_name}
          buttonVariant="border-with-text"
        />
      );
    default:
      return null;
  }
});
