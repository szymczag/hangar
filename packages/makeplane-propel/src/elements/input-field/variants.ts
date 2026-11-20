import { cva } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

// The input field's orientation-aware root: label above (`vertical`) or beside (`horizontal`).
// Stacked, the label column sits 6px above the control at md/lg and 8px at xl/2xl (the Input set,
// 1582:7579); side by side it is a flat 8px.
export const inputFieldVariants = cva("flex", {
  variants: {
    orientation: {
      vertical: "flex-col items-start",
      horizontal: "flex-row items-start gap-2",
    },
    size: {
      md: "",
      lg: "",
      xl: "",
      "2xl": "",
    },
  },
  compoundVariants: [
    { orientation: "vertical", size: ["md", "lg"], class: "gap-1.5" },
    { orientation: "vertical", size: ["xl", "2xl"], class: "gap-2" },
  ],
});

export type InputFieldVariantProps = StrictVariantProps<typeof inputFieldVariants>;
