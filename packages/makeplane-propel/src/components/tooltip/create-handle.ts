import { Tooltip as BaseTooltip } from "@base-ui/react/tooltip";

/**
 * Base UI's detached-handle API, flattened to the family name: create a handle outside the React
 * tree, pass it to the ready-made's `handle` prop (or a composed `Tooltip.Root`), and open
 * imperatively with `handle.open(triggerId)` — the trigger element must carry that same `id`.
 * Multiple detached triggers need Base UI `Tooltip.Trigger` parts wired to the handle; the
 * ready-made only mounts one trigger from `children`.
 */
export const createTooltipHandle = BaseTooltip.createHandle;

export type TooltipHandle = ReturnType<typeof createTooltipHandle>;
