import datetime
import hashlib
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def _binding_key(provider, issuer, subject_format, subject):
    values = (provider, issuer, subject_format, subject)
    framed = b"".join(len(value.encode("utf-8")).to_bytes(4, "big") + value.encode("utf-8") for value in values)
    return hashlib.sha256(framed).hexdigest()


def backfill_google_identities_and_invite_expiry(apps, schema_editor):
    Account = apps.get_model("db", "Account")
    FederatedIdentity = apps.get_model("db", "FederatedIdentity")
    WorkspaceMemberInvite = apps.get_model("db", "WorkspaceMemberInvite")

    for account in Account.objects.filter(provider="google").iterator():
        issuer = "https://accounts.google.com"
        subject = account.provider_account_id
        binding_key = _binding_key("google", issuer, "", subject)
        identity, created = FederatedIdentity.objects.get_or_create(
            binding_key=binding_key,
            defaults={
                "id": uuid.uuid4(),
                "user_id": account.user_id,
                "provider": "google",
                "issuer": issuer,
                "subject_format": "",
                "subject": subject,
                "email_at_link": "",
                "last_email": "",
                "metadata": {"source": "account-backfill"},
            },
        )
        if identity.user_id != account.user_id:
            raise RuntimeError("Conflicting Google provider account binding")
        if created or account.identity_id is None:
            account.identity_id = identity.id
            account.save(update_fields=["identity"])

    WorkspaceMemberInvite.objects.filter(responded_at__isnull=True, expires_at__isnull=True).update(
        expires_at=models.F("created_at") + datetime.timedelta(days=7)
    )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("db", "0123_email_delivery_audit_receipts"),
    ]

    operations = [
        migrations.CreateModel(
            name="FederatedIdentity",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "provider",
                    models.CharField(
                        choices=[("google", "Google"), ("oidc", "OpenID Connect"), ("saml", "SAML")],
                        max_length=32,
                    ),
                ),
                ("issuer", models.CharField(max_length=2048)),
                ("subject_format", models.CharField(blank=True, max_length=512)),
                ("subject", models.CharField(max_length=2048)),
                ("binding_key", models.CharField(editable=False, max_length=64, unique=True)),
                ("email_at_link", models.CharField(blank=True, max_length=255)),
                ("last_email", models.CharField(blank=True, max_length=255)),
                ("last_authenticated_at", models.DateTimeField(null=True)),
                ("metadata", models.JSONField(default=dict)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="federated_identities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "federated_identities", "ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="FederatedIdentityImportAudit",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        choices=[("google", "Google"), ("oidc", "OpenID Connect"), ("saml", "SAML")],
                        max_length=32,
                    ),
                ),
                ("issuer", models.CharField(max_length=2048)),
                ("input_sha256", models.CharField(max_length=64)),
                ("source_name", models.CharField(max_length=512)),
                ("row_count", models.PositiveIntegerField()),
                ("imported_count", models.PositiveIntegerField()),
                ("existing_count", models.PositiveIntegerField()),
                ("report", models.JSONField(default=dict)),
            ],
            options={"db_table": "federated_identity_import_audits", "ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="federatedidentity",
            index=models.Index(fields=["user", "provider"], name="fed_identity_user_provider_idx"),
        ),
        migrations.AddField(
            model_name="account",
            name="identity",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="oauth_account",
                to="db.federatedidentity",
            ),
        ),
        migrations.AddField(
            model_name="workspacememberinvite",
            name="consumed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workspacememberinvite",
            name="expires_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="workspacememberinvite",
            name="revoked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workspacememberinvite",
            name="signup_authorized_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_google_identities_and_invite_expiry, migrations.RunPython.noop),
    ]
