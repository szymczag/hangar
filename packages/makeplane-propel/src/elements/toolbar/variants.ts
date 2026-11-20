import { cva, cx, type VariantProps } from "class-variance-authority";

import { fieldControlSurfaceVariants } from "../../internal/field-control-surface";
import { surfaceVariants } from "../../internal/surface";
import { type StrictVariantProps } from "../../internal/variant-props";

export const toolbarVariants = cva("flex w-fit items-center gap-2 p-1.5 text-secondary", {
  variants: {
    elevation: {
      // No overflow-clip (Figma raised has it) — would clip focus-visible rings on edge items.
      raised: surfaceVariants({ elevation: "raised", radius: "lg" }),
      flat: "",
    },
    // Empty on purpose: hosts the `size` API / `ToolbarSize` type. Root chrome does not
    // change with size — items read size from `components/toolbar` context instead.
    size: {
      sm: "",
      md: "",
    },
  },
});

export const toolbarGroupVariants = cva("flex items-center gap-2");

export const toolbarSeparatorVariants = cva("h-3.5 w-0 shrink-0 border-s-sm border-subtle");

export const toolbarToggleGroupVariants = cva("flex items-center gap-2");

const toolbarItemDefaultVariants = { labeled: false } as const;

// The square hit target for an icon control (button or toggle). Holds only the box,
// chrome, and the `--node-size` the child `Icon` scales to — the glyph itself is never
// sized by a descendant selector here.
export const toolbarItemVariants = cva(
  cx(
    "inline-flex shrink-0 cursor-pointer items-center justify-center rounded-md",
    "bg-layer-transparent text-icon-secondary outline-none",
    "not-disabled:not-data-disabled:hover:bg-layer-transparent-hover not-disabled:not-data-disabled:active:bg-layer-transparent-active",
    "focus-visible:ring-2 focus-visible:ring-accent-strong",
    // On-state chrome (wash + brand tint) — matches Radio/Menu selected, not Figma's
    // outline→filled glyph swap (that's a consumer `icon` concern).
    "data-pressed:bg-layer-transparent-selected data-pressed:text-icon-accent-primary",
    // BOTH disabled selectors, because the two tiers spell it differently: an `elements`
    // consumer renders a raw `<button disabled>`, while `components` routes `disabled`
    // through Base UI's `Toolbar.Button` — which is focusable-when-disabled, so it emits
    // `data-disabled` + `aria-disabled` and strips the native attribute. Without the
    // native one, `:hover`/`:active` still fire, so the washes above are gated too (no
    // `pointer-events-none`: it would kill the `cursor-not-allowed` it is paired with).
    "disabled:cursor-not-allowed disabled:text-icon-disabled",
    "data-disabled:cursor-not-allowed data-disabled:text-icon-disabled",
    // Pressed+disabled: compound selectors beat `data-pressed:text-icon-accent-primary`
    // / wash (same pattern as Radio's `data-disabled:data-checked:`). Without them the
    // accent glyph and selected wash outrank plain disabled color in the cascade.
    "disabled:data-pressed:bg-layer-transparent disabled:data-pressed:text-icon-disabled",
    "data-disabled:data-pressed:bg-layer-transparent data-disabled:data-pressed:text-icon-disabled",
  ),
  {
    variants: {
      size: {
        sm: "h-(--control-height-sm) [--node-size:var(--control-glyph-sm)]", // 24px box, 14px glyph
        md: "h-(--control-height-md) [--node-size:var(--control-glyph-md)]", // 28px box, 16px glyph
      },
      // `labeled` widens the square icon box to hug an icon + text label (e.g. "Comment").
      labeled: {
        true: "",
        false: "",
      },
    },
    compoundVariants: [
      { labeled: false, size: "sm", className: "w-(--control-height-sm)" },
      { labeled: false, size: "md", className: "w-(--control-height-md)" },
      {
        labeled: true,
        size: "sm",
        className: "gap-(--control-gap-sm) px-(--control-padding-x-sm)",
      },
      {
        labeled: true,
        size: "md",
        className: "gap-(--control-gap-md) px-(--control-padding-x-md)",
      },
    ],
    defaultVariants: toolbarItemDefaultVariants,
  },
);

