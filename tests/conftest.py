"""Shared test fixtures and fakes."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest

from payments_agent_audit.governance.audit_chain import AuditChain
from payments_agent_audit.governance.ofac_screening import SanctionedParty


class FakeAuthorizer:
    """Test Authorizer. ``valid_credentials`` maps credential -> principal id;
    ``allow`` decides authorize(). Models an IdP/KMS resolving a credential to
    an authenticated principal."""

    def __init__(
        self,
        valid_credentials: dict[str, str] | None = None,
        allow: bool = True,
    ) -> None:
        self.valid_credentials = valid_credentials or {"valid-token": "operator-001"}
        self.allow = allow

    def authenticate(self, credential: str) -> str | None:
        return self.valid_credentials.get(credential)

    def authorize(self, principal_id: str, action: str, context: dict[str, Any]) -> bool:
        return self.allow


class StaticSanctionsList:
    """A pluggable sanctions-list provider for tests. No bundled production list."""

    def __init__(self, parties: list[SanctionedParty]) -> None:
        self._parties = parties

    def entries(self) -> Iterable[SanctionedParty]:
        return list(self._parties)


@pytest.fixture
def authorizer() -> FakeAuthorizer:
    return FakeAuthorizer()


@pytest.fixture
def chain() -> AuditChain:
    return AuditChain(deployer_id="test-deployer", chain_creation_iso="2026-06-05T00:00:00+00:00")


@pytest.fixture
def sanctions_list() -> StaticSanctionsList:
    return StaticSanctionsList(
        [
            SanctionedParty(
                uid="SDN-1001",
                name="Vladimir Smirnov",
                aliases=("V. Smirnov", "Vladimir Smirnoff"),
                programs=("UKRAINE-EO13662",),
                entity_type="individual",
            ),
            SanctionedParty(
                uid="SDN-2002",
                name="Banco Internacional Sancionado SA",
                aliases=("BIS SA",),
                programs=("VENEZUELA",),
                entity_type="entity",
            ),
        ]
    )
