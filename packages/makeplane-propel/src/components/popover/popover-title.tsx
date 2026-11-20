import { Popover as BasePopover } from "@base-ui/react/popover";

import { PopoverTitle as PopoverTitleElement } from "../../elements/popover/popover-title";

export type PopoverTitleProps = Omit<BasePopover.Title.Props, "className" | "style">;

/**
 * The accessible title for the popover: Base UI's `Popover.Title` behavior (links to the popup via
 * `aria-labelledby`) grafted onto the family-owned title chrome (`text-body-sm-medium`).
 */
export function PopoverTitle(props: PopoverTitleProps) {
  return <BasePopover.Title {...props} render={<PopoverTitleElement />} />;
}
