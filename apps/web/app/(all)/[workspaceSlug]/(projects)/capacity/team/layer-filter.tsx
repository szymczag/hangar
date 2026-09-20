/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Button } from "@plane/propel/button";
import type { TCapacityInterval } from "@/services/capacity.service";
import {
  ALL_CAPACITY_LAYERS,
  CAPACITY_INTERVAL_LAYERS,
  CAPACITY_LAYER_LABELS,
  ONLY_TRAINING_LAYERS,
  isOnlyTraining,
} from "../shared/capacity-timeline.utils";

type Kind = TCapacityInterval["kind"];

type Props = {
  layers: Set<Kind>;
  onChange: (next: Set<Kind>) => void;
};

/**
 * Which kinds of commitment the ledger draws.
 *
 * "Only training" is the shortcut the question actually was -- trainers keep all
 * sorts of things in their calendars, and the one being asked about is the
 * training. The individual toggles are there because the answer to "why is this
 * person unavailable" is usually a different layer.
 *
 * Working hours are not offered as a toggle: they are the canvas everything else
 * is drawn on, so hiding them leaves bars floating over nothing.
 */
export function LayerFilter({ layers, onChange }: Props) {
  const onlyTraining = isOnlyTraining(layers);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant={onlyTraining ? "primary" : "secondary"}
        size="sm"
        aria-pressed={onlyTraining}
        onClick={() => onChange(onlyTraining ? new Set(ALL_CAPACITY_LAYERS) : new Set(ONLY_TRAINING_LAYERS))}
      >
        Only training
      </Button>
      <span aria-hidden="true" className="bg-subtle h-4 w-px" />
      {CAPACITY_INTERVAL_LAYERS.filter((kind) => kind !== "working").map((kind) => (
        <label key={kind} className="flex items-center gap-1.5 text-body-xs-regular text-secondary">
          <input
            type="checkbox"
            checked={layers.has(kind)}
            onChange={() => {
              const next = new Set(layers);
              if (next.has(kind)) next.delete(kind);
              else next.add(kind);
              next.add("working");
              onChange(next);
            }}
          />
          {CAPACITY_LAYER_LABELS[kind]}
        </label>
      ))}
    </div>
  );
}
