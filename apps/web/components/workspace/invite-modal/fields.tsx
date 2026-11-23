/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import type { Control, FieldArrayWithId, FormState } from "react-hook-form";
import { Controller } from "react-hook-form";
// plane imports
import { Field } from "@makeplane/propel/components/field";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { ROLE } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { CloseOutline } from "@makeplane/propel/icons";
import { Select } from "@plane/blocks/select";
import { cn } from "@plane/utils";
// hooks
import { useUserPermissions } from "@/hooks/store/user";
import type { InvitationFormValues } from "@/hooks/use-workspace-invitation";
// local
import type { TInvitePolicy } from "./invite-policy";
import { inviteRejection } from "./invite-policy";

type TRoleOption = { key: number; label: string };

type TInvitationFieldsProps = {
  workspaceSlug: string;
  fields: FieldArrayWithId<InvitationFormValues, "emails", "id">[];
  control: Control<InvitationFormValues>;
  formState: FormState<InvitationFormValues>;
  remove: (index: number) => void;
  className?: string;
  /** Undefined until loaded, or when the caller could not read it. */
  invitePolicy?: TInvitePolicy;
};

export const InvitationFields = observer(function InvitationFields(props: TInvitationFieldsProps) {
  const {
    workspaceSlug,
    fields,
    control,
    formState: { errors },
    remove,
    className,
    invitePolicy,
  } = props;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { workspaceInfoBySlug } = useUserPermissions();
  // derived values
  const currentWorkspaceRole = workspaceInfoBySlug(workspaceSlug.toString())?.role;
  // A member can only invite at or below their own role.
  const roleOptions: TRoleOption[] = Object.entries(ROLE)
    .map(([key, label]) => ({ key: parseInt(key), label }))
    .filter((role) => !!currentWorkspaceRole && currentWorkspaceRole >= role.key);

  /**
   * The server refuses these addresses either way. Applying the rules here
   * moves the refusal to the field being typed in, rather than a toast after
   * submitting a batch — and a batch is refused whole, so one bad address
   * would otherwise discard the rest.
   */
  const validateAgainstPolicy = (value: string) => {
    const rejection = inviteRejection(value, invitePolicy);
    if (!rejection) return true;
    if (rejection.rule === "outside_domain")
      return t("workspace_settings.settings.members.modal.errors.outside_domain", {
        domains: rejection.domains.join(", "),
      });
    if (rejection.rule === "plus_tag")
      return t("workspace_settings.settings.members.modal.errors.plus_tag", { domain: rejection.domain });
    return t("workspace_settings.settings.members.modal.errors.blocked_domain", { domain: rejection.domain });
  };

  return (
    <div className={cn("mb-3 space-y-4", className)}>
      {fields.map((field, index) => (
        <div
          key={field.id}
          className="group relative mb-1 flex w-full items-start justify-between gap-x-4 text-body-xs-regular"
        >
          <div className="w-full">
            <Controller
              control={control}
              name={`emails.${index}.email`}
              rules={{
                required: t("workspace_settings.settings.members.modal.errors.required"),
                pattern: {
                  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                  message: t("workspace_settings.settings.members.modal.errors.invalid"),
                },
                validate: validateAgainstPolicy,
              }}
              render={({ field: { value, onChange, ref } }) => (
                <>
                  <Field name="input" invalid={Boolean(errors.emails?.[index]?.email)}>
                    <InputGroup size="2xl">
                      <Input
                        size="2xl"
                        id={`emails.${index}.email`}
                        name={`emails.${index}.email`}
                        type="text"
                        value={value}
                        onChange={onChange}
                        ref={ref}
                        placeholder={t("workspace_settings.settings.members.modal.placeholder")}
                      />
                    </InputGroup>
                  </Field>
                  {errors.emails?.[index]?.email && (
                    <span className="ml-1 text-caption-sm-regular text-danger-primary">
                      {errors.emails?.[index]?.email?.message}
                    </span>
                  )}
                </>
              )}
            />
          </div>
          <div className="flex shrink-0 items-center justify-between gap-2">
            <div className="flex flex-col gap-1">
              <Controller
                control={control}
                name={`emails.${index}.role`}
                rules={{ required: true }}
                render={({ field: { value, onChange } }) => (
                  <div className="w-24 grow">
                    <Select<TRoleOption>
                      value={roleOptions.find((role) => role.key === value) ?? null}
                      onChange={(val) => onChange(Number(val))}
                      getValues={() => roleOptions}
                      getOptionValue={(role) => String(role.key)}
                      getOptionLabel={(role) => role.label}
                      showSearch={false}
                      pinSelected={false}
                    >
                      <Select.Trigger<TRoleOption> variant="select-2xl">
                        <span className="min-w-0 flex-1 truncate text-left text-caption-sm-regular sm:text-body-xs-regular">
                          {ROLE[value]}
                        </span>
                      </Select.Trigger>
                    </Select>
                  </div>
                )}
              />
            </div>
            {fields.length > 1 && (
              <div className="flex-item flex w-6">
                <button
                  type="button"
                  className="place-items-center self-center rounded-sm"
                  onClick={() => remove(index)}
                >
                  <CloseOutline className="h-4 w-4 text-secondary" />
                </button>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
});
