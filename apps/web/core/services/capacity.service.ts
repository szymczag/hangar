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
  timezone_source?: "google_calendar" | "profile";
  training_events_enabled?: boolean;
  weekly_schedule: Record<string, TScheduleInterval[]>;
  schedule_revision: number;
  connection_status: string;
};
export type TCapacityInterval = {
  start: string;
  end: string;
  kind: "working" | "google_busy" | "google_training" | "workshop" | "workshop_hold";
  work_item?: { id: string; name: string; project_id: string } | null;
  /** Recorded training title, when the viewer is entitled to read it. */
  summary?: string | null;
};
export type TTrainerCapacity = {
  trainer_id: string;
  display_name: string;
  timezone: string;
  timezone_source?: "google_calendar" | "profile";
  connection_status: string;
  availability_status:
    | "fresh"
    | "stale"
    | "not_connected"
    | "reauthentication_required"
    | "rate_limited"
    | "provider_unavailable"
    | string;
  training_status?: string;
  training_workload?: {
    confirmed_sessions: number;
    confirmed_minutes: number;
    pending_sessions: number;
    pending_minutes: number;
    events: Array<{ key: string; start: string; end: string; status: string; linked: boolean }>;
  };
  workload?: {
    workshop_count: number;
    session_count: number;
    delivery_minutes: number;
    buffer_minutes: number;
    hold_count: number;
    hold_minutes: number;
  };
  working_minutes: number;
  google_busy_minutes: number;
  workshop_minutes: number;
  hold_minutes: number;
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
  sessions: Array<Omit<TWorkshopSession, "id"> & { id?: string | null }>;
};
/** The Workshop work item a plan is for, as much of it as a picker needs. */
export type TPlanIssue = {
  id: string;
  name: string;
  sequence_id: number;
  project_id: string;
  project_identifier: string;
};
export type TWorkshopPlanDraftInput = {
  title: string;
  duration_minutes: number;
  preparation_minutes: number;
  travel_before_minutes: number;
  travel_after_minutes: number;
  trainer_ids: string[];
  /** Null while the plan is still exploratory; such a plan cannot be scheduled. */
  issue_id: string | null;
};
export type TWorkshopPlanDraft = TWorkshopPlanDraftInput & {
  id: string;
  revision: number;
  created_at?: string;
  last_session?: { id: string; starts_at: string; ends_at: string } | null;
  updated_at: string;
  hold: TWorkshopPlanHold | null;
  issue: TPlanIssue | null;
};
export type TScheduledPlan = {
  revision: number;
  issue: TPlanIssue;
  session: { id: string; starts_at: string; ends_at: string; trainer_ids: string[] };
};
export type TWorkshopPlanHold = {
  id: string;
  trainer_id: string;
  trainer_name: string;
  workshop_starts_at: string;
  workshop_ends_at: string;
  blocked_starts_at: string;
  blocked_ends_at: string;
  expires_at: string;
  status: "active" | "released" | "confirmed";
};

export type TChecklistAssigneeMode = "unassigned" | "fixed" | "workshop_trainer" | "role";
export type TWorkshopChecklistItem = {
  id?: string;
  position: number;
  title: string;
  description: string;
  assignee_id: string | null;
  assignee_mode: TChecklistAssigneeMode;
  /** Set only in "role" mode; everyone holding the role is assigned. */
  role_id: string | null;
  /** Days from the workshop's first session. Negative is before it. */
  offset_days: number;
};
/** A standing job in running a workshop, and who currently does it. */
export type TWorkshopRole = {
  id: string;
  name: string;
  member_ids: string[];
};
export type TWorkshopRoleInput = {
  name: string;
  member_ids: string[];
};
export type TWorkshopChecklistTemplate = {
  id: string;
  name: string;
  /** Applied to a new Workshop unless another template is chosen. */
  is_default: boolean;
  items: TWorkshopChecklistItem[];
};
export type TWorkshopChecklistTemplateInput = {
  name: string;
  is_default: boolean;
  items: Array<Omit<TWorkshopChecklistItem, "id">>;
};
export type TAppliedChecklist = {
  created: Array<{ id: string; name: string; target_date: string | null }>;
  /** People the template names who cannot hold work in this project. */
  skipped_assignees: string[];
};

