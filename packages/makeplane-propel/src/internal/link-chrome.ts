import { cva, cx, type VariantProps } from "class-variance-authority";

// The inline text-link look (Figma "Link") worn by the semantic `<a>` in `AnchorButton`. The link
// palette is by `variant` (blue primary / muted secondary), text size by `size`. Underline lives on
// the label part (Figma: underline spans the text only, not the flanking icons). `aria-disabled`
// styles the ready-made's disabled state. Compose nothing — it is the whole look; each surface just
// renders its element with this className.
export const linkChromeVariants = cva(
  cx(
    "group inline-flex cursor-pointer items-center gap-1 rounded-xs transition-colors outline-none",
    // The label stays on one line, like every other action in the library
    // (`buttonGeometryVariants`). A wrapped link splits its underline across lines and, with a
    // leading or trailing icon, leaves that icon stranded beside the last line — the flex row
    // centers it against the whole wrapped block, not the text it belongs to.
    "whitespace-nowrap",
    "focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-offset-1",
    // Figma disabled keeps the underline — only the color mutes to `text-disabled`.
    "aria-disabled:cursor-not-allowed aria-disabled:text-disabled",
  ),
  {
    variants: {
      variant: {
        primary: "text-link-primary hover:text-link-primary-hover",
        // The muted link rests at `tertiary` and darkens two steps to `primary` on hover — a wider
        // default→hover gap than `secondary`→`primary` gave, so the hover reads clearly.
        secondary: "text-tertiary hover:text-primary",
      },
      // `AnchorButton` follows the Button size ladder (rule 6d), so a step here means what the same
      // step means on `buttonGeometryVariants` — type 12·13·13·14, and now the glyph too. It used
      // to run a private 12/14/16/20 column, the only sized family off the ladder in both
      // directions: 12px at `xs` was the library's sole sub-14 glyph, and `lg` ran two steps over.
      // Inline text carries no height, so the steps only differ visibly in type — but the pairing
      // that matters is a link sitting beside a button of the same size, which is exactly what
      // disagreed.
      size: {
        xs: "text-caption-md-regular [--node-size:var(--control-glyph-xs)]",
        sm: "text-body-xs-regular [--node-size:var(--control-glyph-sm)]",
        md: "text-body-xs-regular [--node-size:var(--control-glyph-md)]",
        lg: "text-body-sm-regular [--node-size:var(--control-glyph-lg)]",
      },
    },
  },
);

export type LinkChromeVariantProps = VariantProps<typeof linkChromeVariants>;
