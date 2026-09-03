/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import useSWR from "swr";
import { AlertTriangle, GripVertical, Trash2 } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { WorkspaceDefaultsService } from "@plane/services";
import type { TWorkspaceHomeDefault, TWorkspaceSharedLink } from "@plane/services";
import { Loader } from "@plane/ui";
import { cn } from "@plane/utils";
// components
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";

const service = new WorkspaceDefaultsService();

const WIDGET_LABELS: Record<string, string> = {
  quick_links: "Quick links",
  recents: "Recents",
  my_stickies: "Stickies",
};

const HomeDefaultsSettingsPage = observer(function HomeDefaultsSettingsPage() {
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString();
  const { t } = useTranslation();

  const [rows, setRows] = useState<TWorkspaceHomeDefault[]>([]);
  const [applyToEveryone, setApplyToEveryone] = useState(false);
  const [saving, setSaving] = useState(false);
  const [links, setLinks] = useState<TWorkspaceSharedLink[]>([]);
  const [draft, setDraft] = useState({ title: "", url: "" });

  const { data } = useSWR(
    slug ? `HOME_DEFAULTS_${slug}` : null,
    slug ? () => service.retrieveHomeDefaults(slug) : null,
    {
      revalidateOnFocus: false,
    }
  );
  const { data: linkData } = useSWR(
    slug ? `HOME_DEFAULT_LINKS_${slug}` : null,
    slug ? () => service.listSharedLinks(slug) : null,
    { revalidateOnFocus: false }
  );

  useEffect(() => {
    if (!data) return;
    const configured = new Map(data.defaults.map((row) => [row.key, row]));
    setRows(
      data.available_keys.map(
        (key, index) => configured.get(key) ?? { key, is_enabled: true, sort_order: (index + 1) * 100, config: {} }
      )
    );
  }, [data]);

  useEffect(() => {
    if (linkData) setLinks(linkData);
  }, [linkData]);

  const move = (from: number, to: number) => {
    if (to < 0 || to >= rows.length) return;
    const next = [...rows];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    // Written out rather than spread: sort_order is derived from position, so
    // every row gets a fresh object with the recomputed value.
    setRows(
      next.map((row, index) => ({
        key: row.key,
        is_enabled: row.is_enabled,
        config: row.config,
        sort_order: (index + 1) * 100,
      }))
    );
  };

  const save = async () => {
    if (!slug) return;
    setSaving(true);
    try {
      const result = await service.updateHomeDefaults(slug, rows, applyToEveryone);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("common.save"),
        message: applyToEveryone
          ? `Applied to ${result.members_updated ?? 0} people.`
          : "New members will start with this layout.",
      });
      setApplyToEveryone(false);
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Not saved",
        message: (error as { error?: string })?.error ?? "Something went wrong. Try again.",
      });
    } finally {
      setSaving(false);
    }
  };

  const addLink = async () => {
    if (!slug || !draft.url.trim()) return;
    try {
      const created = await service.createSharedLink(slug, draft);
      setLinks((current) => [...current, created]);
      setDraft({ title: "", url: "" });
    } catch (error) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Not added",
        message: (error as { error?: string })?.error ?? "That is not a valid web address.",
      });
    }
  };

  const removeLink = async (linkId: string) => {
    if (!slug) return;
    await service.deleteSharedLink(slug, linkId);
    setLinks((current) => current.filter((link) => link.id !== linkId));
  };

  const heading = t("workspace_settings.settings.home_defaults.title");

  if (!data) {
    return (
      <SettingsContentWrapper>
        <Loader className="space-y-6 p-6">
          <Loader.Item height="40px" width="30%" />
          <Loader.Item height="180px" />
          <Loader.Item height="140px" />
        </Loader>
      </SettingsContentWrapper>
    );
  }

  return (
    <SettingsContentWrapper>
      <PageHead title={heading} />
      <div className="flex w-full max-w-3xl flex-col gap-10 py-6">
        <header className="flex flex-col gap-1">
          <h2 className="text-18 font-semibold text-primary">{heading}</h2>
          <p className="text-13 text-secondary">{t("workspace_settings.settings.home_defaults.description")}</p>
        </header>

        <section className="flex flex-col gap-3">
          <h3 className="text-14 font-medium text-primary">{t("workspace_settings.settings.home_defaults.widgets")}</h3>
          <ul className="divide-y divide-subtle rounded-md border border-subtle">
            {rows.map((row, index) => (
              <li key={row.key} className="flex items-center gap-3 px-3 py-2.5">
                <GripVertical className="size-4 shrink-0 text-placeholder" aria-hidden="true" />
                <span className="flex-1 text-13 text-primary">{WIDGET_LABELS[row.key] ?? row.key}</span>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => move(index, index - 1)}
                    disabled={index === 0}
                    aria-label={`Move ${WIDGET_LABELS[row.key] ?? row.key} up`}
                    className="rounded-sm px-2 py-1 text-12 text-tertiary hover:bg-surface-2 disabled:opacity-40"
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    onClick={() => move(index, index + 1)}
                    disabled={index === rows.length - 1}
                    aria-label={`Move ${WIDGET_LABELS[row.key] ?? row.key} down`}
                    className="rounded-sm px-2 py-1 text-12 text-tertiary hover:bg-surface-2 disabled:opacity-40"
                  >
                    ↓
                  </button>
                </div>
                <label className="flex items-center gap-2 text-12 text-tertiary">
                  <input
                    type="checkbox"
                    className="size-4"
                    checked={row.is_enabled}
                    onChange={(event) =>
                      setRows((current) =>
                        current.map((candidate) =>
                          candidate.key === row.key ? { ...candidate, is_enabled: event.target.checked } : candidate
                        )
                      )
                    }
                  />
                  On
                </label>
              </li>
            ))}
          </ul>
        </section>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-14 font-medium text-primary">Who this applies to</legend>
          {[
            {
              value: false,
              label: t("workspace_settings.settings.home_defaults.apply_to_new"),
              hint: "People already in this workspace keep what they have.",
            },
            {
              value: true,
              label: t("workspace_settings.settings.home_defaults.apply_to_everyone"),
              hint: "This replaces what every member currently sees on their home page. It cannot be undone.",
            },
          ].map((option) => (
            <label
              key={String(option.value)}
              aria-label={option.label}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-md border border-subtle p-3",
                applyToEveryone === option.value && "border-accent-strong bg-accent-subtle"
              )}
            >
              <input
                type="radio"
                name="apply-scope"
                className="mt-0.5 size-4"
                checked={applyToEveryone === option.value}
                onChange={() => setApplyToEveryone(option.value)}
              />
              <span className="flex flex-col gap-0.5">
                <span className="text-13 font-medium text-primary">{option.label}</span>
                <span className="text-11 text-tertiary">{option.hint}</span>
              </span>
            </label>
          ))}
          {applyToEveryone && (
            <p className="flex items-start gap-2 rounded-md border border-warning-subtle bg-warning-subtle p-3 text-12 text-secondary">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              Only the widgets listed above are replaced. Anything a person has set that is not on this list stays as
              they left it.
            </p>
          )}
        </fieldset>

        <section className="flex flex-col gap-3">
          <h3 className="text-14 font-medium text-primary">
            {t("workspace_settings.settings.home_defaults.shared_links")}
          </h3>
          <p className="text-12 text-tertiary">
            One list everybody sees. Editing a link or removing it reaches every home page at once — people can hide one
            from their own, but cannot change it.
          </p>
          {links.length > 0 && (
            <ul className="divide-y divide-subtle rounded-md border border-subtle">
              {links.map((link) => (
                <li key={link.id} className="flex items-center gap-3 px-3 py-2.5">
                  <span className="flex-1 truncate text-13 text-primary">{link.title || link.url}</span>
                  <span className="max-w-64 truncate text-11 text-tertiary">{link.url}</span>
                  <button
                    type="button"
                    onClick={() => removeLink(link.id)}
                    aria-label={`${t("common.remove")}: ${link.title || link.url}`}
                    className="rounded-sm p-1 text-tertiary hover:bg-surface-2 hover:text-danger-primary"
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={draft.title}
              onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
              placeholder={t("common.title")}
              className="rounded-md border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary outline-none placeholder:text-placeholder focus:border-accent-strong sm:w-56"
            />
            <input
              value={draft.url}
              onChange={(event) => setDraft((current) => ({ ...current, url: event.target.value }))}
              placeholder="wiki.example.com/runbook"
              className="flex-1 rounded-md border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary outline-none placeholder:text-placeholder focus:border-accent-strong"
            />
            <Button variant="secondary" onClick={addLink} disabled={!draft.url.trim()}>
              {t("common.add")}
            </Button>
          </div>
        </section>

        <div>
          <Button variant="primary" onClick={save} loading={saving}>
            {saving ? t("common.saving") : t("common.save")}
          </Button>
        </div>
      </div>
    </SettingsContentWrapper>
  );
});

export default HomeDefaultsSettingsPage;
