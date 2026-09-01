/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Applies an operator-supplied browser-tab icon over the built-in one.
 *
 * The icon links are declared by `links()` in `app/root.tsx`, which is evaluated
 * without access to instance configuration — that arrives client-side. So the
 * built-in icon is what the browser sees first and this swaps it afterwards,
 * the same way `PageHead` sets `document.title`. A brief flash of the Hangar
 * mark is the cost of not coupling the document to the config request.
 *
 * The built-in links are detached rather than left in place: several browsers
 * prefer `shortcut icon` or the first declaration they parsed, so appending a
 * second icon is not reliably an override.
 */

const MANAGED = "data-hangar-instance-favicon";
const BUILT_IN_SELECTOR = 'link[rel~="icon"]:not([' + MANAGED + "])";

let detached: { element: HTMLLinkElement; parent: Node; next: ChildNode | null }[] = [];

function restoreBuiltIn(): void {
  for (const { element, parent, next } of detached) {
    try {
      parent.insertBefore(element, next);
    } catch {
      // The head was rebuilt underneath us; the built-in icon is already there.
    }
  }
  detached = [];
}

export function applyInstanceFavicon(faviconUrl: string | undefined | null): void {
  if (typeof document === "undefined") return;

  const existing = document.head.querySelector<HTMLLinkElement>(`link[${MANAGED}]`);
  const url = (faviconUrl ?? "").trim();

  if (!url) {
    existing?.remove();
    restoreBuiltIn();
    return;
  }

  if (existing) {
    // Same icon, nothing to do — reassigning href would refetch it on every render.
    if (existing.getAttribute("href") !== url) existing.setAttribute("href", url);
    return;
  }

  for (const element of Array.from(document.head.querySelectorAll<HTMLLinkElement>(BUILT_IN_SELECTOR))) {
    detached.push({ element, parent: element.parentNode ?? document.head, next: element.nextSibling });
    element.remove();
  }

  const link = document.createElement("link");
  link.setAttribute(MANAGED, "");
  link.rel = "icon";
  link.href = url;
  document.head.appendChild(link);
}
