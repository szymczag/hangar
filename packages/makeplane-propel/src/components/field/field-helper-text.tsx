import type * as React from "react";

import type { FieldSize } from "../../elements/field/variants";
import { FieldDescription } from "./field-description";
import { FieldError } from "./field-error";

/**
 * The error-or-hint line beneath a field: shows the `FieldError` when there is an error, otherwise
 * the `FieldDescription` hint. With no explicit `error`, the `FieldError` renders unmatched so Base
 * UI's own error channel stays open — validity messages and external `Form` `errors` for this field
 * display (and clear) automatically. A components-tier composition of the two elements parts;
 * shared by the ready-made field types so the error-XOR-hint rule lives in one place.
 */
export function FieldHelperText({
  size,
  hint,
  error,
}: {
  size: FieldSize;
  hint?: React.ReactNode;
  error?: React.ReactNode;
}) {
  return (
    <>
      {error != null ? (
        <FieldError size={size} match>
          {error}
        </FieldError>
      ) : (
        <FieldError size={size} />
      )}
      {error == null && hint != null ? (
        <FieldDescription size={size}>{hint}</FieldDescription>
      ) : null}
    </>
  );
}
