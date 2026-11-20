import type { VariantProps } from "class-variance-authority";

type NonNullableVariants<Variants> = { [Key in keyof Variants]-?: NonNullable<Variants[Key]>; };
/**
 * Type-safe variant props for a `cva` helper.
 *
 * Every variant axis is **required** (and non-null) unless it has a configured default, in which
 * case it is **optional**. This keeps the props honest: you can only omit an axis that has a real
 * fallback in `defaultVariants`, so you can never leave a styling axis unset with no default — an
 * impossible visual state. Pass the union of defaulted keys (typically `keyof typeof
 * <name>DefaultVariants`); omit it when the cva has no defaults (all axes required).
 *
 * @example
 *   const buttonDefaultVariants = { variant: "primary", stretch: "auto" } as const;
 *   export const buttonVariants = cva(base, { variants, compoundVariants, defaultVariants: buttonDefaultVariants });
 *   export type ButtonVariantProps = StrictVariantProps<typeof buttonVariants, keyof typeof buttonDefaultVariants>;
 *   // -> { size: …; variant?: …; stretch?: … }
 */
export type StrictVariantProps<Component extends (...args: never[]) => unknown, Defaulted extends keyof VariantProps<Component> = never> = Omit<NonNullableVariants<VariantProps<Component>>, Defaulted> & Partial<Pick<NonNullableVariants<VariantProps<Component>>, Defaulted>>;
