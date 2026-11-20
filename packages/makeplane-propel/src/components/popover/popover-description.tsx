import { Popover as BasePopover } from "@base-ui/react/popover";

import { OverlayDescription } from "../../internal/overlay-description";

export type PopoverDescriptionProps = Omit<BasePopover.Description.Props, "className" | "style">;

/**
 * Supporting text for the popover: Base UI's `Popover.Description` behavior (wired as the popup's
 * `aria-describedby` target) grafted onto the shared `internal/OverlayDescription` at `md` (body-xs
 * secondary).
 */
export function PopoverDescription(props: PopoverDescriptionProps) {
  return <BasePopover.Description {...props} render={<OverlayDescription size="md" />} />;
}
