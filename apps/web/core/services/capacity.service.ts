/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

export type TScheduleInterval = { start: string; end: string };
export type TTrainerException = { date: string; mode: "unavailable" | "override"; intervals: TScheduleInterval[] };
export type TTrainerProfile = {
  id: string;
  user_id: string;
  display_name: string;
  status: "active" | "suspended";
  timezone: string;
  weekly_schedule: Record<string, TScheduleInterval[]>;
  schedule_revision: number;
  connection_status: string;
  exceptions: TTrainerException[];
};
export type TCapacityInterval = {
  start: string;
  end: string;
  kind: "google_busy" | "workshop" | "available" | "outside_hours";
  work_item?: { id: string; name: string; project_id: string } | null;
};
export type TTrainerCapacity = {
  trainer_id: string;
  display_name: string;
  timezone: string;
  connection_status: string;
  availability_status:
    | "fresh"
    | "stale"
    | "not_connected"
    | "reauthentication_required"
    | "rate_limited"
    | "provider_unavailable"
    | string;
  working_minutes: number;
  google_busy_minutes: number;
  workshop_minutes: number;
  unavailable_minutes: number;
  available_minutes: number;
  intervals: TCapacityInterval[];
  conflicts: Array<{ start: string; end: string; kind: string; work_item_id?: string }>;
};
export type TCapacityResponse = { from: string; to: string; trainers: TTrainerCapacity[] };
export type TTrainerListResponse = { results: TTrainerProfile[]; next_cursor: string | null };
export type TGoogleCalendarList = { calendars: TGoogleCalendar[]; selection_revision: number };
export type TGoogleCalendar = {
  id: string;
  summary: string;
  primary: boolean;
  access_role: string;
  selected: boolean;
};
export type TWorkshopSchedule = {
  issue_id: string;
  starts_at: string;
  ends_at: string;
  preparation_minutes: number;
  travel_before_minutes: number;
  travel_after_minutes: number;
};

export class CapacityService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private data<T>(request: Promise<{ data: T }>): Promise<T> {
    return request
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data ?? error;
      });
  }

  listTrainers(workspaceSlug: string, cursor?: string) {
    return this.data<TTrainerListResponse>(
      this.get(`/api/workspaces/${workspaceSlug}/capacity/trainers/`, { params: cursor ? { cursor } : undefined })
    );
  }

  optIn(workspaceSlug: string) {
    return this.data<TTrainerProfile>(this.post(`/api/workspaces/${workspaceSlug}/capacity/trainers/me/`));
  }

  getOwnTrainerProfile(workspaceSlug: string) {
    return this.data<TTrainerProfile | null>(this.get(`/api/workspaces/${workspaceSlug}/capacity/trainers/me/`));
  }

  updateSchedule(workspaceSlug: string, userId: string, scheduleRevision: number, payload: Partial<TTrainerProfile>) {
    return this.data<TTrainerProfile>(
      this.patch(`/api/workspaces/${workspaceSlug}/capacity/trainers/${userId}/schedule/`, {
        ...payload,
        schedule_revision: scheduleRevision,
      })
    );
  }

  startGoogle(workspaceSlug: string) {
    return this.data<{ authorization_url: string }>(
      this.post(`/api/workspaces/${workspaceSlug}/capacity/google/start/`)
    );
  }

  listCalendars(workspaceSlug: string) {
    return this.data<TGoogleCalendarList>(this.get(`/api/workspaces/${workspaceSlug}/capacity/google/calendars/`));
  }

  selectCalendars(workspaceSlug: string, calendarIds: string[], selectionRevision: number) {
    return this.data<{ selected: number; revision: number }>(
      this.put(`/api/workspaces/${workspaceSlug}/capacity/google/calendars/`, {
        calendar_ids: calendarIds,
        selection_revision: selectionRevision,
      })
    );
  }

  disconnectGoogle(workspaceSlug: string) {
    return this.delete(`/api/workspaces/${workspaceSlug}/capacity/google/calendars/`);
  }

  getCapacity(workspaceSlug: string, from: string, to: string, trainerIds: string[]) {
    return this.data<TCapacityResponse>(
      this.get(`/api/workspaces/${workspaceSlug}/capacity/`, {
        params: { from, to, trainer_ids: trainerIds.join(",") },
      })
    );
  }

  getWorkshopSchedule(workspaceSlug: string, projectId: string, issueId: string) {
    return this.data<TWorkshopSchedule>(
      this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${issueId}/workshop-schedule/`)
    );
  }

  saveWorkshopSchedule(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    schedule: Omit<TWorkshopSchedule, "issue_id">
  ) {
    return this.data<TWorkshopSchedule>(
      this.put(
        `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${issueId}/workshop-schedule/`,
        schedule
      )
    );
  }

  deleteWorkshopSchedule(workspaceSlug: string, projectId: string, issueId: string) {
    return this.delete(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${issueId}/workshop-schedule/`
    );
  }
}
