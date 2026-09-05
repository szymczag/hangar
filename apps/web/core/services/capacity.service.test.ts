/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  CapacityRequestError,
  CapacityService,
  type TTrainerProfile,
  type TWorkshopSchedule,
} from "./capacity.service";

const csrfToken = "server-issued-csrf-token";
const csrfHeaders = { headers: { "X-CSRFTOKEN": csrfToken } };

describe("CapacityService CSRF requests", () => {
  let service: CapacityService;

  beforeEach(() => {
    service = new CapacityService();
    vi.spyOn(service, "get").mockResolvedValue({ data: { csrf_token: csrfToken } } as never);
  });

  it("sends the server-issued token when opting in", async () => {
    const profile = { id: "trainer-id" } as TTrainerProfile;
    const post = vi.spyOn(service, "post").mockResolvedValue({ data: profile } as never);

    await expect(service.optIn("workspace")).resolves.toBe(profile);

    expect(service.get).toHaveBeenCalledWith("/auth/get-csrf-token/");
    expect(post).toHaveBeenCalledWith("/api/workspaces/workspace/capacity/trainers/me/", undefined, csrfHeaders);
  });

  it("sends the token when updating a trainer schedule", async () => {
    const profile = { id: "trainer-id" } as TTrainerProfile;
    const patch = vi.spyOn(service, "patch").mockResolvedValue({ data: profile } as never);

    await service.updateSchedule("workspace", "user-id", 7, { timezone: "Europe/Warsaw" });

    expect(patch).toHaveBeenCalledWith(
      "/api/workspaces/workspace/capacity/trainers/user-id/schedule/",
      { timezone: "Europe/Warsaw", schedule_revision: 7 },
      csrfHeaders
    );
  });

  it("sends the token when starting Google authorization", async () => {
    const post = vi
      .spyOn(service, "post")
      .mockResolvedValue({ data: { authorization_url: "https://accounts.google.test/authorize" } } as never);

    await service.startGoogle("workspace");

    expect(post).toHaveBeenCalledWith("/api/workspaces/workspace/capacity/google/start/", undefined, csrfHeaders);
  });

  it("sends the token when selecting calendars", async () => {
    const put = vi.spyOn(service, "put").mockResolvedValue({ data: { selected: 2, revision: 4 } } as never);

    await service.selectCalendars("workspace", ["primary", "training"], 3);

    expect(put).toHaveBeenCalledWith(
      "/api/workspaces/workspace/capacity/google/calendars/",
      { calendar_ids: ["primary", "training"], selection_revision: 3 },
      csrfHeaders
    );
  });

  it.each([
    [false, undefined],
    [true, { force_local: "true" }],
  ])("sends the token and correct query parameters when disconnecting Google", async (forceLocal, params) => {
    const deleteRequest = vi.spyOn(service, "delete").mockResolvedValue({ data: undefined } as never);

    await service.disconnectGoogle("workspace", forceLocal);

    expect(deleteRequest).toHaveBeenCalledWith("/api/workspaces/workspace/capacity/google/calendars/", undefined, {
      ...csrfHeaders,
      params,
    });
  });

  it("sends the token when saving a workshop schedule", async () => {
    const schedule = {
      sessions: [
        {
          starts_at: "2026-09-07T09:00:00+02:00",
          ends_at: "2026-09-07T10:00:00+02:00",
          preparation_minutes: 15,
          travel_before_minutes: 0,
          travel_after_minutes: 0,
          trainer_ids: ["trainer-id"],
        },
      ],
    };
    const savedSchedule = {
      issue_id: "issue-id",
      ...schedule.sessions[0],
      sessions: schedule.sessions.map((session) => ({ ...session, id: "session-id" })),
    } satisfies TWorkshopSchedule;
    const put = vi.spyOn(service, "put").mockResolvedValue({ data: savedSchedule } as never);

    await expect(service.saveWorkshopSchedule("workspace", "project-id", "issue-id", schedule)).resolves.toBe(
      savedSchedule
    );

    expect(put).toHaveBeenCalledWith(
      "/api/workspaces/workspace/projects/project-id/work-items/issue-id/workshop-schedule/",
      schedule,
      csrfHeaders
    );
  });

  it("treats a missing workshop schedule as an empty property", async () => {
    vi.mocked(service.get).mockRejectedValue({ response: { status: 404 } });

    await expect(service.getWorkshopSchedule("workspace", "project-id", "issue-id")).resolves.toBeNull();
  });

  it("preserves a workshop schedule loading failure", async () => {
    vi.mocked(service.get).mockRejectedValue({ response: { status: 503 } });

    const error = await service
      .getWorkshopSchedule("workspace", "project-id", "issue-id")
      .catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(CapacityRequestError);
    expect(error).toMatchObject({ status: 503, message: "Workshop schedule could not be loaded." });
  });

  it("sends the token when deleting a workshop schedule", async () => {
    const deleteRequest = vi.spyOn(service, "delete").mockResolvedValue({ data: undefined } as never);

    await service.deleteWorkshopSchedule("workspace", "project-id", "issue-id");

    expect(deleteRequest).toHaveBeenCalledWith(
      "/api/workspaces/workspace/projects/project-id/work-items/issue-id/workshop-schedule/",
      undefined,
      csrfHeaders
    );
  });

  it("saves a coordinator planning draft with CSRF and optimistic revision", async () => {
    const payload = {
      title: "NetSec workshop",
      duration_minutes: 240,
      preparation_minutes: 30,
      travel_before_minutes: 60,
      travel_after_minutes: 60,
      window_starts_at: "2026-09-07T00:00:00.000Z",
      window_ends_at: "2026-09-14T00:00:00.000Z",
      trainer_ids: ["trainer-id"],
    };
    const put = vi
      .spyOn(service, "put")
      .mockResolvedValue({ data: { ...payload, id: "draft-id", revision: 4 } } as never);

    await service.updateWorkshopPlanDraft("workspace", "draft-id", 3, payload);

    expect(put).toHaveBeenCalledWith(
      "/api/workspaces/workspace/capacity/plans/draft-id/",
      { ...payload, revision: 3 },
      csrfHeaders
    );
  });

  it("does not send a mutation when the CSRF endpoint omits the token", async () => {
    vi.mocked(service.get).mockResolvedValue({ data: {} } as never);
    const post = vi.spyOn(service, "post");

    await expect(service.optIn("workspace")).rejects.toThrow("CSRF token not found");
    expect(post).not.toHaveBeenCalled();
  });

  it("retains status, DRF detail, and Retry-After for capacity throttling", async () => {
    vi.mocked(service.get).mockRejectedValue({
      response: {
        status: 429,
        data: { detail: "Request was throttled." },
        headers: { "retry-after": "12" },
      },
    });

    const error = await service
      .getCapacity("workspace", "2026-09-07T00:00:00Z", "2026-09-14T00:00:00Z", [])
      .catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(CapacityRequestError);
    expect(error).toMatchObject({
      name: "CapacityRequestError",
      message: "Request was throttled.",
      status: 429,
      retryAfterSeconds: 12,
    });
  });
});
