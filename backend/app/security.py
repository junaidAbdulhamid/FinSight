import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import AuditEvent, Document, Generation, User

bearer = HTTPBearer(auto_error=False)
ALLOWED_ASYMMETRIC_ALGORITHMS = {"RS256", "ES256"}


@dataclass(frozen=True)
class SupabaseIdentity:
    id: uuid.UUID
    email: str
    name: str
    claims: dict[str, Any]


class SupabaseTokenVerifier:
    """Verify rotating Supabase access tokens without ever handling a signing secret."""

    def __init__(self) -> None:
        self._keys: dict[str, dict[str, Any]] = {}
        self._keys_expire_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def issuer(self) -> str:
        return f"{settings.supabase_url}/auth/v1"

    async def _fetch_keys(self, force: bool = False) -> None:
        if not force and self._keys and time.monotonic() < self._keys_expire_at:
            return
        async with self._lock:
            if not force and self._keys and time.monotonic() < self._keys_expire_at:
                return
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.issuer}/.well-known/jwks.json")
                response.raise_for_status()
            self._keys = {item["kid"]: item for item in response.json().get("keys", []) if item.get("kid")}
            self._keys_expire_at = time.monotonic() + settings.supabase_jwks_cache_seconds

    async def _verify_asymmetric(self, token: str, kid: str, algorithm: str) -> dict[str, Any]:
        await self._fetch_keys()
        key_data = self._keys.get(kid)
        if not key_data:
            await self._fetch_keys(force=True)
            key_data = self._keys.get(kid)
        if not key_data or key_data.get("alg") not in {None, algorithm}:
            raise JWTError("Signing key is unavailable")
        return jwt.decode(
            token,
            jwk.construct(key_data, algorithm=algorithm),
            algorithms=[algorithm],
            audience="authenticated",
            issuer=self.issuer,
            options={"require_aud": True, "require_exp": True, "require_sub": True},
        )

    async def _verify_legacy_with_auth(self, token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{self.issuer}/user",
                headers={"apikey": settings.supabase_publishable_key or "", "Authorization": f"Bearer {token}"},
            )
        if response.status_code != 200:
            raise JWTError("Supabase Auth rejected the token")
        claims = jwt.get_unverified_claims(token)
        if claims.get("iss") != self.issuer or claims.get("aud") != "authenticated":
            raise JWTError("Invalid token claims")
        remote_user = response.json()
        return {**claims, "email": remote_user.get("email"), "user_metadata": remote_user.get("user_metadata", {})}

    async def verify(self, token: str) -> SupabaseIdentity:
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            if algorithm in ALLOWED_ASYMMETRIC_ALGORITHMS and header.get("kid"):
                claims = await self._verify_asymmetric(token, header["kid"], algorithm)
            elif algorithm == "HS256":
                claims = await self._verify_legacy_with_auth(token)
            else:
                raise JWTError("Unsupported signing algorithm")
            if claims.get("role") != "authenticated":
                raise JWTError("Not an authenticated user session")
            email = claims.get("email")
            if not isinstance(email, str) or not email:
                raise JWTError("Email claim is missing")
            metadata = claims.get("user_metadata") or {}
            name = metadata.get("full_name") or metadata.get("name") or email.split("@", 1)[0]
            return SupabaseIdentity(uuid.UUID(claims["sub"]), email.lower(), str(name)[:120], claims)
        except (JWTError, ValueError, KeyError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=401, detail="Invalid or expired session") from exc


verifier = SupabaseTokenVerifier()


async def sync_local_profile(db: AsyncSession, identity: SupabaseIdentity) -> User:
    user = await db.get(User, identity.id)
    if user:
        user.email, user.name = identity.email, identity.name
        await db.flush()
        return user
    legacy = await db.scalar(select(User).where(User.email == identity.email))
    if legacy:
        legacy.email = f"migrating-{legacy.id}@invalid.local"
        await db.flush()
        user = User(id=identity.id, email=identity.email, name=identity.name, password_hash=None, role=legacy.role)
        db.add(user)
        await db.flush()
        await db.execute(update(Document).where(Document.owner_id == legacy.id).values(owner_id=identity.id))
        await db.execute(update(Generation).where(Generation.user_id == legacy.id).values(user_id=identity.id))
        await db.execute(update(AuditEvent).where(AuditEvent.actor_id == legacy.id).values(actor_id=identity.id))
        await db.delete(legacy)
        await db.flush()
        return user
    new_user = User(id=identity.id, email=identity.email, name=identity.name, password_hash=None)
    db.add(new_user)
    await db.flush()
    return new_user


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not settings.supabase_auth_enabled:
        raise HTTPException(status_code=503, detail="Authentication is not enabled")
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required")
    user = await sync_local_profile(db, await verifier.verify(credentials.credentials))
    await db.commit()
    return user
