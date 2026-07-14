# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Serializers for self-service OpenPGP email security."""

from rest_framework import serializers

from plane.db.models import UserOpenPGPKey


class OpenPGPKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserOpenPGPKey
        fields = (
            "id",
            "version",
            "primary_fingerprint",
            "encryption_subkey_fingerprint",
            "primary_algorithm",
            "encryption_algorithm",
            "encryption_key_size",
            "key_created_at",
            "key_expires_at",
            "last_validated_at",
            "verified_at",
            "status",
            "created_at",
        )
        read_only_fields = fields


class OpenPGPKeyUploadSerializer(serializers.Serializer):
    certificate = serializers.CharField(max_length=64 * 1024, trim_whitespace=False)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True, trim_whitespace=False)


class OpenPGPChallengeVerifySerializer(serializers.Serializer):
    code = serializers.CharField(min_length=8, max_length=64, trim_whitespace=True)


class OpenPGPKeyRemovalSerializer(serializers.Serializer):
    password = serializers.CharField(required=False, allow_blank=True, write_only=True, trim_whitespace=False)
