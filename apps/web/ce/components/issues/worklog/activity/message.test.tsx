/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { IIssueActivity } from "@plane/types";

vi.mock("next/navigation", () => ({ useParams: () => ({ workspaceSlug: "vr" }) }));
vi.mock("@/hooks/store/use-label", () => ({ useLabel: () => ({}) }));
vi.mock("@/hooks/use-platform-os", () => ({ usePlatformOS: () => ({ isMobile: false }) }));

import { ActivityIcon, ActivityMessage } from "@/components/core/activity";
import { WorklogActivityMessage } from "./message";

const here = path.dirname(fileURLToPath(import.meta.url));
// The duration is the emphasised part of each sentence.
const strong = (value: string) => `<span class="font-medium text-primary">${value}</span>`;

const worklogRow = (overrides: Partial<IIssueActivity>) =>
  ({
    id: "activity",
    field: "worklog",
    verb: "created",
    old_value: undefined,
    new_value: "45m",
    actor_detail: { id: "olga", display_name: "olga" },
    workspace_detail: { slug: "vr" },
    ...overrides,
  }) as unknown as IIssueActivity;

describe("WorklogActivityMessage", () => {
  it("says what was logged, changed or removed, with the duration", () => {
    expect(renderToStaticMarkup(<WorklogActivityMessage verb="created" oldValue={undefined} newValue="45m" />)).toBe(
      `logged ${strong("45m")}`
    );
    expect(renderToStaticMarkup(<WorklogActivityMessage verb="updated" oldValue="30m" newValue="1h" />)).toBe(
      `updated logged time from ${strong("30m")} to ${strong("1h")}`
    );
    expect(renderToStaticMarkup(<WorklogActivityMessage verb="deleted" oldValue="1h" newValue={undefined} />)).toBe(
      `removed logged time ${strong("1h")}`
    );
  });
});

// O2 (0.5.0 stack test): the profile activity printed a worklog row as a bare
// "olga 1 minute ago". The profile feeds render through ActivityMessage, which
// had no worklog entry.
describe("ActivityMessage for a worklog row", () => {
  it("reads like the work item feed", () => {
    expect(renderToStaticMarkup(<ActivityMessage activity={worklogRow({})} />)).toBe(`logged ${strong("45m")}`);
    expect(renderToStaticMarkup(<ActivityMessage activity={worklogRow({ verb: "updated", old_value: "30m" })} />)).toBe(
      `updated logged time from ${strong("30m")} to ${strong("45m")}`
    );
  });

  it("has an icon", () => {
    expect(renderToStaticMarkup(<ActivityIcon activity={worklogRow({})} />)).toContain("<svg");
  });

  it.each([
    "../../../../../components/profile/activity/activity-list.tsx",
    "../../../../../components/profile/overview/activity.tsx",
  ])("%s still leaves out rows the reader may not see before rendering them (S20)", (file) => {
    const source = readFileSync(path.join(here, file), "utf8");
    expect(source).toMatch(/!isWorklogHiddenForRole\(/);
    expect(source).toMatch(/<ActivityMessage /);
  });
});
