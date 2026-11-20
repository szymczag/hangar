import { Field as BaseField } from "@base-ui/react/field";
import { mergeProps } from "@base-ui/react/merge-props";
import type * as React from "react";

import { FieldItem as FieldItemElement } from "../../elements/field/field-item";

export type FieldItemProps = Omit<BaseField.Item.Props, "className" | "style">;

// The row highlights on hover across its full padded box (`fieldItemVariants`), so a click
// anywhere in that box — not just on the control or its label — should activate the option. A
// click on anything that already handles its own click is left alone — forwarding it too would
// double-toggle, or (for a link) toggle the option as an unrelated side effect of navigating away.
// `description` is arbitrary `ReactNode`, so this can't be a finite list of the few controls this
// file knows about (Radio/Checkbox/Switch render `role="radio"|"checkbox"|"switch"` on a styled
// `<span>`, not a native `<input>`/`<button>`) — `[role]`/`[tabindex]` generalize the check to any
// interactive descendant a consumer nests in there, native or custom.
//
// `closest` walks ancestors too, so a match is only "already handled" when it lives *inside* this
// row. Without that containment check, a parent `role="radiogroup"` / `role="group"` would make
// every padding click look handled and the row would never activate.
const ALREADY_HANDLED_SELECTOR =
  "a[href], label, button, input, select, textarea, [role], [tabindex]";

function handleRowClick(event: React.MouseEvent<HTMLElement>) {
  if (!(event.target instanceof Element)) return;

  const alreadyHandled = event.target.closest(ALREADY_HANDLED_SELECTOR);
  if (
    alreadyHandled != null &&
    alreadyHandled !== event.currentTarget &&
    event.currentTarget.contains(alreadyHandled)
  ) {
    return;
  }

  // Drag-selecting label/description text ends with a click on the row; don't treat that as an
  // activate. Only bail when the selection is inside this row — leftover selection elsewhere on
  // the page must not disable row click.
  const selection = globalThis.getSelection?.();
  if (selection != null && !selection.isCollapsed && selection.rangeCount > 0) {
    const range = selection.getRangeAt(0);
    if (event.currentTarget.contains(range.commonAncestorContainer)) {
      return;
    }
  }

  event.currentTarget.querySelector("input")?.click();
}

/**
 * Groups one checkbox or radio option with its label and optional description: Base UI's
 * `Field.Item` behavior grafted onto the styled `FieldItem` element (rule 1a).
 */
export function FieldItem(props: FieldItemProps) {
  return (
    <BaseField.Item
      {...mergeProps({ onClick: handleRowClick }, props)}
      render={<FieldItemElement />}
    />
  );
}
