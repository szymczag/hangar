import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { dialogDescriptionVariants } from "./variants";

export type DialogDescriptionProps = Omit<useRender.ComponentProps<"p">, "className" | "style">;

/**
 * Styled dialog description chrome (`text-body-xs-regular` tertiary). Base-UI-agnostic — graft
 * description behavior in `components` via `<BaseDialog.Description render={<DialogDescription />}
 * />`. Dialog-owned (diverges from shared `OverlayDescription`).
 */
export function DialogDescription({ render, ...props }: DialogDescriptionProps) {
  const defaultProps: useRender.ElementProps<"p"> = { className: dialogDescriptionVariants() };
  return useRender({ defaultTagName: "p", render, props: mergeProps(defaultProps, props) });
}
