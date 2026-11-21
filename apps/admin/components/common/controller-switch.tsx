/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useId } from "react";
import type { Control, FieldPath, FieldValues } from "react-hook-form";
import { Controller } from "react-hook-form";
// plane internal packages
import { Switch } from "@makeplane/propel/components/switch";

type Props<T extends FieldValues = FieldValues> = {
  control: Control<T>;
  field: TControllerSwitchFormField<T>;
};

export type TControllerSwitchFormField<T extends FieldValues = FieldValues> = {
  name: FieldPath<T>;
  label: string;
};

export function ControllerSwitch<T extends FieldValues>(props: Props<T>) {
  const {
    control,
    field: { name, label },
  } = props;
  const labelId = useId();
  const descriptionId = useId();

  return (
    <div className="flex items-start justify-between gap-4 py-1">
      <div className="flex min-w-0 flex-col gap-1">
        <span id={labelId} className="text-body-sm-medium text-primary">
          Refresh user attributes from {label} during sign in
        </span>
        {/* Said plainly, because the consequence is destructive and the label
            alone reads like a harmless sync. */}
        <p id={descriptionId} className="text-caption-sm-regular text-tertiary">
          Every sign-in overwrites the person&apos;s display name and avatar with whatever {label} reports. Anything
          they changed in Hangar is replaced, each time they sign in. Leave this off to let people keep their own.
        </p>
      </div>
      <div className="shrink-0">
        <Controller
          control={control}
          name={name as FieldPath<T>}
          render={({ field: { value, onChange } }) => {
            const parsedValue = Number.parseInt(typeof value === "string" ? value : String(value ?? "0"), 10);
            const isOn = !Number.isNaN(parsedValue) && parsedValue !== 0;
            return (
              <Switch
                checked={isOn}
                onCheckedChange={() => onChange(isOn ? "0" : "1")}
                size="sm"
                aria-labelledby={labelId}
                aria-describedby={descriptionId}
              />
            );
          }}
        />
      </div>
    </div>
  );
}
