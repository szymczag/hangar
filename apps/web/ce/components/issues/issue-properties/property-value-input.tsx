/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { Field } from "@makeplane/propel/components/field";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { Switch } from "@makeplane/propel/components/switch";
import { Select } from "@plane/blocks/select";
// components
import { MemberSelect } from "@/components/dropdowns/member/member-select";
// plane web
import type { TIssuePropertyExt, TIssuePropertyOptionExt } from "@/plane-web/types/issue-types";

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
    case "number":
    case "date":
      return (
        <Field name={`property-${property.id}`} invalid={hasError}>
          <InputGroup size="md">
            <Input
              size="md"
              id={`property-${property.id}`}
              type={property.property_type}
              value={property.property_type === "date" && value ? value.slice(0, 10) : value}
              onChange={(e) => onChange(e.target.value ? [e.target.value] : [])}
              placeholder={property.property_type === "date" ? undefined : property.display_name}
              aria-label={property.display_name}
              disabled={disabled}
            />
          </InputGroup>
        </Field>
      );
    case "boolean":
      return (
        <Switch
          size="sm"
          checked={value === "true"}
          onCheckedChange={(checked) => onChange([checked ? "true" : "false"])}
          aria-label={property.display_name}
          disabled={disabled}
        />
      );
    case "select":
    case "multi_select": {
      const isMulti = property.property_type === "multi_select" && property.is_multi;
      // Deactivated options stay out of the list, but a value that still holds one keeps it.
      const options = (property.options ?? []).filter((option) => option.is_active || values.includes(option.id));
      const byId = new Map(options.map((option) => [option.id, option]));
      const selected = values.map((id) => byId.get(id)).filter((option) => option !== undefined);
      const placeholder = `Select ${property.display_name}`;
      const common = {
        getValues: () => options,
        getOptionValue: (option: TIssuePropertyOptionExt) => option.id,
        getOptionLabel: (option: TIssuePropertyOptionExt) => option.name,
        getOptionDisabled: (option: TIssuePropertyOptionExt) => !option.is_active,
        disabled,
        placeholder,
        pinSelected: false,
        showSearch: options.length > 7,
        contentSizing: "anchor" as const,
      };
      const trigger = (
        <Select.Trigger<TIssuePropertyOptionExt>
          variant="select-md"
          disabled={disabled}
          className="w-full"
          id={`property-${property.id}`}
        >
          {(chosen) => (
            <span className="min-w-0 grow truncate text-left">
              {chosen.length ? chosen.map((option) => option.name).join(", ") : placeholder}
            </span>
          )}
        </Select.Trigger>
      );
      return (
        <Field name={`property-${property.id}`} invalid={hasError}>
          {isMulti ? (
            <Select<TIssuePropertyOptionExt> {...common} multiple value={selected} onChange={(next) => onChange(next)}>
              {trigger}
            </Select>
          ) : (
            <Select<TIssuePropertyOptionExt>
              {...common}
              value={selected[0] ?? null}
              onChange={(next) => onChange(next ? [next] : [])}
            >
              {trigger}
            </Select>
          )}
        </Field>
      );
    }
    case "member":
      if (property.is_multi) {
        return (
          <MemberSelect
            value={values}
            onChange={(next) => onChange(next ?? [])}
            projectId={projectId}
            multiple
            disabled={disabled}
            placeholder={property.display_name}
            variant={values.length ? "avatar-group-md" : "pill-md"}
          />
        );
      }
      return (
        <MemberSelect
          value={value || null}
          onChange={(next) => onChange(next ? [next] : [])}
          projectId={projectId}
          disabled={disabled}
          placeholder={property.display_name}
          variant="pill-md"
        />
      );
    default:
      return null;
  }
});
