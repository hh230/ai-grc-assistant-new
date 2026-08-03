"""`ServiceAssertionIdentityProvider` — the interim apps/web -> grc-api identity bridge (ADR 0066
addendum). Pure unit tests, no HTTP/database involved."""

from __future__ import annotations

import time

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
    tampered = f"{payload_b64}x.{signature}"  # corrupt the payload, keep the (now-mismatched) signature
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
