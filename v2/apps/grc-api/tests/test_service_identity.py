"""`ServiceAssertionIdentityProvider` — the interim apps/web -> grc-api identity bridge (ADR 0066
addendum). Pure unit tests, no HTTP/database involved."""

from __future__ import annotations

from grc_api.service_identity import (
    CompositeIdentityProvider,
    ServiceAssertionIdentityProvider,
    mint_service_assertion,
)


def test_a_validly_signed_token_resolves_to_the_asserted_tenant() -> None:
    provider = ServiceAssertionIdentityProvider(secret="shared-secret")
    token = mint_service_assertion(
        secret="shared-secret", tenant_id="org_123", principal_id="user_456", roles=("owner",)
    )
    tenant = provider.resolve(token)
    assert tenant is not None
    assert tenant.tenant_id == "org_123"
    assert tenant.principal_id == "user_456"
    assert tenant.roles == ("owner",)


def test_a_token_signed_with_a_different_secret_is_rejected() -> None:
    provider = ServiceAssertionIdentityProvider(secret="shared-secret")
    token = mint_service_assertion(secret="wrong-secret", tenant_id="org_123")
    assert provider.resolve(token) is None


def test_a_tampered_payload_is_rejected() -> None:
    provider = ServiceAssertionIdentityProvider(secret="shared-secret")
    token = mint_service_assertion(secret="shared-secret", tenant_id="org_123")
    payload_b64, _, signature = token.partition(".")
    tampered = f"{payload_b64}x.{signature}"  # corrupt the payload, signature now mismatched
    assert provider.resolve(tampered) is None


def test_an_expired_token_is_rejected() -> None:
    provider = ServiceAssertionIdentityProvider(secret="shared-secret")
    token = mint_service_assertion(secret="shared-secret", tenant_id="org_123", ttl_seconds=-10)
    assert provider.resolve(token) is None


def test_a_malformed_credential_is_rejected_not_raised() -> None:
    provider = ServiceAssertionIdentityProvider(secret="shared-secret")
    assert provider.resolve("not-a-real-token") is None
    assert provider.resolve("") is None
    assert provider.resolve("....") is None


def test_composite_provider_tries_each_in_order() -> None:
    class _FixedProvider:
        def resolve(self, credential: str):
            return None

    service_provider = ServiceAssertionIdentityProvider(secret="s")
    composite = CompositeIdentityProvider((_FixedProvider(), service_provider))
    token = mint_service_assertion(secret="s", tenant_id="org_x")
    tenant = composite.resolve(token)
    assert tenant is not None
    assert tenant.tenant_id == "org_x"
    assert composite.resolve("nothing-matches-anything") is None


def test_secret_must_be_non_empty() -> None:
    import pytest

    with pytest.raises(ValueError):
        ServiceAssertionIdentityProvider(secret="")


# --- rotation (B4) -----------------------------------------------------------------------------


def test_a_token_signed_with_either_accepted_secret_is_valid() -> None:
    """The property the whole rotation rests on. With one accepted value, rotation needs both
    sides to change at the same instant and any skew rejects every request — so the first attempt
    at rotating would happen during a security incident, and fail."""
    provider = ServiceAssertionIdentityProvider(["new-secret", "old-secret"])

    for secret in ("new-secret", "old-secret"):
        token = mint_service_assertion(secret=secret, tenant_id="t-1", principal_id="p-1")
        resolved = provider.resolve(token)
        assert resolved is not None, f"a token signed with {secret!r} must be accepted"
        assert resolved.tenant_id == "t-1"


def test_a_retired_secret_stops_working_once_removed() -> None:
    """Step 3 of the rotation must actually revoke. A rotation that never retires the old key is
    not a rotation."""
    token = mint_service_assertion(secret="old-secret", tenant_id="t-1")
    assert ServiceAssertionIdentityProvider(["new-secret"]).resolve(token) is None


def test_a_single_secret_string_is_still_accepted() -> None:
    """Backwards compatible: existing callers pass one string."""
    token = mint_service_assertion(secret="only", tenant_id="t-1")
    assert ServiceAssertionIdentityProvider("only").resolve(token) is not None


def test_blank_entries_never_become_accepted_keys() -> None:
    """A trailing comma in a secret-manager value must not create an empty accepted secret."""
    provider = ServiceAssertionIdentityProvider(["real", "", "  "])
    assert provider.resolve(mint_service_assertion(secret="", tenant_id="t-1")) is None
    assert provider.resolve(mint_service_assertion(secret="real", tenant_id="t-1")) is not None


def test_no_secrets_at_all_is_refused_loudly() -> None:
    """Failing closed at construction beats accepting everything at runtime."""
    import pytest

    with pytest.raises(ValueError):
        ServiceAssertionIdentityProvider(["", "   "])


def test_verification_does_not_short_circuit_on_the_first_match() -> None:
    """Every candidate is compared, so response timing never reveals how many keys are in
    rotation."""
    import inspect

    source = inspect.getsource(ServiceAssertionIdentityProvider.resolve)
    assert "matched |=" in source, "the loop must not break early on a match"
    assert "compare_digest" in source


def test_the_env_var_expresses_a_rotation_as_a_comma_separated_list(monkeypatch: object) -> None:
    """Rotation must be a configuration change, not a code change."""
    from grc_api.app import GOVERNANCE_SERVICE_SECRET_ENV_VAR, service_secrets

    monkeypatch.setenv(GOVERNANCE_SERVICE_SECRET_ENV_VAR, " new , old ,")  # type: ignore[attr-defined]
    assert service_secrets() == ("new", "old")


def test_an_unset_env_var_yields_no_secrets(monkeypatch: object) -> None:
    from grc_api.app import GOVERNANCE_SERVICE_SECRET_ENV_VAR, service_secrets

    monkeypatch.delenv(GOVERNANCE_SERVICE_SECRET_ENV_VAR, raising=False)  # type: ignore[attr-defined]
    assert service_secrets() == ()
