/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

export type TScheduleInterval = { start: string; end: string };
export type TTrainerProfile = {
  id: string;
  user_id: string;
  display_name: string;
  status: "active" | "suspended";
  timezone: string;
  weekly_schedule: Record<string, TScheduleInterval[]>;
  schedule_revision: number;
  connection_status: string;
};
export type TCapacityInterval = {
  start: string;
  end: string;
  kind: "working" | "google_busy" | "workshop";
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
export type TWorkshopSession = {
  id: string | null;
  starts_at: string;
  ends_at: string;
  preparation_minutes: number;
  travel_before_minutes: number;
  travel_after_minutes: number;
  trainer_ids: string[];
};
export type TWorkshopSchedule = {
  issue_id: string;
  /** @deprecated Read sessions instead. Retained during the rolling migration. */
  starts_at: string;
  /** @deprecated Read sessions instead. Retained during the rolling migration. */
  ends_at: string;
  /** @deprecated Read sessions instead. Retained during the rolling migration. */
  preparation_minutes: number;
  /** @deprecated Read sessions instead. Retained during the rolling migration. */
  travel_before_minutes: number;
  /** @deprecated Read sessions instead. Retained during the rolling migration. */
  travel_after_minutes: number;
  sessions: TWorkshopSession[];
};
export type TWorkshopScheduleInput = {
  sessions: Array<Omit<TWorkshopSession, "id">>;
};
export type TWorkshopPlanDraftInput = {
  title: string;
  duration_minutes: number;
  preparation_minutes: number;
  travel_before_minutes: number;
  travel_after_minutes: number;
  window_starts_at: string;
  window_ends_at: string;
  trainer_ids: string[];
};
export type TWorkshopPlanDraft = TWorkshopPlanDraftInput & {
  id: string;
  revision: number;
  updated_at: string;
};

export class CapacityRequestError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly retryAfterSeconds?: number
  ) {
    super(message);
    this.name = "CapacityRequestError";
  }
}

function parseRetryAfterSeconds(value: unknown): number | undefined {
  if (typeof value !== "string") return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.ceil(seconds);
  const at = Date.parse(value);
  return Number.isNaN(at) ? undefined : Math.max(0, Math.ceil((at - Date.now()) / 1000));
}

export class CapacityService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private async csrfToken(): Promise<string> {
    const response = await this.get("/auth/get-csrf-token/");
    const token = response.data?.csrf_token;
    if (!token) throw new Error("CSRF token not found");
    return token;
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

  async optIn(workspaceSlug: string) {
    const csrfToken = await this.csrfToken();
    return this.data<TTrainerProfile>(
      this.post(`/api/workspaces/${workspaceSlug}/capacity/trainers/me/`, undefined, {
        headers: { "X-CSRFTOKEN": csrfToken },
      })
    );
  }

  getOwnTrainerProfile(workspaceSlug: string) {
    return this.data<TTrainerProfile | null>(this.get(`/api/workspaces/${workspaceSlug}/capacity/trainers/me/`));
  }

  async updateSchedule(
    workspaceSlug: string,
    userId: string,
    scheduleRevision: number,
    payload: Partial<TTrainerProfile>
  ) {
    const csrfToken = await this.csrfToken();
    return this.data<TTrainerProfile>(
      this.patch(
        `/api/workspaces/${workspaceSlug}/capacity/trainers/${userId}/schedule/`,
        {
          ...payload,
          schedule_revision: scheduleRevision,
        },
        { headers: { "X-CSRFTOKEN": csrfToken } }
      )
    );
  }

  async startGoogle(workspaceSlug: string) {
    const csrfToken = await this.csrfToken();
    return this.data<{ authorization_url: string }>(
      this.post(`/api/workspaces/${workspaceSlug}/capacity/google/start/`, undefined, {
        headers: { "X-CSRFTOKEN": csrfToken },
      })
    );
  }

  listCalendars(workspaceSlug: string) {
    return this.data<TGoogleCalendarList>(this.get(`/api/workspaces/${workspaceSlug}/capacity/google/calendars/`));
  }

