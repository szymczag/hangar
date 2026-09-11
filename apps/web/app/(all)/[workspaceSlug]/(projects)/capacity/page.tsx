/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import { Link2, Unplug } from "lucide-react";
import useSWR, { mutate } from "swr";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { useInstance } from "@/hooks/store/use-instance";
import { CapacityService, type TGoogleCalendar, type TTrainerProfile } from "@/services/capacity.service";
import type { Route } from "./+types/page";
import { bookingHoursSummary, errorMessage } from "./shared/capacity-format.utils";
import { ScheduleEditor } from "./shared/schedule-editor";

const capacityService = new CapacityService();

function BookingHoursSummary({ profile, onManage }: { profile: TTrainerProfile; onManage: () => void }) {
  return (
    <section className="flex flex-col justify-between gap-4 rounded-lg border border-subtle bg-surface-1 p-4 md:flex-row md:items-center">
      <div>
        <h2 className="text-body-sm-medium">Booking hours · {profile.display_name}</h2>
        <p className="mt-1 text-body-xs-regular text-secondary">{bookingHoursSummary(profile)}</p>
        <p className="mt-1 text-11 text-placeholder">
          {profile.timezone} · Google busy time and scheduled workshops are subtracted inside these hours.
        </p>
      </div>
      <Button variant="secondary" size="sm" onClick={onManage}>
        Manage schedule
      </Button>
    </section>
  );
}

function CalendarPicker({
  workspaceSlug,
  calendars,
  selectionRevision,
  onSaved,
}: {
  workspaceSlug: string;
  calendars: TGoogleCalendar[];
  selectionRevision: number;
  onSaved: () => void;
}) {
  const [selected, setSelected] = useState(() => {
    const saved = calendars.filter((item) => item.selected).map((item) => item.id);
    const primary = calendars.find((item) => item.primary)?.id;
    return new Set(saved.length || !primary ? saved : [primary]);
  });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      await capacityService.selectCalendars(workspaceSlug, [...selected], selectionRevision);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Calendars saved",
        message: "Only anonymous busy ranges will be used.",
      });
      onSaved();
    } catch (error: unknown) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Calendars not saved", message: errorMessage(error, "Try again.") });
    } finally {
      setSaving(false);
    }
  };
  return (
    <section className="rounded-lg border border-subtle bg-surface-1 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-body-sm-medium">Calendars that block your time</h2>
          <p className="mt-1 text-body-xs-regular text-secondary">
            Hangar reads free/busy ranges, never event details.
          </p>
        </div>
        <Button size="sm" variant="primary" loading={saving} disabled={selected.size === 0} onClick={save}>
          Save calendars
        </Button>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {calendars.map((calendar) => (
          <label
            key={calendar.id}
            className="flex cursor-pointer items-center gap-3 rounded-md border border-subtle px-3 py-2 text-body-xs-regular hover:bg-surface-2"
          >
            <input
              type="checkbox"
              checked={selected.has(calendar.id)}
              onChange={() =>
                setSelected((current) => {
                  const next = new Set(current);
                  if (next.has(calendar.id)) next.delete(calendar.id);
                  else next.add(calendar.id);
                  return next;
                })
              }
            />
            <span className="truncate">{calendar.summary}</span>
            {calendar.primary ? <span className="ml-auto text-11 text-placeholder">Primary</span> : null}
          </label>
        ))}
      </div>
      {selected.size === 0 ? (
        <p role="alert" className="mt-2 text-11 text-danger-primary">
          Select at least one blocking calendar. Primary may be replaced by another calendar.
        </p>
      ) : null}
    </section>
  );
}

