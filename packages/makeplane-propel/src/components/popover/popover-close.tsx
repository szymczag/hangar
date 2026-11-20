import { Popover as BasePopover } from "@base-ui/react/popover";

export type PopoverCloseProps = Omit<BasePopover.Close.Props, "className" | "style">;

/**
 * The behavior that closes the popover when activated. Use as the `render` target of a `Button` or
 * `IconButton` so the styled primitive's look wins via render-composition:
 *
 * ```tsx
 * <Button
 *   variant="secondary"
 *   size="sm"
 *   stretch="auto"
 *   label="Cancel"
 *   render={<PopoverClose />}
 * />;
 * ```
 *
 * Maps 1:1 to `Popover.Close`.
 */
export function PopoverClose(props: PopoverCloseProps) {
  return <BasePopover.Close {...props} />;
}
