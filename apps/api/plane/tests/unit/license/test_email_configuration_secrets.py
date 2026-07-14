import pytest
from django.test import override_settings

from plane.license.api.serializers import InstanceConfigurationSerializer
from plane.license.models import InstanceConfiguration


@pytest.mark.unit
def test_encrypted_instance_configuration_is_write_only():
    configuration = InstanceConfiguration(
        key="EMAIL_HOST_PASSWORD",
        value="encrypted-secret-value",
        is_encrypted=True,
    )

    serialized = InstanceConfigurationSerializer(configuration).data

    assert serialized["value"] == ""
    assert serialized["is_configured"] is True
    assert "encrypted-secret-value" not in str(serialized)


@pytest.mark.unit
@override_settings(EMAIL_PROVIDER="ses_api")
def test_deployment_managed_provider_uses_runtime_setting():
    configuration = InstanceConfiguration(
        key="EMAIL_PROVIDER",
        value="stale-database-value",
        is_encrypted=False,
    )

    serialized = InstanceConfigurationSerializer(configuration).data

    assert serialized["value"] == "ses_api"
