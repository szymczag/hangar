# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from .federated_auth import ExternalIdentity, FederatedAuthenticationResult, authenticate_external_identity

__all__ = ["ExternalIdentity", "FederatedAuthenticationResult", "authenticate_external_identity"]
