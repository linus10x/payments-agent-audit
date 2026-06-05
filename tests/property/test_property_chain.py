"""Property-based tests for the audit chain (the volume tier, §7).

Generates thousands of cases: any sequence of appends verifies True; any
single-field mutation of any event breaks verification; hardened and legacy
chains both verify.
"""

from __future__ import annotations

import warnings

from hypothesis import given, settings
from hypothesis import strategies as st

from payments_agent_audit.governance.audit_chain import AuditChain, AuditChainTamperError
from payments_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel

CREATED = "2026-06-05T00:00:00+00:00"

_EVENT_TYPES = list(AuditEventType)
_LEVELS = list(AutonomyLevel)

payloads = st.dictionaries(
    keys=st.text(min_size=1, max_size=8),
    values=st.one_of(st.integers(), st.text(max_size=16), st.booleans()),
    max_size=5,
)
appends = st.lists(
    st.tuples(
        st.sampled_from(_EVENT_TYPES),
        st.sampled_from(_LEVELS),
        st.text(min_size=1, max_size=12),
        payloads,
    ),
    min_size=1,
    max_size=20,
)


@settings(max_examples=400)
@given(events=appends)
def test_any_append_sequence_verifies(events) -> None:
    chain = AuditChain(deployer_id="prop", chain_creation_iso=CREATED)
    for et, lvl, agent, payload in events:
        chain.append(et, lvl, agent, payload)
    assert chain.verify() is True
    chain.verify_strict()
    assert chain.length == len(events) + 1  # +1 genesis


@settings(max_examples=300)
@given(events=appends, idx=st.integers(min_value=0, max_value=19))
def test_any_payload_mutation_breaks_verification(events, idx) -> None:
    chain = AuditChain(deployer_id="prop", chain_creation_iso=CREATED)
    for et, lvl, agent, payload in events:
        chain.append(et, lvl, agent, payload)
    target = idx % chain.length
    victim = chain._events[target]
    object.__setattr__(victim, "payload", {**victim.payload, "__injected__": "tamper"})
    assert chain.verify() is False
    try:
        chain.verify_strict()
        raise AssertionError("verify_strict should have raised")
    except AuditChainTamperError:
        pass


@settings(max_examples=200)
@given(events=appends)
def test_legacy_chain_also_verifies(events) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        chain = AuditChain()
        for et, lvl, agent, payload in events:
            chain.append(et, lvl, agent, payload)
        assert chain.verify() is True


@settings(max_examples=200)
@given(deployer=st.text(min_size=1, max_size=20), other=st.text(min_size=1, max_size=20))
def test_distinct_deployers_distinct_genesis(deployer, other) -> None:
    a = AuditChain(deployer_id=deployer, chain_creation_iso=CREATED)
    b = AuditChain(deployer_id=other, chain_creation_iso=CREATED)
    if deployer == other:
        assert a._events[0].prev_hash == b._events[0].prev_hash
    else:
        assert a._events[0].prev_hash != b._events[0].prev_hash
