# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The pre-cutover report has to classify accounts the way sign-in will treat them.

Its whole purpose is to say which accounts survive pinning a domain and which
are refused, so a wrong classification here sends an operator into the cutover
believing nobody will be locked out.
"""

import csv
import uuid
from io import StringIO

import pytest
from django.core.management import call_command

from plane.db.models import Account, FederatedIdentity, User


def _user(email, *, password=False, active=True):
    user = User.objects.create(
        email=email,
        username=uuid.uuid4().hex,
        is_password_autoset=not password,
        is_active=active,
    )
    return user


def _run(**options):
    out = StringIO()
    call_command("audit_user_identities", stdout=out, **options)
    return out.getvalue()


@pytest.mark.contract
@pytest.mark.django_db
def test_classifies_the_three_populations_that_matter_at_cutover():
    bound = _user("bound@corp.com")
    FederatedIdentity.objects.create(
        user=bound,
        provider="google",
        issuer="https://accounts.google.com",
        subject="sub-1",
        subject_format="",
        email_at_link=bound.email,
        last_email=bound.email,
    )
    adoptable = _user("adoptable@corp.com")
    Account.objects.create(
        user=adoptable,
        provider="google",
        provider_account_id="sub-2",
        access_token="t",
        last_connected_at="2026-01-01T00:00:00Z",
    )
    _user("passwordonly@corp.com", password=True)

    output = _run(domain="corp.com", provider="google")

    assert "bound@corp.com" in output and "federated" in output
    assert "adoptable@corp.com" in output and "adoptable" in output
    assert "passwordonly@corp.com" in output and "needs-import" in output
    assert "would be refused" in output


@pytest.mark.contract
@pytest.mark.django_db
def test_an_account_bound_to_a_different_provider_still_needs_an_import():
    """A SAML binding does not help when the domain is being pinned to Google."""
    user = _user("elsewhere@corp.com")
    FederatedIdentity.objects.create(
        user=user,
        provider="saml",
        issuer="https://idp.example",
        subject="sub-3",
        subject_format="",
        email_at_link=user.email,
        last_email=user.email,
    )

    output = _run(domain="corp.com", provider="google")

    assert "needs-import" in output


@pytest.mark.contract
@pytest.mark.django_db
def test_other_domains_are_excluded():
    _user("person@corp.com", password=True)
    _user("person@other.com", password=True)

    output = _run(domain="corp.com")

    assert "person@corp.com" in output
    assert "person@other.com" not in output


@pytest.mark.contract
@pytest.mark.django_db
def test_deactivated_accounts_are_hidden_unless_asked_for():
    _user("gone@corp.com", active=False)

    assert "gone@corp.com" not in _run(domain="corp.com")
    assert "gone@corp.com" in _run(domain="corp.com", include_inactive=True)


@pytest.mark.contract
@pytest.mark.django_db
def test_csv_output_is_machine_readable_for_building_the_import():
    user = _user("person@corp.com", password=True)

    output = _run(domain="corp.com", provider="google", csv=True)

    assert "user_id,email" in output
    assert str(user.id) in output
    assert "needs-import" in output


@pytest.mark.contract
@pytest.mark.django_db
def test_reports_nothing_rather_than_failing_on_an_empty_domain():
    assert "No matching users" in _run(domain="empty.example")


def _bind(user):
    FederatedIdentity.objects.create(
        user=user,
        provider="google",
        issuer="https://accounts.google.com",
        subject=uuid.uuid4().hex,
        subject_format="",
        email_at_link=user.email,
        last_email=user.email,
    )


def _federated_population():
    """A federated account holding a password, one without, and an ordinary one."""
    escaped = _user("escaped@corp.com", password=True)
    escaped.set_password("Tr0ub4dor&3-quite-long")
    escaped.save()
    _bind(escaped)

    clean = _user("clean@corp.com")
    clean.set_unusable_password()
    clean.save()
    _bind(clean)

    ordinary = _user("ordinary@corp.com", password=True)
    ordinary.set_password("Tr0ub4dor&3-quite-long")
    ordinary.save()
    return escaped, clean, ordinary


@pytest.mark.contract
@pytest.mark.django_db
def test_flags_a_federated_account_that_still_holds_a_password():
    _federated_population()

    output = _run(domain="corp.com")

    flagged = [line for line in output.splitlines() if "@corp.com" in line and "yes!" in line]
    assert len(flagged) == 1 and flagged[0].startswith("escaped@corp.com")
    assert "1 federated account(s) still hold a usable Hangar password" in output


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unusable_password_is_not_a_password():
    """What the provider writes on account creation must not read as a way in."""
    _escaped, clean, _ordinary = _federated_population()

    rows = {row["email"]: row for row in csv.DictReader(StringIO(_run(domain="corp.com", csv=True)))}

    assert rows[clean.email]["has_password"] == "False"
    assert rows[clean.email]["federated_with_password"] == "False"
    assert rows["escaped@corp.com"]["federated_with_password"] == "True"
    assert rows["ordinary@corp.com"]["has_password"] == "True"
    assert rows["ordinary@corp.com"]["federated_with_password"] == "False", "an ordinary password is not the finding"


@pytest.mark.contract
@pytest.mark.django_db
def test_the_filter_lists_only_the_accounts_to_clear():
    _federated_population()

    output = _run(domain="corp.com", federated_with_password=True)

    assert "escaped@corp.com" in output
    assert "clean@corp.com" not in output
    assert "ordinary@corp.com" not in output


@pytest.mark.contract
@pytest.mark.django_db
def test_no_warning_when_nothing_is_flagged():
    _user("person@corp.com", password=True)

    assert "still hold a usable Hangar password" not in _run(domain="corp.com")
