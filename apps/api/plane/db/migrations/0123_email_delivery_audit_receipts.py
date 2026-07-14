import secrets

from django.db import migrations, models


def backfill_email_receipts(apps, schema_editor):
    EmailOutbox = apps.get_model("db", "EmailOutbox")
    labels = {
        "auth.magic_signin": "Login code",
        "auth.forgot_password": "Password reset",
        "account.activation": "Account activation",
        "account.deactivation": "Account deactivation",
        "account.email_update_code": "Email change code",
        "account.email_updated": "Email changed",
        "invitation.workspace": "Workspace invitation",
        "invitation.workspace_known": "Workspace invitation",
        "invitation.project": "Project invitation",
        "invitation.project_known": "Project invitation",
        "project.member_added": "Project membership",
        "notification.issue_updates": "Work item updates",
        "export.analytics": "Analytics export",
        "operational.webhook_deactivated": "Webhook disabled",
        "security.openpgp_challenge": "OpenPGP verification",
        "security.openpgp_test": "Encrypted email test",
        "security.openpgp_changed": "Email security changed",
        "diagnostic.test": "Administrator email test",
    }
    for outbox in EmailOutbox.objects.all().iterator(chunk_size=500):
        raw = secrets.token_hex(10).upper()
        outbox.receipt_code = "-".join(raw[index : index + 4] for index in range(0, 20, 4))
        outbox.audit_label = labels.get(outbox.template_key, "Hangar email")
        outbox.delivery_mode = "openpgp" if outbox.openpgp_key_id else "clear"
        if outbox.status.startswith("suppressed_"):
            outbox.delivery_mode = "suppressed"
        outbox.save(update_fields=("receipt_code", "audit_label", "delivery_mode"))


class Migration(migrations.Migration):
    dependencies = [("db", "0122_secure_email_delivery")]

    operations = [
        migrations.AddConstraint(
            model_name="useropenpgpkey",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="pending", deleted_at__isnull=True),
                fields=("user",),
                name="uniq_pending_openpgp_key_per_user",
            ),
        ),
        migrations.AddField(
            model_name="emailoutbox",
            name="audit_label",
            field=models.CharField(default="", max_length=96),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="emailoutbox",
            name="sender",
            field=models.CharField(default="", max_length=320),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="emailoutbox",
            name="delivery_mode",
            field=models.CharField(
                choices=[
                    ("clear", "Cleartext account email"),
                    ("openpgp", "OpenPGP encrypted"),
                    ("suppressed", "Not sent"),
                ],
                default="clear",
                max_length=16,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="emailoutbox",
            name="receipt_code",
            field=models.CharField(blank=True, max_length=24, null=True),
        ),
        migrations.RunPython(backfill_email_receipts, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="emailoutbox",
            name="receipt_code",
            field=models.CharField(max_length=24, unique=True),
        ),
    ]
