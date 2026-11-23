/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

const addReaction = vi.fn();
const listReactions = vi.fn();
const removeReaction = vi.fn();
const addVote = vi.fn();
const listVotes = vi.fn();

vi.mock("@plane/services", () => ({
  SitesIssueService: class {
    addReaction = addReaction;
    listReactions = listReactions;
    removeReaction = removeReaction;
    addVote = addVote;
    listVotes = listVotes;
  },
  // The reaction and vote actions never touch file uploads.
  SitesFileService: class {
    uploadAsset = vi.fn();
  },
}));

const { IssueDetailStore } = await import("./issue-detail.store");

const ANCHOR = "anchor-1";
const ISSUE = "issue-1";
const viewer = { id: "user-1", display_name: "viewer", avatar_url: null, is_bot: false };
const other = { id: "user-2", display_name: "other", avatar_url: null, is_bot: false };

function makeStore(details: Record<string, unknown>) {
  const rootStore = {
    user: { currentActor: viewer, data: { id: viewer.id } },
    publishList: { publishMap: { [ANCHOR]: { project: "project-1", workspace_detail: { slug: "ws" } } } },
  };
  // A partial root store: these actions read only the viewer and the publish settings.
  const store = new IssueDetailStore(rootStore as never);
  store.details = { [ISSUE]: { id: ISSUE, ...details } as never };
  return store;
}

describe("IssueDetailStore reactions", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "log").mockImplementation(() => {});
  });

  it("sends the first reaction on a work item whose reaction_items is null", async () => {
    addReaction.mockResolvedValue({});
    const store = makeStore({ reaction_items: null, vote_items: null });

    await store.addIssueReaction(ANCHOR, ISSUE, "1f680");

    expect(addReaction).toHaveBeenCalledWith(ANCHOR, ISSUE, { reaction: "1f680" });
    expect(listReactions).not.toHaveBeenCalled();
    expect(store.details[ISSUE].reaction_items).toEqual([{ reaction: "1f680", actor_details: viewer }]);
  });

  it("adds to the existing reactions", async () => {
    addReaction.mockResolvedValue({});
    const store = makeStore({ reaction_items: [{ reaction: "1f44d", actor_details: other }] });

    await store.addIssueReaction(ANCHOR, ISSUE, "1f680");

    expect(store.details[ISSUE].reaction_items).toEqual([
      { reaction: "1f44d", actor_details: other },
      { reaction: "1f680", actor_details: viewer },
    ]);
  });

  it("reloads a failed reaction in the work item's shape", async () => {
    addReaction.mockRejectedValue(new Error("boom"));
    listReactions.mockResolvedValue([{ id: "r-1", reaction: "1f44d", actor_detail: other, issue: ISSUE }]);
    const store = makeStore({ reaction_items: [] });

    await store.addIssueReaction(ANCHOR, ISSUE, "1f680");

    expect(console.log).toHaveBeenCalledWith("Failed to add issue reaction");
    expect(store.details[ISSUE].reaction_items).toEqual([{ reaction: "1f44d", actor_details: other }]);
  });

  it("removes a reaction from a work item whose reaction_items is null", async () => {
    removeReaction.mockResolvedValue(undefined);
    const store = makeStore({ reaction_items: null });

    await store.removeIssueReaction(ANCHOR, ISSUE, "1f680");

    expect(removeReaction).toHaveBeenCalledWith(ANCHOR, ISSUE, "1f680");
    expect(store.details[ISSUE].reaction_items).toEqual([]);
  });
});

describe("IssueDetailStore votes", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "log").mockImplementation(() => {});
  });

  it("reloads a failed vote in the work item's shape", async () => {
    addVote.mockRejectedValue(new Error("boom"));
    listVotes.mockResolvedValue([{ id: "v-1", vote: -1, actor_detail: other }]);
    const store = makeStore({ vote_items: null });

    await store.addIssueVote(ANCHOR, ISSUE, { vote: 1 });

    expect(store.details[ISSUE].vote_items).toEqual([{ vote: -1, actor_details: other }]);
  });
});
