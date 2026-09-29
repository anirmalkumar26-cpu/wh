from collections import defaultdict, deque
from threading import Lock
import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import CurrentUser, DbSession
from backend.app.core.security import decode_token
from backend.app.models import User
from backend.app.schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse
from backend.app.services.auth import AuthenticationError, authenticate, register_student, revoke_family, rotate_refresh

router = APIRouter(prefix="/auth", tags=["authentication"])
_requests: dict[str, deque[float]] = defaultdict(deque)
_requests_lock = Lock()


def _enforce_auth_rate_limit(request: Request) -> None:
    now = time.monotonic()
    client = request.client.host if request.client else "unknown"
    with _requests_lock:
        attempts = _requests[client]
        while attempts and attempts[0] < now - 60:
            attempts.popleft()
        if len(attempts) >= 20:
            raise HTTPException(status_code=429, detail="Too many authentication requests; try again shortly")
        attempts.append(now)


def _token_response(user, tokens: dict[str, str]) -> TokenResponse:
    return TokenResponse(access_token=tokens["access_token"], refresh_token=tokens["refresh_token"], user=user)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, request: Request, session: DbSession):
    _enforce_auth_rate_limit(request)
    try:
        user, tokens = register_student(session, str(body.email), body.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _token_response(user, tokens)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, session: DbSession):
    _enforce_auth_rate_limit(request)
    try:
        user, tokens = authenticate(session, str(body.email), body.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _token_response(user, tokens)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, request: Request, session: DbSession):
    _enforce_auth_rate_limit(request)
    try:
        claims = decode_token(body.refresh_token)
        if claims["typ"] != "refresh":
            raise ValueError("Refresh token required")
        tokens = rotate_refresh(session, claims)
    except (ValueError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail="Refresh token is invalid or revoked") from exc
    user = session.get(User, claims["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="Refresh token is invalid or revoked")
    return _token_response(user, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: CurrentUser, session: DbSession, request: Request):
    _enforce_auth_rate_limit(request)
    authorization = request.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    revoke_family(session, claims["fid"])


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser):
    return user
