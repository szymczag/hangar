// Set uses SameValueZero; a private key keeps -0 distinct from +0 as Object.is requires.
const negativeZero = Symbol("negative-zero");

/** Index values once for repeated membership checks with Base UI's default Object.is equality. */
export function createSelectionMatcher<Value>(
  selected: readonly Value[],
): (item: Value) => boolean {
  const membership = new Set<Value | symbol>();
  selected.forEach((value) => {
    membership.add(Object.is(value, -0) ? negativeZero : value);
  });
  return (item) => membership.has(Object.is(item, -0) ? negativeZero : item);
}
