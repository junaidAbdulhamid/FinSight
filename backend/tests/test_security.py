import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings
from app.security import SupabaseIdentity, SupabaseTokenVerifier, sync_local_profile


def test_enabled_auth_requires_project_configuration():
    with pytest.raises(ValidationError):
        Settings(supabase_auth_enabled=True, supabase_url=None, supabase_publishable_key=None)


@pytest.mark.asyncio
async def test_verifier_accepts_authenticated_claims(monkeypatch):
    subject = uuid.uuid4()
    verifier = SupabaseTokenVerifier()
    monkeypatch.setattr("app.security.jwt.get_unverified_header", lambda _: {"alg": "ES256", "kid": "active"})
    verifier._verify_asymmetric = AsyncMock(return_value={
        "sub": str(subject), "email": "Analyst@Example.com", "role": "authenticated",
        "aud": "authenticated", "iss": verifier.issuer, "exp": 4_000_000_000,
        "user_metadata": {"full_name": "Alex Morgan"},
    })
    identity = await verifier.verify("header.payload.signature")
    assert identity.id == subject
    assert identity.email == "analyst@example.com"
    assert identity.name == "Alex Morgan"


@pytest.mark.asyncio
async def test_verifier_rejects_wrong_role(monkeypatch):
    verifier = SupabaseTokenVerifier()
    monkeypatch.setattr("app.security.jwt.get_unverified_header", lambda _: {"alg": "RS256", "kid": "active"})
    verifier._verify_asymmetric = AsyncMock(return_value={
        "sub": str(uuid.uuid4()), "email": "user@example.com", "role": "anon",
    })
    with pytest.raises(HTTPException) as caught:
        await verifier.verify("header.payload.signature")
    assert caught.value.status_code == 401


@pytest.mark.asyncio
async def test_verifier_rejects_unknown_algorithm(monkeypatch):
    verifier = SupabaseTokenVerifier()
    monkeypatch.setattr("app.security.jwt.get_unverified_header", lambda _: {"alg": "none"})
    with pytest.raises(HTTPException):
        await verifier.verify("unsigned")


@pytest.mark.asyncio
async def test_profile_sync_creates_supabase_owned_profile():
    identity = SupabaseIdentity(uuid.uuid4(), "new@example.com", "New Analyst", {})
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    db.scalar = AsyncMock(return_value=None)
    db.flush = AsyncMock()
    profile = await sync_local_profile(db, identity)
    assert profile.id == identity.id
    assert profile.email == identity.email
    assert profile.password_hash is None
    db.add.assert_called_once_with(profile)


@pytest.mark.asyncio
async def test_profile_sync_updates_existing_profile():
    identity = SupabaseIdentity(uuid.uuid4(), "changed@example.com", "Changed Name", {})
    existing = MagicMock()
    db = MagicMock()
    db.get = AsyncMock(return_value=existing)
    db.flush = AsyncMock()
    assert await sync_local_profile(db, identity) is existing
    assert existing.email == identity.email
    assert existing.name == identity.name
