import {
  Toast as BaseToast,
  type ToastManagerAddOptions,
  type ToastManagerPromiseOptions,
  type ToastManagerUpdateOptions,
  type ToastObject,
} from "@base-ui/react/toast";
import { useCallback, useMemo } from "react";
import type * as React from "react";

import {
  Toast as ToastElement,
  ToastAction,
  ToastActionButton,
  ToastActionGroup,
  ToastActions,
  ToastCloseGroup,
  ToastContent,
  ToastDescription,
  type ToastVariant,
  ToastTextGroup,
  ToastTitle,
} from "../../elements/toast/index";
import { LinearProgress } from "../linear-progress/index";
import {
  createToastManager as createBaseToastManager,
  useToastManager as useBaseToastManager,
} from "./manager";
import { ToastStatusIcon } from "./toast-status-icon";

// The semantic intent of a toast (Figma "Property 1": Default / Variant2 / Variant3
// = success / danger / info). `warning` and `neutral` round out the standard set.
// Each variant auto-selects a filled status icon and its color token (see `ToastStatusIcon`) —
// the caller never passes an icon. `variant` is required and lives in the toast's `data`
// payload (see `ToastData`).
export type { ToastVariant };

/**
 * A single action rendered inside a toast. The toast is a portaled, auto-dismissing surface with no
 * `className`/`style` escape hatch, so an action is declared as data (label + handler, or label +
 * `href`) rather than arbitrary markup — keeping the styling on-token and the API closed.
 */
export type ToastAction = {
  /** Visible button text — also its accessible name. */
  label: string;
  /** Invoked on click (and Enter/Space on the button form, since it's a real `<button>`). */
  onClick?: React.MouseEventHandler<HTMLElement>;
  /**
   * Renders the action as a link to this URL instead of a button. Still data — no markup crosses
   * the boundary — so the action keeps its on-token styling and the API stays closed. Prefer it
   * over an `onClick` that calls `window.open`: a link supports middle-click, cmd/ctrl-click,
   * right-click → "Copy link address" and the browser's status-bar URL preview, and assistive tech
   * announces it as a link rather than a button. `onClick` still fires if both are given.
   *
   * It renders a plain `<a>`, so in a client-routed app a same-tab `href` is a full page load, not
   * a route transition. Use `href` for external or new-tab targets, and keep an `onClick` for
   * in-app navigation that should stay client-side.
   */
  href?: string;
  /**
   * Only meaningful alongside `href`.
   *
   * @default "_self" — `"_blank"` also sets `rel="noopener noreferrer"`.
   */
  target?: "_self" | "_blank";
};

/**
 * Custom data carried on every toast queued through this component. `add({ ... data: { variant }
 * })` selects the status icon + color; `variant` is required so the caller always chooses the
 * intent explicitly. Action buttons are optional and map directly to Figma's toast
 * `button`/`button2` booleans (node 1146-61689): `actions` is the left cluster of 1–2 buttons,
 * `primaryAction` is the right-aligned button shown on the success treatment.
 */
export type ToastData = {
  /** Semantic intent — drives the status icon and its color. */
  variant: ToastVariant;
  /**
   * Completion (0–100) of a long-running task the toast is reporting. When set, a thin `Progress`
   * bar with a `%` label renders between the description and the action row (Figma node
   * 1146-61689). Omit it for a plain toast.
   */
  progress?: number;
  /**
   * Left-aligned action cluster (Figma's `button` / `button2`). One or two buttons; extras beyond
   * two are ignored to stay faithful to the design.
   */
  actions?: ToastAction[];
  /**
   * Optional right-aligned action, rendered whenever it's provided (the component doesn't restrict
   * it by variant). In Figma it appears on the success treatment. Like `actions`, it renders as a
   * button, or as a link when it carries an `href`.
   */
  primaryAction?: ToastAction;
};

// `danger`/`warning` toasts are urgent: Base UI's `priority: "high"` makes the toast
// render as `role="alertdialog"` and adds an assertive off-screen announcer, matching
// the toast a11y spec (error/warning → role="alert"/aria-live="assertive", interrupts
// immediately; success/info → role="status"/aria-live="polite", announced after the
// current utterance). `priority` lives on Base UI's toast object (set at `add()` time,
// not on `Toast.Root`), so it's derived here rather than in the `Toast` renderer below.
function toastPriority(variant: ToastVariant | undefined): "low" | "high" {
  return variant === "danger" || variant === "warning" ? "high" : "low";
}

