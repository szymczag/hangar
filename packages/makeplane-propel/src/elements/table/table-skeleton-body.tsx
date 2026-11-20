import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { tableSkeletonBodyVariants } from "./variants";

export type TableSkeletonBodyProps = Omit<useRender.ComponentProps<"tbody">, "className" | "style">;

/**
 * The body section (`<tbody>`) of a loading table: pulsing and non-interactive, so the placeholder
 * rows inside it neither animate out of step nor take the row hover tint.
 *
 * It deliberately does not hold the rows — repeating a row is composition, which belongs to the
 * ready-made in `components/table`.
 */
export function TableSkeletonBody({ render, ...props }: TableSkeletonBodyProps) {
  const defaultProps: useRender.ElementProps<"tbody"> = {
    className: tableSkeletonBodyVariants(),
  };
  return useRender({ defaultTagName: "tbody", render, props: mergeProps(defaultProps, props) });
}
