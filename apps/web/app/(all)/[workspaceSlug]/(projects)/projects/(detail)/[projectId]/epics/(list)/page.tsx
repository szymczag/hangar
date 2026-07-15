/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Navigate } from "react-router";
import type { Route } from "./+types/page";

export default function ProjectEpicsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  return <Navigate to={`/${workspaceSlug}/projects/${projectId}/issues`} replace />;
}
