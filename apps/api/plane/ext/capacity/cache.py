# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.cache import cache


BUSY_CACHE_TTL_SECONDS = 300
BUSY_INDEX_TTL_SECONDS = 3600
MAX_INDEXED_BUSY_KEYS = 256


def register_busy_cache_key(selection_id, cache_key):
    index_key = f"gcal:busy-index:{selection_id}"
    keys = cache.get(index_key)
    if not isinstance(keys, list):
        keys = []
    if cache_key not in keys:
        keys = [*keys[-(MAX_INDEXED_BUSY_KEYS - 1) :], cache_key]
    cache.set(index_key, keys, BUSY_INDEX_TTL_SECONDS)


def clear_selection_cache(selection_id):
    index_key = f"gcal:busy-index:{selection_id}"
    keys = cache.get(index_key)
    if isinstance(keys, list):
        cache.delete_many(keys)
    cache.delete(index_key)


def clear_credential_cache(credential_id):
    cache.delete(f"gcal:access:{credential_id}")
