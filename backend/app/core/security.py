import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from backend.app.core.config import settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def _encode_segment(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode_segment(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def create_token(user_id: str, role: str, kind: str, lifetime_seconds: int, family_id: str) -> tuple[str, str, datetime]:
    issued = int(time.time())
    expires = issued + lifetime_seconds
    token_id = secrets.token_urlsafe(24)
    header = _encode_segment(b'{"alg":"HS256","typ":"JWT"}')
    payload = _encode_segment(
        json.dumps(
            {"sub": user_id, "role": role, "typ": kind, "jti": token_id, "fid": family_id, "iat": issued, "exp": expires},
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_encode_segment(signature)}", token_id, datetime.fromtimestamp(expires, timezone.utc)


def decode_token(token: str) -> dict[str, Any]:
    try:
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}".encode("ascii")
        expected = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode_segment(signature)):
            raise ValueError("Invalid token signature")
        decoded_header = json.loads(_decode_segment(header))
        claims = json.loads(_decode_segment(payload))
        if decoded_header != {"alg": "HS256", "typ": "JWT"}:
            raise ValueError("Unsupported token algorithm")
        if not isinstance(claims, dict) or claims.get("exp", 0) <= int(time.time()):
            raise ValueError("Token has expired")
        if not all(isinstance(claims.get(key), str) and claims[key] for key in ("sub", "typ", "jti", "fid")):
            raise ValueError("Token claims are invalid")
        return claims
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, binascii.Error) as exc:
        raise ValueError("Invalid or expired token") from exc
