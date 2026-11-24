/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import useSWR from "swr";
import { useTranslation } from "@plane/i18n";
import { Banner } from "@makeplane/propel/components/banner";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { InputField } from "@makeplane/propel/components/input-field";
import { RadioGroupField, RadioGroupFieldOption } from "@makeplane/propel/components/radio-group-field";
import { Switch } from "@makeplane/propel/components/switch";
import { ArrowDownOutline, ArrowUpOutline, DeleteOutline, GripOutline } from "@makeplane/propel/icons";
import { Loader } from "@plane/blocks/skeleton";
import { setToast } from "@plane/blocks/toast";
import { WorkspaceDefaultsService } from "@plane/services";
import type { TWorkspaceHomeDefault, TWorkspaceSharedLink } from "@plane/services";
// components
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";

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
        type: "success",
        title: t("common.save"),
        message: applyToEveryone
          ? `Applied to ${result.members_updated ?? 0} people.`
          : "New members will start with this layout.",
      });
      setApplyToEveryone(false);
    } catch (error) {
      setToast({
        type: "error",
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
        type: "error",
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
        <SettingsHeading title={heading} description={t("workspace_settings.settings.home_defaults.description")} />

        <section className="flex flex-col gap-3">
          <SettingsHeading variant="h5" title={t("workspace_settings.settings.home_defaults.widgets")} />
          <ul className="divide-y divide-subtle rounded-lg border border-subtle bg-layer-1">
            {rows.map((row, index) => {
              const label = WIDGET_LABELS[row.key] ?? row.key;
              return (
                <li key={row.key} className="flex items-center gap-3 px-3 py-2">
                  <GripOutline className="size-4 shrink-0 text-placeholder" />
                  <span className="flex-1 text-body-xs-medium text-primary">{label}</span>
                  <div className="flex items-center gap-1">
                    <IconButton
                      variant="ghost"
                      size="sm"
                      icon={<Icon icon={ArrowUpOutline} />}
                      aria-label={`Move ${label} up`}
                      onClick={() => move(index, index - 1)}
                      disabled={index === 0}
                    />
                    <IconButton
                      variant="ghost"
                      size="sm"
                      icon={<Icon icon={ArrowDownOutline} />}
                      aria-label={`Move ${label} down`}
                      onClick={() => move(index, index + 1)}
                      disabled={index === rows.length - 1}
                    />
                  </div>
                  <Switch
                    size="md"
                    aria-label={`${label} on`}
                    checked={row.is_enabled}
                    onCheckedChange={(checked) =>
                      setRows((current) =>
                        current.map((candidate) =>
                          candidate.key === row.key ? { ...candidate, is_enabled: checked } : candidate
                        )
                      )
                    }
                  />
                </li>
              );
            })}
          </ul>
        </section>

        <div className="flex flex-col gap-3">
          <RadioGroupField<string>
            name="apply-scope"
            label="Who this applies to"
            size="lg"
            density="comfortable"
            value={applyToEveryone ? "everyone" : "new"}
            onValueChange={(value) => setApplyToEveryone(value === "everyone")}
          >
            <RadioGroupFieldOption
              size="lg"
              value="new"
              label={t("workspace_settings.settings.home_defaults.apply_to_new")}
              description="People already in this workspace keep what they have."
            />
            <RadioGroupFieldOption
              size="lg"
              value="everyone"
              label={t("workspace_settings.settings.home_defaults.apply_to_everyone")}
              description="This replaces what every member currently sees on their home page. It cannot be undone."
            />
          </RadioGroupField>
          {applyToEveryone && (
            <Banner
              variant="warning"
              placement="inline"
              description="Only the widgets listed above are replaced. Anything a person has set that is not on this list stays as they left it."
            />
          )}
        </div>

        <section className="flex flex-col gap-3">
          <SettingsHeading
            variant="h5"
            title={t("workspace_settings.settings.home_defaults.shared_links")}
            description="One list everybody sees. Editing a link or removing it reaches every home page at once — people can hide one from their own, but cannot change it."
          />
          {links.length > 0 && (
            <ul className="divide-y divide-subtle rounded-lg border border-subtle bg-layer-1">
              {links.map((link) => (
                <li key={link.id} className="flex items-center gap-3 px-3 py-2">
                  <span className="flex-1 truncate text-body-xs-medium text-primary">{link.title || link.url}</span>
                  <span className="max-w-64 truncate text-caption-md-regular text-tertiary">{link.url}</span>
                  <IconButton
                    variant="ghost"
                    size="sm"
                    icon={<Icon icon={DeleteOutline} />}
                    aria-label={`${t("common.remove")}: ${link.title || link.url}`}
                    onClick={() => void removeLink(link.id)}
                  />
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
            <div className="sm:w-56">
              <InputField
                size="lg"
                orientation="vertical"
                aria-label={t("common.title")}
                value={draft.title}
                onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
                placeholder={t("common.title")}
              />
            </div>
            <div className="flex-1">
              <InputField
                size="lg"
                orientation="vertical"
                aria-label="Web address"
                value={draft.url}
                onChange={(event) => setDraft((current) => ({ ...current, url: event.target.value }))}
                placeholder="wiki.example.com/runbook"
              />
            </div>
            <Button
              variant="secondary"
              size="lg"
              stretch="auto"
              label={t("common.add")}
              onClick={() => void addLink()}
              disabled={!draft.url.trim()}
            />
          </div>
        </section>

        <div>
          <Button
            variant="primary"
            size="lg"
            stretch="auto"
            label={saving ? t("common.saving") : t("common.save")}
            loading={saving}
            onClick={() => void save()}
          />
        </div>
      </div>
    </SettingsContentWrapper>
  );
});

export default HomeDefaultsSettingsPage;
