from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.rate_limit import enforce_rate_limit
from app.core.security import create_access_token, current_user, hash_password, verify_password
from app.models import User
from app.schemas import Credentials, TokenRead, UserRead

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=TokenRead, status_code=status.HTTP_201_CREATED)
async def register(payload: Credentials, request: Request, session: AsyncSession = Depends(get_session)):
    await enforce_rate_limit(request, f"register:{request.client.host if request.client else 'unknown'}", 8)
    normalized_email = str(payload.email).lower()
    if await session.scalar(select(User.id).where(User.email == normalized_email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=normalized_email, hashed_password=hash_password(payload.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return TokenRead(access_token=create_access_token(user.id), user=UserRead.model_validate(user))


@router.post("/login", response_model=TokenRead)
async def login(payload: Credentials, request: Request, session: AsyncSession = Depends(get_session)):
    await enforce_rate_limit(request, f"login:{request.client.host if request.client else 'unknown'}", 12)
    user = await session.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    return TokenRead(access_token=create_access_token(user.id), user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(current_user)):
    return UserRead.model_validate(user)
