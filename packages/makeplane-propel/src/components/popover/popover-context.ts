// Private (index does not export `*-context.ts`). Hover-only click suppression:
// Base UI has no `openOnClick`, so the trigger registers the real DOM node and Root
// cancels mouse `trigger-press` for that node. WeakSet so nothing leaks on the
// public element.

const clickDisabledTriggers = new WeakSet<Element>();

export function setTriggerClickPolicy(node: Element | null, openOnClick: boolean) {
  if (!node) return;
  if (openOnClick) clickDisabledTriggers.delete(node);
  else clickDisabledTriggers.add(node);
}

export function isClickDisabledTrigger(trigger: Element | undefined) {
  return trigger != null && clickDisabledTriggers.has(trigger);
}