export default function TrainerCapacityPage({ params }: Route.ComponentProps) {
  const workspaceSlug = params.workspaceSlug;
  const { config } = useInstance();
  const featureEnabled = config?.is_google_calendar_capacity_enabled === true;
  const [editingOwnSchedule, setEditingOwnSchedule] = useState(false);
  const [optingIn, setOptingIn] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const { data: ownProfile, mutate: mutateOwnProfile } = useSWR(
    featureEnabled ? ["capacity-trainer-self", workspaceSlug] : null,
    () => capacityService.getOwnTrainerProfile(workspaceSlug)
  );
  const hasActiveProfile = ownProfile?.status === "active";
  const isConnected = hasActiveProfile && ownProfile?.connection_status === "connected";
  const { data: calendars, mutate: mutateCalendars } = useSWR(
    featureEnabled && isConnected ? ["capacity-calendars", workspaceSlug] : null,
    () => capacityService.listCalendars(workspaceSlug)
  );

  /**
   * Opting in, connecting a calendar and changing booking hours all change what
   * the team ledger and the planner show, but this page renders neither. So it
   * invalidates those cache entries by key rather than subscribing to them
   * through `useCapacityData` -- subscribing would make a personal settings page
   * fetch the whole workspace's capacity to throw it away.
   */
  const refresh = useCallback(async () => {
    await mutateOwnProfile();
    await mutate((key) => Array.isArray(key) && typeof key[0] === "string" && key[0].startsWith("capacity"));
  }, [mutateOwnProfile]);
  const optIn = async () => {
    setOptingIn(true);
    try {
      await capacityService.optIn(workspaceSlug);
      await refresh();
    } finally {
      setOptingIn(false);
    }
  };
  const connect = async () => {
    setConnecting(true);
    try {
      const { authorization_url } = await capacityService.startGoogle(workspaceSlug);
      window.location.assign(authorization_url);
    } catch (error: unknown) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Google Calendar not connected",
        message: errorMessage(error, "Try again."),
      });
      setConnecting(false);
    }
  };
  const disconnect = async () => {
    if (!window.confirm("Disconnect Google Calendar and remove its cached availability from Hangar?")) return;
    setDisconnecting(true);
    try {
      await capacityService.disconnectGoogle(workspaceSlug);
      await refresh();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Google Calendar disconnected",
        message: "Cached Google availability was removed.",
      });
    } catch (error: unknown) {
      const mayForce =
        typeof error === "object" &&
        error !== null &&
        "can_force_local_disconnect" in error &&
        error.can_force_local_disconnect === true;
      if (
        mayForce &&
        window.confirm(
          "Google could not revoke the token. Remove the connection from Hangar anyway? You may also need to revoke Hangar in your Google Account."
        )
      ) {
        await capacityService.disconnectGoogle(workspaceSlug, true);
        await refresh();
      } else {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Google Calendar remains connected",
          message: errorMessage(error, "Try again later."),
        });
      }
    } finally {
      setDisconnecting(false);
    }
  };

  if (config && !config.is_google_calendar_capacity_enabled)
    return <NotAuthorizedView section="settings" className="h-auto" />;

  return (
    <div className="h-full overflow-y-auto bg-surface-2">
      <PageHead title="My capacity" />
      <div className="mx-auto flex max-w-[1440px] flex-col gap-5 p-4 md:p-6">
        {/* Opting in used to live in the team ledger's header, which this route
            no longer renders. Without it here a colleague who is not yet a
            trainer would find an empty page and no way off it. */}
        {!hasActiveProfile ? (
          <section className="flex flex-col justify-between gap-4 rounded-xl border border-subtle bg-surface-1 p-5 md:flex-row md:items-center">
            <div>
              <h1 className="text-body-sm-medium text-primary">
                {ownProfile ? "You are not an active trainer." : "You are not a trainer yet."}
              </h1>
              <p className="mt-1 text-body-xs-regular text-secondary">
                Opt in to put your booking hours on the workspace capacity ledger. You choose the hours, and which
                calendars block your time.
              </p>
            </div>
            <Button variant="primary" loading={optingIn} onClick={optIn}>
              {ownProfile ? "Reactivate trainer" : "Become a trainer"}
            </Button>
          </section>
        ) : null}

        {ownProfile && editingOwnSchedule ? (
          <section aria-label="Manage your schedule" className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="text-body-sm-medium">Your booking hours</h2>
              <Button variant="secondary" size="sm" onClick={() => setEditingOwnSchedule(false)}>
                Close
              </Button>
            </div>
            <ScheduleEditor
              key={`${ownProfile.id}-${ownProfile.schedule_revision}-schedule`}
              profile={ownProfile}
              workspaceSlug={workspaceSlug}
              onSaved={refresh}
            />
          </section>
        ) : null}

        {ownProfile && hasActiveProfile ? (
          <>
            {!editingOwnSchedule ? (
              <BookingHoursSummary profile={ownProfile} onManage={() => setEditingOwnSchedule(true)} />
            ) : null}
            {isConnected && calendars ? (
              <CalendarPicker
                workspaceSlug={workspaceSlug}
                calendars={calendars.calendars}
                selectionRevision={calendars.selection_revision}
                onSaved={async () => {
                  await mutateCalendars();
                  await refresh();
                }}
              />
            ) : (
              <section className="flex flex-col justify-between gap-4 rounded-lg border border-subtle bg-surface-1 p-4 md:flex-row md:items-center">
                <div>
                  <h2 className="text-body-sm-medium">Google Calendar</h2>
                  <p className="mt-1 text-body-xs-regular text-secondary">
                    Connect read-only free/busy access. Event names and details never enter Hangar.
                  </p>
                </div>
                <Button variant="primary" loading={connecting} onClick={connect}>
                  <Link2 className="mr-2 size-4" />
                  Connect Google Calendar
                </Button>
              </section>
            )}
            {isConnected ? (
              <button
                type="button"
                className="self-end text-11 text-secondary hover:text-danger-primary"
                disabled={disconnecting}
                onClick={disconnect}
              >
                <Unplug className="mr-1 inline size-3" />
                {disconnecting ? "Disconnecting…" : "Disconnect Google Calendar"}
              </button>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