  async selectCalendars(workspaceSlug: string, calendarIds: string[], selectionRevision: number) {
    const csrfToken = await this.csrfToken();
    return this.data<{ selected: number; revision: number }>(
      this.put(
        `/api/workspaces/${workspaceSlug}/capacity/google/calendars/`,
        {
          calendar_ids: calendarIds,
          selection_revision: selectionRevision,
        },
        { headers: { "X-CSRFTOKEN": csrfToken } }
      )
    );
  }

  async disconnectGoogle(workspaceSlug: string, forceLocal = false) {
    const csrfToken = await this.csrfToken();
    return this.delete(`/api/workspaces/${workspaceSlug}/capacity/google/calendars/`, undefined, {
      headers: { "X-CSRFTOKEN": csrfToken },
      params: forceLocal ? { force_local: "true" } : undefined,
    });
  }

  getCapacity(workspaceSlug: string, from: string, to: string, trainerIds: string[]) {
    return this.get(`/api/workspaces/${workspaceSlug}/capacity/`, {
      params: { from, to, trainer_ids: trainerIds.join(",") },
    })
      .then((response) => response.data as TCapacityResponse)
      .catch((error) => {
        const response = error?.response;
        const payload = response?.data;
        const message =
          (typeof payload?.error === "string" && payload.error) ||
          (typeof payload?.detail === "string" && payload.detail) ||
          "Capacity could not be loaded.";
        throw new CapacityRequestError(
          message,
          typeof response?.status === "number" ? response.status : undefined,
          parseRetryAfterSeconds(response?.headers?.["retry-after"])
        );
      });
  }

  listWorkshopPlanDrafts(workspaceSlug: string) {
    return this.data<{ results: TWorkshopPlanDraft[] }>(this.get(`/api/workspaces/${workspaceSlug}/capacity/plans/`));
  }

  async createWorkshopPlanDraft(workspaceSlug: string, payload: TWorkshopPlanDraftInput) {
    const csrfToken = await this.csrfToken();
    return this.data<TWorkshopPlanDraft>(
      this.post(`/api/workspaces/${workspaceSlug}/capacity/plans/`, payload, {
        headers: { "X-CSRFTOKEN": csrfToken },
      })
    );
  }

  async updateWorkshopPlanDraft(
    workspaceSlug: string,
    draftId: string,
    revision: number,
    payload: TWorkshopPlanDraftInput
  ) {
    const csrfToken = await this.csrfToken();
    return this.data<TWorkshopPlanDraft>(
      this.put(
        `/api/workspaces/${workspaceSlug}/capacity/plans/${draftId}/`,
        { ...payload, revision },
        {
          headers: { "X-CSRFTOKEN": csrfToken },
        }
      )
    );
  }

  async deleteWorkshopPlanDraft(workspaceSlug: string, draftId: string) {
    const csrfToken = await this.csrfToken();
    return this.delete(`/api/workspaces/${workspaceSlug}/capacity/plans/${draftId}/`, undefined, {
      headers: { "X-CSRFTOKEN": csrfToken },
    });
  }

  getWorkshopSchedule(workspaceSlug: string, projectId: string, issueId: string) {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${issueId}/workshop-schedule/`)
      .then((response) => response.data as TWorkshopSchedule)
      .catch((error) => {
        if (error?.response?.status === 404) return null;
        throw new CapacityRequestError("Workshop schedule could not be loaded.", error?.response?.status);
      });
  }

  async saveWorkshopSchedule(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    schedule: TWorkshopScheduleInput
  ) {
    const csrfToken = await this.csrfToken();
    return this.data<TWorkshopSchedule>(
      this.put(
        `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${issueId}/workshop-schedule/`,
        schedule,
        { headers: { "X-CSRFTOKEN": csrfToken } }
      )
    );
  }

  async deleteWorkshopSchedule(workspaceSlug: string, projectId: string, issueId: string) {
    const csrfToken = await this.csrfToken();
    return this.delete(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${issueId}/workshop-schedule/`,
      undefined,
      { headers: { "X-CSRFTOKEN": csrfToken } }
    );
  }
}