// The styled chrome for a toolbar menu trigger: a horizontal control that pairs a
// text label with a disclosure indicator. The label's typography lives on the label
// part, not here.
export const toolbarMenuTriggerButtonVariants = cva(
  cx(
    // `group` so the shared DisclosureIndicator can read `data-popup-open` for flip motion.
    // `justify-between` pins the caret to the trailing edge of the Figma min-width so extra
    // width sits between label and caret (same pattern as SelectTrigger), not after the caret.
    "group inline-flex shrink-0 cursor-pointer items-center justify-between",
    "bg-layer-transparent text-secondary outline-none",
    "not-disabled:not-data-disabled:hover:bg-layer-transparent-hover not-disabled:not-data-disabled:active:bg-layer-transparent-active",
    "focus-visible:ring-2 focus-visible:ring-accent-strong",
    "data-popup-open:bg-layer-transparent-selected",
    // Both spellings — see `toolbarItemVariants` above.
    "disabled:cursor-not-allowed disabled:text-disabled",
    "data-disabled:cursor-not-allowed data-disabled:text-disabled",
  ),
  {
    variants: {
      size: {
        // Ladder sm/md: h + px + gap + radius. Min-width is a Figma-fixed 40/48px (no
        // `--control-min-w-*` rung exists). The caret is the text-adjacent glyph at both steps;
        // `md`'s 16px is now the ladder's own value, so the old raw-length carve-out is gone.
        sm: "h-(--control-height-sm) min-w-10 gap-(--control-gap-sm) rounded-(--control-radius-sm) px-(--control-padding-x-sm) [--node-size:var(--control-glyph-sm)]",
        md: "h-(--control-height-md) min-w-12 gap-(--control-gap-md) rounded-(--control-radius-md) px-(--control-padding-x-md) [--node-size:var(--control-glyph-md)]",
      },
    },
  },
);

// The text label region of a toolbar item (a labeled button, link, or menu trigger).
// Its own part so the control holds no raw typography.
export const toolbarItemLabelVariants = cva("text-body-xs-medium");

/** Whether the toolbar draws its own surface (`raised`) or sits flush (`flat`). */
export type ToolbarElevation = NonNullable<VariantProps<typeof toolbarVariants>["elevation"]>;

/**
 * Control hit-target scale: `sm` (24px) or `md` (28px). Orthogonal to `elevation`. Figma's
 * `density` maps here — `compact` → `sm`, `comfortable` → `md` (raised floaters use `sm`).
 */
export type ToolbarSize = NonNullable<VariantProps<typeof toolbarVariants>["size"]>;

export type ToolbarVariantProps = StrictVariantProps<typeof toolbarVariants>;

export type ToolbarItemVariantProps = StrictVariantProps<
  typeof toolbarItemVariants,
  keyof typeof toolbarItemDefaultVariants
>;

export type ToolbarMenuTriggerButtonVariantProps = StrictVariantProps<
  typeof toolbarMenuTriggerButtonVariants
>;

// An inline text input sitting among toolbar items (e.g. a filter box): a miniature field —
// the shared control surface at `self` focus — whose height tracks the toolbar's size like
// every other item. Invented pending a Figma spec; flagged for design polish.
export const toolbarInputVariants = cva(
  cx(
    fieldControlSurfaceVariants({ focus: "self" }),
    "text-body-xs-regular text-primary outline-none placeholder:text-placeholder",
    // Both spellings — `Toolbar.Input` is focusable-when-disabled too, so `components`
    // gets `data-disabled` while an `elements` consumer renders a native `<input disabled>`.
    // Opacity mutes the shared field surface (fill + border), not only the text color.
    "disabled:cursor-not-allowed disabled:text-disabled disabled:opacity-60",
    "data-disabled:cursor-not-allowed data-disabled:text-disabled data-disabled:opacity-60",
  ),
  {
    variants: {
      size: {
        sm: "h-(--control-height-sm) rounded-(--control-radius-sm) px-(--control-padding-x-sm)",
        md: "h-(--control-height-md) rounded-(--control-radius-md) px-(--control-padding-x-md)",
      },
    },
  },
);
export type ToolbarInputVariantProps = StrictVariantProps<typeof toolbarInputVariants>;
