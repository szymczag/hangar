/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Trash2, Upload } from "lucide-react";
// plane internal packages
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { AuthService, InstanceBrandingService } from "@plane/services";
import type { IFormattedInstanceConfiguration, TInstanceBrandingConfigurationKeys } from "@plane/types";
// components
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
// helpers
import { configurationErrorMessage } from "@/helpers/configuration-error";
// hooks
import { useInstance } from "@/hooks/store";
import { useConfigurationEditable } from "@/hooks/use-configuration-editable";

const authService = new AuthService();
const brandingService = new InstanceBrandingService();

type Props = {
  config: IFormattedInstanceConfiguration;
};

type BrandingFormValues = Record<TInstanceBrandingConfigurationKeys, string>;

export function InstanceBrandingForm(props: Props) {
  const { config } = props;
  // states
  const [csrfToken, setCsrfToken] = useState<string | undefined>(undefined);
  const [logoUrl, setLogoUrl] = useState<string>(
    config.INSTANCE_LOGO_ASSET_ID ? `/api/assets/v2/static/${config.INSTANCE_LOGO_ASSET_ID}/` : ""
  );
  const [isUploading, setIsUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  // store hooks
  const { updateInstanceConfigurations } = useInstance();
  const isConfigurationEditable = useConfigurationEditable();
  // form
  const {
    handleSubmit,
    control,
    reset,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<BrandingFormValues>({
    defaultValues: {
      INSTANCE_BRANDING_NAME: config.INSTANCE_BRANDING_NAME ?? "",
      INSTANCE_SIGN_IN_HEADER: config.INSTANCE_SIGN_IN_HEADER ?? "",
      INSTANCE_SIGN_IN_SUBHEADER: config.INSTANCE_SIGN_IN_SUBHEADER ?? "",
    },
  });

  useEffect(() => {
    authService.requestCSRFToken().then((data) => data?.csrf_token && setCsrfToken(data.csrf_token));
  }, []);

  const BRANDING_FIELDS: TControllerInputFormField<BrandingFormValues>[] = [
    {
      key: "INSTANCE_BRANDING_NAME",
      type: "text",
      label: "Organisation name",
      description: (
        <>Shown in the sign-in page footer and in the browser tab. Left empty, neither mentions an organisation.</>
      ),
      placeholder: "SECURITUM SZKOLENIA",
      error: Boolean(errors.INSTANCE_BRANDING_NAME),
      required: false,
    },
    {
      key: "INSTANCE_SIGN_IN_HEADER",
      type: "text",
      label: "Sign-in headline",
      description: <>Replaces &quot;Work in all dimensions.&quot; Left empty, that wording stays.</>,
      placeholder: "Work in all dimensions.",
      error: Boolean(errors.INSTANCE_SIGN_IN_HEADER),
      required: false,
    },
    {
      key: "INSTANCE_SIGN_IN_SUBHEADER",
      type: "text",
      label: "Sign-in subheading",
      description: <>Replaces &quot;Welcome back to Hangar.&quot; Left empty, that wording stays.</>,
      placeholder: "Welcome back to Hangar.",
      error: Boolean(errors.INSTANCE_SIGN_IN_SUBHEADER),
      required: false,
    },
  ];

  const onSubmit = async (formData: BrandingFormValues) => {
    try {
      const response = await updateInstanceConfigurations(formData);
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Saved", message: "Branding updated." });
      reset({
        INSTANCE_BRANDING_NAME: response.find((item) => item.key === "INSTANCE_BRANDING_NAME")?.value ?? "",
        INSTANCE_SIGN_IN_HEADER: response.find((item) => item.key === "INSTANCE_SIGN_IN_HEADER")?.value ?? "",
        INSTANCE_SIGN_IN_SUBHEADER: response.find((item) => item.key === "INSTANCE_SIGN_IN_SUBHEADER")?.value ?? "",
      });
    } catch (error) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: configurationErrorMessage(error) });
    }
  };

  const uploadLogo = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !csrfToken) return;
    setIsUploading(true);
    try {
      const result = await brandingService.uploadLogo(csrfToken, file);
      setLogoUrl(result.asset_url);
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Logo updated", message: "The sign-in page now shows it." });
    } catch (error) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Logo not updated", message: configurationErrorMessage(error) });
    } finally {
      setIsUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const clearLogo = async () => {
    if (!csrfToken) return;
    setIsUploading(true);
    try {
      await brandingService.clearLogo(csrfToken);
      setLogoUrl("");
    } catch (error) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Logo not cleared", message: configurationErrorMessage(error) });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="flex max-w-4xl flex-col gap-8">
      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium text-primary">Logo</span>
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-44 items-center justify-center rounded-md border border-strong bg-surface-1">
            {logoUrl ? (
              <img src={logoUrl} alt="Instance logo" className="max-h-10 max-w-[160px] object-contain" />
            ) : (
              <span className="text-11 text-tertiary">Hangar wordmark</span>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <input
              ref={fileInput}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              className="text-sm"
              onChange={uploadLogo}
              disabled={isUploading || !isConfigurationEditable}
            />
            {logoUrl && (
              <Button variant="secondary" size="sm" onClick={clearLogo} disabled={isUploading}>
                <Trash2 className="h-3.5 w-3.5" /> Use the Hangar wordmark
              </Button>
            )}
          </div>
        </div>
        <span className="text-11 text-tertiary">
          PNG, JPEG, WebP or GIF. It is served to anyone who opens the sign-in page, so it is validated as an image
          server-side rather than trusted from the upload.
        </span>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-8">
        <div className="grid grid-cols-1 gap-x-16 gap-y-8 lg:grid-cols-2">
          {BRANDING_FIELDS.map((field) => (
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
        <div>
          <Button
            variant="primary"
            onClick={handleSubmit(onSubmit)}
            loading={isSubmitting}
            disabled={!isDirty || isSubmitting || !isConfigurationEditable}
          >
            {isSubmitting ? "Saving" : "Save changes"}
          </Button>
        </div>
      </form>

      <div className="flex items-start gap-3 rounded-md border border-subtle p-4 text-13">
        <Upload className="mt-0.5 h-4 w-4 shrink-0 text-tertiary" />
        <span className="text-tertiary">
          Hangar is AGPL-licensed. You may present it under your own name, and the licence still requires that the
          source remains available to the people using it.
        </span>
      </div>
    </div>
  );
}
