/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useForm } from "react-hook-form";
import { ThoughtsOutline } from "@makeplane/propel/icons";
import { Button } from "@makeplane/propel/components/button";
import type { IFormattedInstanceConfiguration, TInstanceAIConfigurationKeys } from "@plane/types";
// components
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
import { setToast } from "@plane/blocks/toast";
// helpers
import { configurationErrorMessage } from "@/helpers/configuration-error";
// hooks
import { useInstance } from "@/hooks/store";

type IInstanceAIForm = {
  config: IFormattedInstanceConfiguration;
};

type AIFormValues = Record<TInstanceAIConfigurationKeys, string>;

export function InstanceAIForm(props: IInstanceAIForm) {
  const { config } = props;
  // store
  const { updateInstanceConfigurations, configuredSecrets } = useInstance();
  // The API never returns a stored secret, so an empty field means either
  // "never set" or "set and unreadable". Only the first should block saving:
  // an empty value is understood server-side as "keep the existing secret".
  const isSecretConfigured = configuredSecrets.has("LLM_API_KEY");
  // form data
  const {
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<AIFormValues>({
    defaultValues: {
      LLM_API_KEY: "",
      LLM_MODEL: config["LLM_MODEL"],
    },
  });

  const aiFormFields: TControllerInputFormField<AIFormValues>[] = [
    {
      key: "LLM_MODEL",
      type: "text",
      label: "LLM Model",
      description: (
        <>
          Choose an OpenAI engine.{" "}
          <a
            href="https://platform.openai.com/docs/models/overview"
            target="_blank"
            className="text-accent-primary hover:underline"
            rel="noreferrer"
            aria-label="OpenAI models documentation"
          >
            Learn more
          </a>
        </>
      ),
      placeholder: "gpt-4o-mini",
      error: Boolean(errors.LLM_MODEL),
      required: false,
    },
    {
      key: "LLM_API_KEY",
      type: "password",
      label: "API key",
      description: (
        <>
          You will find your API key{" "}
          <a
            href="https://platform.openai.com/api-keys"
            target="_blank"
            className="text-accent-primary hover:underline"
            rel="noreferrer"
            aria-label="OpenAI API keys page"
          >
            here.
          </a>
        </>
      ),
      placeholder: isSecretConfigured
        ? "Leave blank to keep the current secret"
        : "sk-asddassdfasdefqsdfasd23das3dasdcasd",
      error: Boolean(errors.LLM_API_KEY),
      required: !isSecretConfigured,
    },
  ];

  const onSubmit = async (formData: AIFormValues) => {
    const payload: Partial<AIFormValues> = { ...formData };

    try {
      await updateInstanceConfigurations(payload);
      // the key is not kept in the form, since the API never shows it back either
      reset({ ...formData, LLM_API_KEY: "" });
      setToast({
        type: "success",
        title: "Success",
        message: "AI Settings updated successfully",
      });
    } catch (error) {
      setToast({ type: "error", title: "Error", message: configurationErrorMessage(error) });
    }
  };

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <div>
          <div className="pb-1 text-h6-medium text-primary">OpenAI</div>
          <div className="text-body-sm-regular text-tertiary">If you use ChatGPT, this is for you.</div>
        </div>
        <div className="grid-col grid w-full max-w-4xl grid-cols-1 items-start justify-between gap-10 lg:grid-cols-2">
          {aiFormFields.map((field) => (
            <ControllerInput
              key={field.key}
              control={control}
              type={field.type}
              name={field.key}
              label={field.label}
              description={field.description}
              placeholder={field.placeholder}
              error={field.error}
              required={field.required}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-col items-start gap-4">
        <Button
          variant="primary"
          size="md"
          stretch="auto"
          onClick={handleSubmit(onSubmit)}
          loading={isSubmitting}
          label={isSubmitting ? "Saving" : "Save changes"}
        />

        <div className="relative inline-flex items-center gap-1.5 rounded-sm border border-accent-subtle bg-accent-subtle px-4 py-2 text-caption-sm-regular text-accent-secondary">
          <ThoughtsOutline className="size-4" />
          <div>
            To request another AI model provider, open a{" "}
            <a className="font-medium underline" href="https://github.com/szymczag/hangar/issues">
              GitHub issue.
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
