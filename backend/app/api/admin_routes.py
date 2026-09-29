from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.dependencies import DbSession, require_roles
from backend.app.models import User
from backend.app.schemas import AdminUserRequest, UserResponse
from backend.app.services.auth import AuthenticationError, create_staff

router = APIRouter(prefix="/admin", tags=["administration"])


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(body: AdminUserRequest, session: DbSession, _: Annotated[User, Depends(require_roles("administrator"))]):
    try:
        return create_staff(session, str(body.email), body.password, body.role)
    except AuthenticationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