// Figma's guidance is explicit: "Don't auto-dismiss error toasts too quickly — give extra
// time ... so users can read the failure reason." 8s (vs. Base UI's 5s default) is a
// placeholder for "extra time" — the spec gives no exact figure. Returns `undefined` for
// every other variant so the default/caller-supplied timeout passes through untouched.
function toastTimeout(variant: ToastVariant | undefined): number | undefined {
  return variant === "danger" || variant === "warning" ? 8000 : undefined;
}

// Derived here rather than exposed: the action API carries no `rel` field.
function relFor(target: ToastAction["target"]): string | undefined {
  return target === "_blank" ? "noopener noreferrer" : undefined;
}

export type ToastUpdate<Data extends ToastData> =
  | ToastManagerUpdateOptions<Data>
  | ((previous: ToastObject<Data>) => ToastManagerUpdateOptions<Data>);

// Injects the derived `priority`/`timeout` into an `add`/`update` payload — but only when the
// payload actually sets a `variant` (an `update` that only touches, say, the title must not
// clobber the toast's existing priority/timeout). An explicit `priority`/`timeout` in the
// payload still wins (spread after the derived defaults).
//
// Base UI merges as `{...prevToast, ...updates}` and reschedules the timer when
// `Object.hasOwn(updates, "timeout")` (even if the value is unchanged). So we must not
// force-write either key on every data-carrying update:
// - `add` (no `prev`): always write both so the toast starts with the right role + timer.
// - `update` with `prev` when the *derived* priority/timeout for the new variant differs
//   from the previous variant's: write only the keys that changed (including `timeout:
//   undefined` so an 8s danger override is cleared on downgrade, not stuck).
// - `update` with `prev` when derived values are unchanged: leave both keys alone so
//   `timeout: 0` progress toasts, custom timers, and an explicit `priority: "high"` on a
//   non-urgent variant survive progress-style updates that restate the same `variant`.
// - `update` without `prev`: fall back to the always-write path.
function withVariantDefaults<T extends ToastData>(
  options: ToastManagerUpdateOptions<T>,
  prev?: ToastData,
): ToastManagerUpdateOptions<T> {
  const variant = options.data?.variant;
  if (variant === undefined) {
    return options;
  }

  const derivedPriority = toastPriority(variant);
  const derivedTimeout = toastTimeout(variant);

  if (prev === undefined) {
    return {
      priority: derivedPriority,
      timeout: derivedTimeout,
      ...options,
    };
  }

  // Start from the caller's payload only — do not pre-write derived keys. Re-inject a key
  // only when its derived value actually changed for this variant transition; otherwise
  // Base UI's merge keeps the toast's existing priority/timeout (and does not reschedule).
  let next: ToastManagerUpdateOptions<T> = options;

  if (!Object.hasOwn(options, "priority") && toastPriority(prev.variant) !== derivedPriority) {
    next = { priority: derivedPriority, ...next };
  }

  if (!Object.hasOwn(options, "timeout") && toastTimeout(prev.variant) !== derivedTimeout) {
    next = { timeout: derivedTimeout, ...next };
  }

  return next;
}

// `promise()`'s `success`/`error` outcomes are each *either* a static payload *or* a function of
// the settled value/error — wrap whichever form is given so both still pick up the derived
// defaults. `loading` only ever takes the static form.
function wrapPromiseOutcome<T extends ToastData, Arg>(
  outcome:
    | string
    | ToastManagerUpdateOptions<T>
    | ((arg: Arg) => string | ToastManagerUpdateOptions<T>),
): string | ToastManagerUpdateOptions<T> | ((arg: Arg) => string | ToastManagerUpdateOptions<T>) {
  if (typeof outcome === "function") {
    return (arg: Arg) => {
      const resolved = outcome(arg);
      return typeof resolved === "string" ? resolved : withVariantDefaults(resolved);
    };
  }
  return typeof outcome === "string" ? outcome : withVariantDefaults(outcome);
}