/** Why a trainer's row may not be trustworthy; `ok` is the only one that counts. */
export type TTrainingSyncStatus =
  | "ok"
  | "stale"
  | "never_synced"
  | "consent_missing"
  | "reauth_required"
  | "not_connected"
  | "access_lost";
export type TTrainingReportRow = {
  trainer_id: string;
  display_name: string;
  sync_status: TTrainingSyncStatus;
  counts_towards_totals: boolean;
  workshop_count: number;
  session_count: number;
  delivery_minutes: number;
  buffer_minutes: number;
  external_confirmed_sessions: number;
  external_confirmed_minutes: number;
  external_pending_sessions: number;
  external_pending_minutes: number;
};
export type TTrainingReport = {
  from: string;
  to: string;
  /** Oldest successful sweep behind these figures; null when nothing has swept. */
  data_as_of: string | null;
  coverage: {
    window_starts_at: string | null;
    window_ends_at: string | null;
    requested_range_covered: boolean;
    calendars: Array<{
      rule_label: string;
      last_success_at: string | null;
      last_full_scan_at: string | null;
      status: "ok" | "stale" | "unavailable";
    }>;
  };
  trainers: TTrainingReportRow[];
};
/** A training that exists in the calendar but not yet as a work item. */
export type TPendingTrainingImport = {
  id: string;
  trainer_id: string;
  display_name: string;
  starts_at: string;
  ends_at: string;
  minutes: number;
  status: "confirmed" | "pending";
  rule_label: string;
  title: string | null;
};
export type TTrainingImportResult = {
  created: Array<{ occurrence_id: string; issue_id: string; name: string }>;
  skipped: Array<{ occurrence_id: string; reason: string }>;
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

  /** Start the Google consent that lets a rule write into its calendar. */
  async startCalendarWriter(workspaceSlug: string, ruleId: string) {
    const csrfToken = await this.csrfToken();
    return this.data<{ authorization_url: string }>(
      this.post(
        `/api/workspaces/${workspaceSlug}/capacity/google/start/`,
        { calendar_writer: true, rule_id: ruleId },
        { headers: { "X-CSRFTOKEN": csrfToken } }
      )
    );
  }

  async startGoogle(workspaceSlug: string, trainingEvents = false) {
    const csrfToken = await this.csrfToken();
    return this.data<{ authorization_url: string }>(
      this.post(
        `/api/workspaces/${workspaceSlug}/capacity/google/start/`,
        trainingEvents ? { training_events: true } : undefined,
        {
          headers: { "X-CSRFTOKEN": csrfToken },
        }
      )
    );
  }

  listTrainingRules(workspaceSlug: string) {
    return this.data<{
      results: Array<{
        id: string;
        label: string;
        calendar_id: string;
        /** Whether this rule can write into its calendar, and why not. */
        writer_status: "not_connected" | "ok" | "scope_missing" | "reauthorization_required";
        writer_email: string;
      }>;
    }>(this.get(`/api/workspaces/${workspaceSlug}/capacity/google/training-rules/`));
  }
  async addTrainingRule(workspaceSlug: string, rule: { label: string; calendar_id: string }) {
    const token = await this.csrfToken();
    return this.data(
      this.post(`/api/workspaces/${workspaceSlug}/capacity/google/training-rules/`, rule, {
        headers: { "X-CSRFTOKEN": token },
      })
    );
  }
  async deleteTrainingRule(workspaceSlug: string, id: string) {
    const token = await this.csrfToken();
    return this.data(
      this.delete(`/api/workspaces/${workspaceSlug}/capacity/google/training-rules/${id}/`, {
        headers: { "X-CSRFTOKEN": token },
      })
    );
  }
  async linkTrainingEvent(workspaceSlug: string, eventKey: string, sessionId: string) {
    const token = await this.csrfToken();
    return this.data(
      this.post(
        `/api/workspaces/${workspaceSlug}/capacity/google/training-links/`,
        { event_key: eventKey, session_id: sessionId },
        { headers: { "X-CSRFTOKEN": token } }
      )
    );
  }
  async unlinkTrainingEvent(workspaceSlug: string, eventKey: string) {
    const token = await this.csrfToken();
    return this.data(
      this.delete(`/api/workspaces/${workspaceSlug}/capacity/google/training-links/${eventKey}/`, {
        headers: { "X-CSRFTOKEN": token },
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

  getCapacity(workspaceSlug: string, from: string, to: string, trainerIds: string[], signal?: AbortSignal) {
    return this.get(`/api/workspaces/${workspaceSlug}/capacity/`, {
      params: { from, to, trainer_ids: trainerIds.join(",") },
      signal,
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

  /** Workshop work items the viewer can plan, for the planner's picker. */
  getTrainingReport(workspaceSlug: string, from: string, to: string) {
    return this.data<TTrainingReport>(
      this.get(`/api/workspaces/${workspaceSlug}/capacity/training-report/`, { params: { from, to } })
    );
  }

  /**
   * The CSV lives behind the same endpoint, so the browser downloads it directly
   * rather than this service buffering it only to hand it back.
   *
   * `export`, not `format`: DRF reserves the latter for renderer negotiation and
   * answers 404 for a value it does not know.
   */
  trainingReportCsvUrl(workspaceSlug: string, from: string, to: string) {
    const params = new URLSearchParams({ from, to, export: "csv" });
    return `${API_BASE_URL}/api/workspaces/${workspaceSlug}/capacity/training-report/?${params}`;
  }

  listPendingTrainingImports(workspaceSlug: string, from: string, to: string) {
    return this.data<{ from: string; to: string; results: TPendingTrainingImport[] }>(
      this.get(`/api/workspaces/${workspaceSlug}/capacity/training-imports/`, { params: { from, to } })
    );
  }

  async importTrainings(workspaceSlug: string, projectId: string, occurrenceIds: string[]) {
    const csrfToken = await this.csrfToken();
    return this.data<TTrainingImportResult>(
      this.post(
        `/api/workspaces/${workspaceSlug}/capacity/training-imports/`,
        { project_id: projectId, occurrence_ids: occurrenceIds },
        { headers: { "X-CSRFTOKEN": csrfToken } }
      )
    );
  }

  searchWorkshops(workspaceSlug: string, query: string) {
    return this.data<{ results: TPlanIssue[] }>(
      this.get(`/api/workspaces/${workspaceSlug}/capacity/workshops/`, { params: { query } })
    );
  }

  listWorkshopPlanDrafts(workspaceSlug: string) {
    return this.data<{ results: TWorkshopPlanDraft[] }>(this.get(`/api/workspaces/${workspaceSlug}/capacity/plans/`));
  }

  async updatePlanMetadata(
    workspaceSlug: string,
    draftId: string,
    revision: number,
    data: { title: string; issue_id: string | null }
  ) {
    const csrfToken = await this.csrfToken();
    return this.data<TWorkshopPlanDraft>(
      this.patch(
        `/api/workspaces/${workspaceSlug}/capacity/plans/${draftId}/`,
        { revision, ...data },
        { headers: { "X-CSRFTOKEN": csrfToken } }
      )
    );
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

  async holdWorkshopPlan(
    workspaceSlug: string,
    draftId: string,
    revision: number,
    trainerId: string,
    workshopStartsAt: string
  ) {
    const csrfToken = await this.csrfToken();
    return this.data<{ hold: TWorkshopPlanHold; revision: number }>(
      this.post(
        `/api/workspaces/${workspaceSlug}/capacity/plans/${draftId}/hold/`,
        { revision, trainer_id: trainerId, workshop_starts_at: workshopStartsAt },
        { headers: { "X-CSRFTOKEN": csrfToken } }
      )
    );
  }

  /** Spend the hold: it becomes a session on the work item the plan is for. */
  async scheduleWorkshopPlan(
    workspaceSlug: string,
    draftId: string,
    revision: number,
    options?: { idempotency_key: string; trainer_id?: string; workshop_starts_at?: string }
  ) {
    const csrfToken = await this.csrfToken();
    return this.data<TScheduledPlan>(
      this.post(
        `/api/workspaces/${workspaceSlug}/capacity/plans/${draftId}/schedule/`,
        { revision, ...options },
        { headers: { "X-CSRFTOKEN": csrfToken } }
      )
    );
  }

  async releaseWorkshopPlanHold(workspaceSlug: string, draftId: string) {
    const csrfToken = await this.csrfToken();
    return this.data<{ revision: number }>(
      this.delete(`/api/workspaces/${workspaceSlug}/capacity/plans/${draftId}/hold/`, undefined, {
        headers: { "X-CSRFTOKEN": csrfToken },
      })
    );
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

  listWorkshopRoles(workspaceSlug: string) {
    return this.data<{ results: TWorkshopRole[] }>(
      this.get(`/api/workspaces/${workspaceSlug}/capacity/workshop-roles/`)
    );
  }

  async createWorkshopRole(workspaceSlug: string, role: TWorkshopRoleInput) {
    const csrfToken = await this.csrfToken();
    return this.data<TWorkshopRole>(
      this.post(`/api/workspaces/${workspaceSlug}/capacity/workshop-roles/`, role, {
        headers: { "X-CSRFTOKEN": csrfToken },
      })
    );
  }

  async updateWorkshopRole(workspaceSlug: string, roleId: string, role: TWorkshopRoleInput) {
    const csrfToken = await this.csrfToken();
    return this.data<TWorkshopRole>(
      this.put(`/api/workspaces/${workspaceSlug}/capacity/workshop-roles/${roleId}/`, role, {
        headers: { "X-CSRFTOKEN": csrfToken },
      })
    );
  }

  async deleteWorkshopRole(workspaceSlug: string, roleId: string) {
    const csrfToken = await this.csrfToken();
    return this.delete(`/api/workspaces/${workspaceSlug}/capacity/workshop-roles/${roleId}/`, undefined, {
      headers: { "X-CSRFTOKEN": csrfToken },
    });
  }

  listChecklistTemplates(workspaceSlug: string) {
    return this.data<{ results: TWorkshopChecklistTemplate[] }>(
      this.get(`/api/workspaces/${workspaceSlug}/capacity/checklist-templates/`)
    );
  }

  async createChecklistTemplate(workspaceSlug: string, template: TWorkshopChecklistTemplateInput) {
    const csrfToken = await this.csrfToken();
    return this.data<TWorkshopChecklistTemplate>(
      this.post(`/api/workspaces/${workspaceSlug}/capacity/checklist-templates/`, template, {
        headers: { "X-CSRFTOKEN": csrfToken },
      })
    );
  }

  async updateChecklistTemplate(workspaceSlug: string, templateId: string, template: TWorkshopChecklistTemplateInput) {
    const csrfToken = await this.csrfToken();
    return this.data<TWorkshopChecklistTemplate>(
      this.put(`/api/workspaces/${workspaceSlug}/capacity/checklist-templates/${templateId}/`, template, {
        headers: { "X-CSRFTOKEN": csrfToken },
      })
    );
  }

  async deleteChecklistTemplate(workspaceSlug: string, templateId: string) {
    const csrfToken = await this.csrfToken();
    return this.delete(`/api/workspaces/${workspaceSlug}/capacity/checklist-templates/${templateId}/`, undefined, {
      headers: { "X-CSRFTOKEN": csrfToken },
    });
  }

  /** Create the checklist subtasks on a Workshop. Omitting the template uses the default one. */
  async applyChecklist(workspaceSlug: string, projectId: string, issueId: string, templateId?: string) {
    const csrfToken = await this.csrfToken();
    return this.data<TAppliedChecklist>(
      this.post(
        `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${issueId}/apply-checklist/`,
        templateId ? { template_id: templateId } : undefined,
        { headers: { "X-CSRFTOKEN": csrfToken } }
      )
    );
  }
}
