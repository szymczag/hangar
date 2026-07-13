from plane.authentication.utils.password import PASSWORD_MIN_LENGTH, is_password_strong


def test_password_policy_rejects_short_password_even_when_guessability_is_high():
    assert not is_password_strong("Tr0ub4dor&3")


def test_password_policy_rejects_long_obvious_password():
    assert not is_password_strong("passwordpassword")


def test_password_policy_accepts_long_memorable_passphrase_without_composition_rules():
    password = "correct horse battery staple"

    assert len(password) >= PASSWORD_MIN_LENGTH
    assert is_password_strong(password)