function withPromiseDefaults<Value, T extends ToastData>(
  options: ToastManagerPromiseOptions<Value, T>,
): ToastManagerPromiseOptions<Value, T> {
  return {
    ...options,
    loading:
      typeof options.loading === "string" ? options.loading : withVariantDefaults(options.loading),
    success: wrapPromiseOutcome(options.success),
    error: wrapPromiseOutcome(options.error),
  };
}

// Re-export Base UI's toast manager hook + global manager factory with Propel's
// `ToastData` as the default payload. Consumers can still pass a narrower extension
// type, but the default path requires the `variant` data this renderer needs. All three
// mutating methods (`add`/`update`/`promise`) wrap their payload so a caller's `variant`
// sets the announcement priority and (for `danger`/`warning`) a longer auto-dismiss timer
// without having to pass `priority`/`timeout` themselves — either, explicitly set in the
// same call, still wins.
export function createToastManager<Data extends ToastData = ToastData>() {
  const manager = createBaseToastManager<Data>();
  return {
    ...manager,
    add: <T extends Data = Data>(options: ToastManagerAddOptions<T>) =>
      manager.add(withVariantDefaults(options)),
    /**
     * Patch-style: pass only the keys you mean to change (or return a partial from a functional
     * updater). Spreading top-level `...previous` restates stored `priority`/`timeout` as own keys
     * and blocks variant-derived urgency — do not do that when escalating. `data` is replaced, not
     * merged, so keep nested fields with `data: { ...previous.data, variant: "danger" }` (e.g.
     * `actions`, `progress`, `primaryAction`).
     */
    update: <T extends Data = Data>(id: string, updates: ToastUpdate<T>) =>
      manager.update<T>(id, (previous) =>
        withVariantDefaults(
          typeof updates === "function" ? updates(previous) : updates,
          previous.data,
        ),
      ),
    promise: <Value, T extends Data = Data>(
      promise: Promise<Value>,
      options: ToastManagerPromiseOptions<Value, T>,
    ) => manager.promise(promise, withPromiseDefaults(options)),
  };
}

/**
 * Toast manager hook with Propel variant defaults (`priority` / `timeout` from `data.variant`).
 * Prefer this (or {@link useToast}) over Base UI's raw hook so `danger`/`warning` stay assertive.
 */
export function useToastManager<Data extends ToastData = ToastData>() {
  const manager = useBaseToastManager<Data>();
  // Keep Base UI's stable method identities: inline wrappers would be new every render and
  // retrigger effects/memos that depend on `add`/`update`/`promise` (duplicate toasts).
  const add = useCallback(
    <T extends Data = Data>(options: ToastManagerAddOptions<T>) =>
      manager.add(withVariantDefaults(options)),
    [manager.add],
  );
  // Read provider-owned state synchronously, including same-tick updates from other managers.
  // No duplicate history survives a toast's removal or provider unmount.
  const update = useCallback(
    <T extends Data = Data>(id: string, updates: ToastUpdate<T>) =>
      manager.update<T>(id, (previous) =>
        withVariantDefaults(
          typeof updates === "function" ? updates(previous) : updates,
          previous.data,
        ),
      ),
    [manager.update],
  );
  const promise = useCallback(
    <Value, T extends Data = Data>(
      promiseValue: Promise<Value>,
      options: ToastManagerPromiseOptions<Value, T>,
    ) => manager.promise(promiseValue, withPromiseDefaults(options)),
    [manager.promise],
  );
  // Memoized for the same reason the methods are: Base UI's hook returns a `useMemo`'d
  // object (it changes only when `toasts` does), so returning a fresh literal here would
  // re-fire any `useEffect(…, [toast])` on every render — the identity hazard above, one
  // level up.
  return useMemo(
    () => ({
      ...manager,
      add,
      /**
       * Patch-style: pass only the keys you mean to change (or return a partial from a functional
       * updater). Spreading top-level `...previous` restates stored `priority`/`timeout` as own
       * keys and blocks variant-derived urgency — do not do that when escalating. `data` is
       * replaced, not merged, so keep nested fields with `data: { ...previous.data, variant:
       * "danger" }` (e.g. `actions`, `progress`, `primaryAction`).
       */
      update,
      promise,
    }),
    [manager, add, update, promise],
  );
}

