import os

from django.db import migrations


def migrate_sso_configuration(apps, schema_editor):
    InstanceConfiguration = apps.get_model("license", "InstanceConfiguration")
    for key, value, category in (
        ("GOOGLE_AUTH_MODE", os.environ.get("GOOGLE_AUTH_MODE", "generic"), "GOOGLE"),
        ("GOOGLE_WORKSPACE_DOMAINS", os.environ.get("GOOGLE_WORKSPACE_DOMAINS", ""), "GOOGLE"),
        ("SAML_ATTR_SUBJECT", os.environ.get("SAML_ATTR_SUBJECT", ""), "SAML"),
    ):
        InstanceConfiguration.objects.get_or_create(
            key=key,
            defaults={"value": value, "category": category, "is_encrypted": False},
        )
    InstanceConfiguration.objects.filter(key="OIDC_ALLOW_UNVERIFIED_EMAIL").delete()


class Migration(migrations.Migration):
    dependencies = [("license", "0007_disable_telemetry_by_default")]
    operations = [migrations.RunPython(migrate_sso_configuration, migrations.RunPython.noop)]
