# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.


import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ext', '0013_openpgp_policy'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FederatedLinkAudit',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Last Modified At')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted At')),
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('email', models.CharField(db_index=True, max_length=255)),
                ('provider', models.CharField(max_length=32)),
                ('issuer', models.CharField(max_length=2048)),
                ('subject', models.CharField(max_length=2048)),
                ('authorized_at', models.DateTimeField(null=True)),
                ('note', models.TextField(blank=True)),
                ('authorized_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='federated_link_audits_authorized', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='federated_link_audits', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'ext_federated_link_audits',
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='FederatedLinkAuthorization',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Last Modified At')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted At')),
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('email', models.CharField(db_index=True, max_length=255)),
                ('provider', models.CharField(max_length=32)),
                ('issuer', models.CharField(max_length=2048)),
                ('note', models.TextField(blank=True)),
                ('expires_at', models.DateTimeField()),
                ('consumed_at', models.DateTimeField(blank=True, null=True)),
                ('consumed_subject', models.CharField(blank=True, max_length=2048)),
                ('authorized_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='federated_link_authorizations', to=settings.AUTH_USER_MODEL)),
                ('consumed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='federated_links_consumed', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By')),
            ],
            options={
                'db_table': 'ext_federated_link_authorizations',
                'ordering': ('-created_at',),
                'indexes': [models.Index(fields=['email', 'provider'], name='fed_link_email_provider_idx')],
            },
        ),
    ]
