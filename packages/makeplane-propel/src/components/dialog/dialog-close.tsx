import { Dialog as BaseDialog } from "@base-ui/react/dialog";

export type DialogCloseProps = Omit<BaseDialog.Close.Props, "className" | "style">;

/**
 * The behavior that closes the dialog when activated. Use as the `render` target of a `Button` or
 * `IconButton` so the styled primitive's look wins via render-composition. Corner dismiss belongs
 * in `DialogCloseGroup`:
 *
 * ```tsx
 * <DialogCloseGroup>
 *   <IconButton
 *     variant="ghost"
 *     size="xs"
 *     aria-label={closeLabel}
 *     icon={<Icon icon={X} />}
 *     render={<DialogClose />}
 *   />
 * </DialogCloseGroup>;
 * ```
 *
 * Maps 1:1 to `Dialog.Close`.
 */
export function DialogClose(props: DialogCloseProps) {
  return <BaseDialog.Close {...props} />;
}
