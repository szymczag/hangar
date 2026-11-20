import * as React from "react";

import type { FieldSize } from "../elements/field/variants";

// Cascades the field size from a group field (`CheckboxGroupField` / `RadioGroupField`) down to
// its option rows, so an option can omit `size` and inherit the group's. React context is a
// composition concern — never `elements` (rule 7) — and this one is shared by both group fields, so it
// lives here in `internal` (alongside the other shared composition impl).
const FieldOptionSizeContext = React.createContext<FieldSize | null>(null);

export function FieldOptionSizeProvider({
  children,
  size,
}: {
  children: React.ReactNode;
  size: FieldSize;
}) {
  return <FieldOptionSizeContext.Provider value={size}>{children}</FieldOptionSizeContext.Provider>;
}

export function useFieldOptionSize(size?: FieldSize) {
  // Read the context unconditionally — `size ?? React.useContext(…)` would skip the hook call
  // whenever `size` is passed, violating the Rules of Hooks.
  const inheritedSize = React.useContext(FieldOptionSizeContext);
  const resolvedSize = size ?? inheritedSize;

  if (resolvedSize == null) {
    throw new Error("Field option components require a size or a parent field composition.");
  }

  return resolvedSize;
}