/** Alias of {@link useToastManager} — the documented entry point for queuing toasts. */
export function useToast<Data extends ToastData = ToastData>() {
  return useToastManager<Data>();
}

export type ToastProps = Omit<BaseToast.Root.Props, "className" | "style"> & {
  /**
   * The close control (e.g. an `IconButton`), rendered as the toast's close button. It carries its
   * own — localizable — `aria-label`; the toast bakes no label or glyph.
   */
  close: React.ReactElement;
};

/**
 * A single styled toast: status icon (auto-selected from `toast.data.variant`), title, description,
 * optional action buttons (from `toast.data.actions` / `primaryAction`), and a close button.
 * Rendered automatically by `ToastProvider` for each queued toast — you normally don't render this
 * directly.
 */
export function Toast({ toast, close, ...props }: ToastProps) {
  // `variant` is a required field of `ToastData`, supplied when the toast is queued.
  // We intentionally have NO default variant — fail loud with guidance if it's missing.
  const data = toast.data as ToastData | undefined;
  if (data?.variant == null) {
    throw new Error(
      'propel Toast requires a `variant` in the toast\'s data payload, e.g. toast.add({ title, data: { variant: "info" } }).',
    );
  }
  // Action buttons, per Figma (node 1146-61689): a left cluster of up to two buttons
  // plus an optional right-aligned primary action. The button row only renders when
  // there's at least one of either, so an action-less toast keeps its tight layout.
  const leftActions = (data.actions ?? []).slice(0, 2);
  const primaryAction = data.primaryAction;
  const hasActionRow = leftActions.length > 0 || primaryAction != null;
  return (
    <BaseToast.Root toast={toast} {...props} render={<ToastElement />}>
      {/* `mt-0.5` on the icon (via toastStatusIconVariants) baselines it with the title. */}
      <ToastStatusIcon variant={data.variant} />
      <BaseToast.Content render={<ToastContent />}>
        <ToastTextGroup>
          <BaseToast.Title render={<ToastTitle />} />
          <BaseToast.Description render={<ToastDescription />} />
        </ToastTextGroup>
        {data.progress != null ? (
          <LinearProgress
            value={data.progress}
            size="sm"
            variant="brand"
            aria-label={typeof toast.title === "string" && toast.title ? toast.title : "Progress"}
          />
        ) : null}
        {hasActionRow ? (
          // The left cluster grows to fill so the primary action pins to the inline-end
          // edge; `ToastActionGroup` carries the offset that lines the buttons up with
          // the title text. RTL-safe via logical utilities (owned by the elements parts).
          <ToastActions>
            <ToastActionGroup>
              {/* Actions are positional and have no stable id; index keys are fine for this
                  short, static-per-render list. */}
              {leftActions.map((action, index) =>
                action.href != null ? (
                  <ToastActionButton
                    key={index}
                    onClick={action.onClick}
                    // The part's `type="button"` default is meaningless on an anchor.
                    type={undefined}
                    render={
                      <a href={action.href} target={action.target} rel={relFor(action.target)} />
                    }
                  >
                    {action.label}
                  </ToastActionButton>
                ) : (
                  <ToastActionButton key={index} onClick={action.onClick}>
                    {action.label}
                  </ToastActionButton>
                ),
              )}
            </ToastActionGroup>
            {primaryAction == null ? null : primaryAction.href != null ? (
              // Rendered directly rather than through `BaseToast.Action`: that part's `useButton`
              // stamps `type="button"` or `role="button"` onto whatever it renders, which would
              // announce the link as a button. It contributes no focus management to lose.
              <ToastAction
                render={
                  <a
                    href={primaryAction.href}
                    target={primaryAction.target}
                    rel={relFor(primaryAction.target)}
                  />
                }
                onClick={primaryAction.onClick}
              >
                {primaryAction.label}
              </ToastAction>
            ) : (
              <BaseToast.Action render={<ToastAction />} onClick={primaryAction.onClick}>
                {primaryAction.label}
              </BaseToast.Action>
            )}
          </ToastActions>
        ) : null}
      </BaseToast.Content>
      <ToastCloseGroup>
        <BaseToast.Close render={close} />
      </ToastCloseGroup>
    </BaseToast.Root>
  );
}
