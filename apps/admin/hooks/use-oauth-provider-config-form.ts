/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { BaseSyntheticEvent } from "react";
import { useForm } from "react-hook-form";
import type { DefaultValues, UseFormReturn } from "react-hook-form";
// plane internal packages
import { setToast } from "@plane/blocks/toast";
import type { IFormattedInstanceConfiguration } from "@plane/types";
// helpers
import { configurationErrorMessage } from "@/helpers/configuration-error";
// hooks
import { useInstance } from "@/hooks/store";

type TConfigFormValues = Partial<IFormattedInstanceConfiguration>;

/**
 * The values with every secret emptied.
 *
 * Secrets are write-only: the API never returns a stored one, and an empty
 * value is read server-side as "keep the current secret". A secret field
 * therefore always starts empty, and is emptied again after a save, whatever
 * the caller or the server response holds for it. Taking it from either would
 * put a value the form never had into the next submission.
 */
function withEmptySecrets<T extends TConfigFormValues>(values: DefaultValues<T> | T, secretKeys: readonly (keyof T)[]) {
  const next = { ...values } as Record<keyof T, unknown>;
  for (const key of secretKeys) next[key] = "";
  return next as DefaultValues<T>;
}

/**
 * Form state and save handler shared by the OAuth and OIDC provider config forms.
 *
 * On save the form resets to what was submitted, with every secret emptied, so
 * it is no longer dirty and no secret stays in memory or comes back from the
 * response. A refused save shows the server's reason.
 */
export function useOAuthProviderConfigForm<T extends TConfigFormValues>(
  providerName: string,
  defaultValues: DefaultValues<T>,
  secretKeys: readonly (keyof T)[]
): UseFormReturn<T> & { onSave: (e?: BaseSyntheticEvent) => Promise<void> } {
  // store hooks
  const { updateInstanceConfigurations } = useInstance();
  // form data
  const form = useForm<T>({ defaultValues: withEmptySecrets(defaultValues, secretKeys) });

  const onSubmit = async (formData: T) => {
    try {
      await updateInstanceConfigurations(formData);
      setToast({
        type: "success",
        title: "Done!",
        message: `Your ${providerName} authentication is configured. You should test it now.`,
      });
      form.reset(withEmptySecrets(formData, secretKeys));
    } catch (error) {
      setToast({ type: "error", title: "Error", message: configurationErrorMessage(error) });
    }
  };

  return { ...form, onSave: form.handleSubmit(onSubmit) };
}
