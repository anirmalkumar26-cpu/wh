from datetime import datetime, timezone
import secrets

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import create_token, hash_password, verify_password
from backend.app.models import AuthSession, User


class AuthenticationError(Exception):
    pass


def _issue_pair(session: Session, user: User, family_id: str | None = None) -> dict[str, str]:
    family = family_id or secrets.token_urlsafe(24)
    access_lifetime = settings.access_token_minutes * 60
    refresh_lifetime = settings.refresh_token_days * 86400
    access, access_id, access_expiry = create_token(user.id, user.role, "access", access_lifetime, family)
    refresh, refresh_id, refresh_expiry = create_token(user.id, user.role, "refresh", refresh_lifetime, family)
    session.add_all(
        [
            AuthSession(user_id=user.id, token_id=access_id, family_id=family, kind="access", expires_at=access_expiry),
            AuthSession(user_id=user.id, token_id=refresh_id, family_id=family, kind="refresh", expires_at=refresh_expiry),
        ]
    )
    session.commit()
    return {"access_token": access, "refresh_token": refresh}


def register_student(session: Session, email: str, password: str) -> tuple[User, dict[str, str]]:
    normalized_email = email.strip().casefold()
    if session.scalar(select(User).where(User.email == normalized_email)):
        raise AuthenticationError("An account with that email already exists")
    user = User(email=normalized_email, password_hash=hash_password(password), role="student")
    session.add(user)
    session.flush()
    tokens = _issue_pair(session, user)
    return user, tokens


def authenticate(session: Session, email: str, password: str) -> tuple[User, dict[str, str]]:
    user = session.scalar(select(User).where(User.email == email.strip().casefold()))
    if not user or not verify_password(password, user.password_hash) or not user.is_active:
        raise AuthenticationError("Invalid email or password")
    return user, _issue_pair(session, user)


def rotate_refresh(session: Session, claims: dict[str, str]) -> dict[str, str]:
    record = session.scalar(select(AuthSession).where(AuthSession.token_id == claims["jti"]))
    user = session.get(User, claims["sub"])
    if record and record.kind == "refresh" and record.revoked_at is not None:
        revoke_family(session, claims["fid"])
        raise AuthenticationError("Refresh token reuse detected; session family revoked")
    if (
        not record
        or record.kind != "refresh"
        or not user
        or not user.is_active
    ):
        raise AuthenticationError("Refresh token is invalid or revoked")
    now = datetime.now(timezone.utc)
    session.execute(
        update(AuthSession)
        .where(AuthSession.family_id == claims["fid"], AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    session.flush()
    return _issue_pair(session, user, family_id=claims["fid"])


def revoke_family(session: Session, family_id: str) -> None:
    session.execute(
        update(AuthSession)
        .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    session.commit()


def create_staff(session: Session, email: str, password: str, role: str) -> User:
    normalized_email = email.strip().casefold()
    if session.scalar(select(User).where(User.email == normalized_email)):
        raise AuthenticationError("An account with that email already exists")
    user = User(email=normalized_email, password_hash=hash_password(password), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
