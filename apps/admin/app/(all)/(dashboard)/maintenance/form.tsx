/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { AlertOctagon, AlertTriangle, Eye, Info } from "lucide-react";
// plane internal packages
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { AuthService, InstanceMaintenanceService } from "@plane/services";
import type { TMaintenanceNoticeAdmin, TMaintenanceSeverity } from "@plane/services";
import { cn } from "@plane/utils";

const authService = new AuthService();
const maintenanceService = new InstanceMaintenanceService();

const MESSAGE_MAX_LENGTH = 500;

const SEVERITIES: { value: TMaintenanceSeverity; label: string; hint: string; Icon: typeof Info }[] = [
  { value: "info", label: "Info", hint: "Something people should know.", Icon: Info },
  { value: "warning", label: "Warning", hint: "Work is planned or under way.", Icon: AlertTriangle },
  { value: "critical", label: "Critical", hint: "Something is broken now.", Icon: AlertOctagon },
];

/** `datetime-local` needs "YYYY-MM-DDTHH:mm" in local time; the API speaks ISO. */
const toLocalInput = (iso: string | null): string => {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
};

const toIso = (local: string): string | null => {
  if (!local) return null;
  const date = new Date(local);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
};

type FormValues = {
  is_enabled: boolean;
  message: string;
  severity: TMaintenanceSeverity;
  starts_at: string;
  ends_at: string;
  show_on_sign_in: boolean;
};

type Props = {
  notice: TMaintenanceNoticeAdmin;
  onSaved: (notice: TMaintenanceNoticeAdmin) => void;
};

export const InstanceMaintenanceForm = ({ notice, onSaved }: Props) => {
  const [csrfToken, setCsrfToken] = useState<string | undefined>(undefined);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { isSubmitting },
  } = useForm<FormValues>({
    defaultValues: {
      is_enabled: notice.is_enabled,
      message: notice.message,
      severity: notice.severity,
      starts_at: toLocalInput(notice.starts_at),
      ends_at: toLocalInput(notice.ends_at),
      show_on_sign_in: notice.show_on_sign_in,
    },
  });

  useEffect(() => {
    authService.requestCSRFToken().then((data) => data?.csrf_token && setCsrfToken(data.csrf_token));
  }, []);

  const severity = watch("severity");
  const message = watch("message") ?? "";
  const publishedToSignIn = watch("show_on_sign_in");

  const onSubmit = async (values: FormValues) => {
    if (!csrfToken) return;
    try {
      const saved = await maintenanceService.update(csrfToken, {
        is_enabled: values.is_enabled,
        message: values.message,
        severity: values.severity,
        starts_at: toIso(values.starts_at),
        ends_at: toIso(values.ends_at),
        show_on_sign_in: values.show_on_sign_in,
      });
      onSaved(saved);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Saved",
        message: saved.is_active ? "The notice is showing now." : "Saved. The notice is not showing.",
      });
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Not saved",
        message: (error as { error?: string })?.error ?? "Something went wrong. Try again.",
      });
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex max-w-3xl flex-col gap-8">
      <div className="flex flex-col gap-2">
        <label htmlFor="maintenance-message" className="text-14 font-medium text-primary">
          Message
        </label>
        <textarea
          id="maintenance-message"
          rows={3}
          maxLength={MESSAGE_MAX_LENGTH}
          placeholder="Maintenance 22:00–22:30 today. Hangar will be briefly unavailable."
          className="w-full rounded-md border border-subtle bg-surface-1 px-3 py-2 text-14 text-primary outline-none placeholder:text-placeholder focus:border-accent-strong"
          {...register("message")}
        />
        <div className="flex items-center justify-between text-11 text-tertiary">
          <span>One line of plain text. Say what is happening and when — links and line breaks are not accepted.</span>
          <span className={cn("tabular-nums", message.length > MESSAGE_MAX_LENGTH && "text-danger-primary")}>
            {message.length}/{MESSAGE_MAX_LENGTH}
          </span>
        </div>
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-14 font-medium text-primary">Severity</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {SEVERITIES.map(({ value, label, hint, Icon }) => (
            <button
              key={value}
              type="button"
              onClick={() => setValue("severity", value, { shouldDirty: true })}
              aria-pressed={severity === value}
              className={cn(
                "flex flex-col gap-1 rounded-md border border-subtle bg-surface-1 p-3 text-left transition-colors",
                severity === value ? "border-accent-strong bg-accent-subtle" : "hover:bg-surface-2"
              )}
            >
              <span className="flex items-center gap-2 text-13 font-medium text-primary">
                <Icon className="size-4" aria-hidden="true" />
                {label}
              </span>
              <span className="text-11 text-tertiary">{hint}</span>
            </button>
          ))}
        </div>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <label htmlFor="maintenance-starts" className="text-14 font-medium text-primary">
            Starts <span className="font-normal text-tertiary">(optional)</span>
          </label>
          <input
            id="maintenance-starts"
            type="datetime-local"
            className="rounded-md border border-subtle bg-surface-1 px-3 py-2 text-14 text-primary outline-none focus:border-accent-strong"
            {...register("starts_at")}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor="maintenance-ends" className="text-14 font-medium text-primary">
            Ends <span className="font-normal text-tertiary">(optional)</span>
          </label>
          <input
            id="maintenance-ends"
            type="datetime-local"
            className="rounded-md border border-subtle bg-surface-1 px-3 py-2 text-14 text-primary outline-none focus:border-accent-strong"
            {...register("ends_at")}
          />
        </div>
        <p className="text-11 text-tertiary sm:col-span-2">
          Times are in your own timezone. Everyone sees the window in theirs. Leave both empty for a notice that runs
          until you switch it off.
        </p>
      </div>

      <label className="flex items-start gap-3 rounded-md border border-subtle bg-surface-1 p-4">
        <input type="checkbox" className="mt-0.5 size-4" {...register("show_on_sign_in")} />
        <span className="flex flex-col gap-1">
          <span className="text-14 font-medium text-primary">Also show on the sign-in page</span>
          <span className="text-12 text-tertiary">
            People who cannot sign in are the ones an outage affects most, so this is usually what you want during one.
          </span>
        </span>
      </label>

      {publishedToSignIn && (
        <div className="flex items-start gap-3 rounded-md border border-warning-subtle bg-warning-subtle p-4">
          <Eye className="mt-0.5 size-4 shrink-0 text-secondary" aria-hidden="true" />
          <p className="text-12 leading-5 text-secondary">
            <span className="font-medium">Anyone who can reach your sign-in page can read this</span>, including people
            outside your network. Keep it free of detail you would not publish — hostnames, ticket numbers, or what
            exactly is broken.
          </p>
        </div>
      )}

      <label className="flex items-start gap-3 rounded-md border border-subtle bg-surface-1 p-4">
        <input type="checkbox" className="mt-0.5 size-4" {...register("is_enabled")} />
        <span className="flex flex-col gap-1">
          <span className="text-14 font-medium text-primary">Show this notice</span>
          <span className="text-12 text-tertiary">
            People can dismiss it, and it stays dismissed in that browser until you change the wording or the window.
            Someone on a laptop and a phone dismisses it twice.
          </span>
        </span>
      </label>

      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary" loading={isSubmitting} disabled={!csrfToken}>
          {isSubmitting ? "Saving" : "Save"}
        </Button>
        <span className="text-12 text-tertiary">{notice.is_active ? "Showing now." : "Not showing."}</span>
      </div>
    </form>
  );
};
