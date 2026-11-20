import { Tooltip as BaseTooltip } from "@base-ui/react/tooltip";
import type * as React from "react";

type BaseTooltipProviderProps = BaseTooltip.Provider.Props;

export type TooltipProviderProps = Omit<
  BaseTooltipProviderProps,
  "delay" | "closeDelay" | "timeout" | "children"
> & {
  /**
   * How long to wait before opening a tooltip, in milliseconds. Applied only when a child trigger
   * does not set its own `delay` — Base UI resolves `delay ?? providerDelay ?? 600` (per-tooltip
   * wins). The ready-made `Tooltip` always passes its own `300`, so this reaches only a
   * hand-composed `BaseTooltip.Trigger`; set the timing on the `Tooltip` itself instead.
   */
  delay?: number;
  /**
   * How long to wait before closing a tooltip, in milliseconds. Shared across the group so moving
   * between nearby triggers can swap hints without a hard cut. Per-tooltip close delay is not on
   * the ready-made `Tooltip` — set it here. No provider default — omit for Base UI's per-trigger
   * close delay (`0`).
   */
  closeDelay?: number;
  /**
   * After a tooltip in this group closes, another may open instantly if its trigger is interacted
   * with within this window (ms).
   *
   * @default 400
   */
  timeout?: number;
  /** The subtree whose tooltips share this group's open/close timing. */
  children?: React.ReactNode;
};

/**
 * Shares one open/close delay across every tooltip beneath it, so moving between nearby triggers
 * can show adjacent tooltips immediately.
 */
export function TooltipProvider(props: TooltipProviderProps) {
  return <BaseTooltip.Provider {...props} />;
}
