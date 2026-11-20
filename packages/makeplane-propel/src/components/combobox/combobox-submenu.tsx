import { Combobox as BaseCombobox } from "@base-ui/react/combobox";
import * as React from "react";

import {
  ComboboxSubmenuContext,
  type ComboboxSubmenuContextValue,
} from "./combobox-submenu-context";

type BaseRootProps<Value, Multiple extends boolean | undefined> = BaseCombobox.Root.Props<
  Value,
  Multiple
>;

export type ComboboxSubmenuProps<Value, Multiple extends boolean | undefined = false> = Omit<
  BaseRootProps<Value, Multiple>,
  "className" | "style" | "open" | "defaultOpen" | "onOpenChange" | "children"
> & {
  /**
   * The parent row that opens this nested list — a `ComboboxSubmenuTrigger`. It is a **prop**, not
   * a child, because it belongs to the PARENT list: the row is one of that combobox's options (so
   * it stays arrow-key navigable and filterable there) while everything under `children` belongs to
   * the nested combobox this part roots. Rendering it here keeps it above that nested root rather
   * than inside it.
   */
  trigger: React.ReactNode;
  /** Whether the nested list is open. Controlled; pair with `onOpenChange`. */
  open?: boolean;
  /** Whether the nested list is open on mount. Uncontrolled. @default false */
  defaultOpen?: boolean;
  /**
   * Called with the next open state when the nested list opens or closes.
   *
   * `eventDetails` is Base UI's own — forwarded verbatim, so `reason` still separates an
   * `escapeKey` close from an `outsidePress` or a completed `itemPress`. It is optional here,
   * unlike on a Base UI root, because propel drives the hover and row-press paths itself (Base UI
   * ships no combobox submenu to drive them) and exposes no way to mint details for them: those two
   * calls arrive with the flag alone.
   */
  onOpenChange?: (open: boolean, eventDetails?: BaseCombobox.Root.ChangeEventDetails) => void;
  /**
   * Open the nested list when the pointer rests on the parent row, the way a menu submenu does.
   * Turn it off for lists the user sweeps while reading, where an unasked-for search field is a
   * nuisance — the row still opens on click or on Enter while highlighted.
   *
   * @default true
   */
  openOnHover?: boolean;
  /** How long in ms the pointer must rest on the row before a hover-open fires. @default 100 */
  delay?: number;
  /**
   * How long in ms the nested list stays open after the pointer leaves both it and the row. The
   * grace period is what lets the pointer cross the gap between the two.
   *
   * @default 150
   */
  closeDelay?: number;
  /**
   * Whether `Escape` inside the nested list closes the whole stack, or only this list. Mirrors
   * `MenuSubmenu`'s prop of the same name — and its default, which steps back out to the parent
   * rather than dismissing everything.
   *
   * @default false
   */
  closeParentOnEsc?: boolean;
  /** The nested `ComboboxSubmenuContent` (and nothing else — the row goes in `trigger`). */
  children?: React.ReactNode;
};

/**
 * One nested combobox: the parent row that opens it, plus its own Base UI `Combobox.Root`. The row
 * itself carries no value — it is a way into the nested list, and only that list's items are
 * selectable — so the two roots keep separate values. Point this root's `value`/`onValueChange` at
 * the parent's state when the nested picks should land in the parent's selection, or at state of
 * its own when they should not.
 *
 * Base UI has no combobox submenu primitive (only `Menu` does), so the nesting is assembled here.
 * The nested popup still portals to `<body>`, but it stays a React-tree descendant of the parent
 * popup, which is what stops a press inside it from reading as an outside-press that dismisses the
 * parent.
 *
 * Selecting a nested item closes the nested list (Base UI's own single-select behavior) and leaves
 * the parent list open. Closing the parent too is the consumer's call — do it from `onValueChange`,
 * where the parent's own `open` is in reach.
 */
export function ComboboxSubmenu<Value, Multiple extends boolean | undefined = false>({
  trigger,
  open: openProp,
  defaultOpen = false,
  onOpenChange,
  openOnHover = true,
  delay = 100,
  closeDelay = 150,
  closeParentOnEsc = false,
  children,
  ...props
}: ComboboxSubmenuProps<Value, Multiple>) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen);
  const open = openProp ?? uncontrolledOpen;
  const triggerRef = React.useRef<HTMLDivElement | null>(null);

  // One handle for both hover timers: only ever one is pending, and every entry point cancels the
  // other first, so a single slot cannot leak a stray open behind a close.
  const timeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelScheduled = React.useCallback(() => {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);
  React.useEffect(() => cancelScheduled, [cancelScheduled]);

  const openRef = React.useRef(open);
  openRef.current = open;
  const onOpenChangeRef = React.useRef(onOpenChange);
  onOpenChangeRef.current = onOpenChange;
  // Every open change lands here — the hover and row-press paths below, and the ones Base UI
  // drives on the nested root (Escape, an outside press, a completed selection), which arrive
  // through `handleRootOpenChange` with their own `eventDetails` to forward.
  const commitOpen = React.useCallback(
    (next: boolean, eventDetails?: BaseCombobox.Root.ChangeEventDetails) => {
      cancelScheduled();
      if (openRef.current === next) return;
      setUncontrolledOpen(next);
      onOpenChangeRef.current?.(next, eventDetails);
    },
    [cancelScheduled],
  );
  const handleRootOpenChange = React.useCallback<
    NonNullable<BaseRootProps<Value, Multiple>["onOpenChange"]>
  >((next, eventDetails) => commitOpen(next, eventDetails), [commitOpen]);

  const scheduleOpen = React.useCallback(() => {
    if (!openOnHover) return;
    cancelScheduled();
    if (openRef.current) return;
    timeoutRef.current = setTimeout(() => commitOpen(true), delay);
  }, [cancelScheduled, commitOpen, delay, openOnHover]);

  const scheduleClose = React.useCallback(() => {
    cancelScheduled();
    if (!openRef.current) return;
    timeoutRef.current = setTimeout(() => commitOpen(false), closeDelay);
  }, [cancelScheduled, commitOpen, closeDelay]);

  const context = React.useMemo<ComboboxSubmenuContextValue>(
    () => ({
      open,
      setOpen: commitOpen,
      triggerRef,
      scheduleOpen,
      scheduleClose,
      cancelScheduled,
      closeParentOnEsc,
    }),
    [cancelScheduled, closeParentOnEsc, commitOpen, open, scheduleClose, scheduleOpen],
  );

  return (
    <ComboboxSubmenuContext.Provider value={context}>
      {trigger}
      <BaseCombobox.Root {...props} open={open} onOpenChange={handleRootOpenChange}>
        {children}
      </BaseCombobox.Root>
    </ComboboxSubmenuContext.Provider>
  );
}
