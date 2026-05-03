"""
JWT authentication dependency.
Used by all FastAPI routes via Depends(get_current_user).
Returns an object with at minimum: id (UUID), and email (str).
"""

import os
from uuid import UUID
from typing import Annotated
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

bearer_scheme = HTTPBearer()

JWT_SECRET  = os.environ.get("JWT_SECRET", "dev-secret-change-in-prod")
JWT_ALGO    = os.environ.get("JWT_ALGORITHM", "HS256")

@dataclass
class User:
    id: UUID
    email: str

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]
) -> User:
    """
    Validates Bearer JWT from Authorization header.
    Returns: User with id and email.
    Raises 401 on any validation failure.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        user_id_raw = payload.get("sub") or payload.get("user_id")
        email = payload.get("email", "")
        if not user_id_raw:
            raise ValueError("no sub/user_id in token")
        return User(
            id=UUID(str(user_id_raw)),
            email=email,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
