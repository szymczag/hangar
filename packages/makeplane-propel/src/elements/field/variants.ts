import { cva, cx, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

export type { InputSize } from "../input/variants";

const fieldDefaultVariants = { size: "lg" } as const;

// Label column to control: 6px at md/lg, 8px at xl/2xl, per the Input, Select and Combobox sets.
export const fieldVariants = cva("flex flex-col", {
  variants: {
    size: {
      md: "gap-1.5",
      lg: "gap-1.5",
      xl: "gap-2",
      "2xl": "gap-2",
    },
  },
  defaultVariants: fieldDefaultVariants,
});

export type FieldVariantProps = StrictVariantProps<
  typeof fieldVariants,
  keyof typeof fieldDefaultVariants
>;

// The required marker sits flush against the label text (Figma `spacing/0`).
export const fieldLabelVariants = cva(cx("inline-flex items-center gap-0", "text-primary"), {
  variants: {
    size: {
      md: "text-body-xs-medium",
      lg: "text-body-xs-medium",
      xl: "text-body-sm-medium",
      "2xl": "text-body-sm-medium",
    },
    inset: {
      true: "",
      false: "",
    },
  },
  compoundVariants: [
    { size: "md", inset: true, class: "pt-1" },
    { size: "lg", inset: true, class: "pt-[7px]" },
    { size: "xl", inset: true, class: "pt-[9px]" },
    { size: "2xl", inset: true, class: "pt-[13px]" },
  ],
});

type FieldLabelVariantConfig = VariantProps<typeof fieldLabelVariants>;

export type FieldSize = NonNullable<FieldLabelVariantConfig["size"]>;

export type FieldLabelVariantProps = StrictVariantProps<typeof fieldLabelVariants>;

// The required `*` marker rendered after the label text. Decorative (the control's
// `required` carries the semantics), tinted danger per the Figma spec. `body-sm` (14/22) at every
// label size — the Input and Text area sets draw the same asterisk at every step.
export const fieldLabelRequiredMarkerVariants = cva("text-body-sm-regular text-danger-primary");

// The label + description column for a single choice option (checkbox/radio/switch row). The
// explicit 20px line box (`leading-5`) pairs with the 20px control slot
// (`fieldItemControlGroupVariants`) so the control centers on the label's first line.
export const fieldItemContentVariants = cva("flex min-w-0 flex-col gap-1 leading-5");

// The control slot of a choice option row: a 20px-tall box matching the label's first line box
// (`fieldItemContentVariants`' `leading-5`), centering any control height (radio/checkbox 16px,
// switch 14–18px) against that line — even when the label wraps or a description follows.
export const fieldItemControlGroupVariants = cva("flex h-5 shrink-0 items-center");

// Supporting text, under the label or under the control, is one tier below the label at every
// size: body-2xs under a 13px label, body-xs under a 14px one.
export const fieldDescriptionVariants = cva("text-tertiary", {
  variants: {
    size: {
      md: "text-body-2xs-regular",
      lg: "text-body-2xs-regular",
      xl: "text-body-xs-regular",
      "2xl": "text-body-xs-regular",
    },
  },
});

export type FieldDescriptionVariantProps = StrictVariantProps<typeof fieldDescriptionVariants>;

export const fieldErrorVariants = cva("text-danger-primary", {
  variants: {
    size: {
      md: "text-body-2xs-regular",
      lg: "text-body-2xs-regular",
      xl: "text-body-xs-regular",
      "2xl": "text-body-xs-regular",
    },
  },
});

export type FieldErrorVariantProps = StrictVariantProps<typeof fieldErrorVariants>;

// The control + helper-text column shared by the input and textarea fields (orientation-aware).
export const fieldControlContentVariants = cva("flex flex-col", {
  variants: {
    orientation: {
      vertical: "w-full",
      horizontal: "min-w-0 flex-1 gap-2",
    },
    size: {
      md: "",
      lg: "",
      xl: "",
      "2xl": "",
    },
  },
  compoundVariants: [
    // Vertical control-to-helper-text gap steps with size (6px at md/lg, 8px at xl/2xl);
    // horizontal stays a flat 8px regardless of size, per the Figma spec.
    { orientation: "vertical", size: "md", class: "gap-1.5" },
    { orientation: "vertical", size: "lg", class: "gap-1.5" },
    { orientation: "vertical", size: "xl", class: "gap-2" },
    { orientation: "vertical", size: "2xl", class: "gap-2" },
  ],
});

export type FieldControlContentVariantProps = StrictVariantProps<
  typeof fieldControlContentVariants
>;

export const fieldItemVariants = cva(
  cx(
    "flex min-w-0 items-start gap-2 rounded-sm px-2 py-1 text-primary transition-colors",
    "data-disabled:cursor-not-allowed data-disabled:opacity-60",
    "not-data-disabled:hover:bg-layer-transparent-hover",
  ),
);

// Label-to-description gap is 2px (`spacing/0_5`) in both orientations at every size, per Figma.
export const fieldLabelGroupVariants = cva("flex flex-col gap-0.5", {
  variants: {
    orientation: {
      vertical: "w-full",
      horizontal: "min-w-0 flex-1",
    },
  },
});

export type FieldLabelGroupVariantProps = StrictVariantProps<typeof fieldLabelGroupVariants>;
