"""Authentication API Endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.org import OrgMember
from app.schemas.auth import UserRegister, UserLogin, UserRead, OrgRead, Token
from app.core.auth import (
    verify_password,
    create_access_token,
    create_user_with_default_org,
    get_current_user,
    get_current_org,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user, create their default organization, and grant initial credits."""
    user, org = await create_user_with_default_org(
        db=db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        org_name=payload.org_name,
    )
    token = create_access_token(user_id=user.id, org_id=org.id, email=user.email)
    user_read = UserRead.model_validate(user)
    user_read.active_org = OrgRead.model_validate(org)
    return Token(access_token=token, token_type="bearer", user=user_read)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with username (email) and password, returning signed JWT."""
    query = (
        select(User)
        .where(User.email == form_data.username.lower())
        .options(selectinload(User.org_memberships).selectinload(OrgMember.org))
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    active_org = user.org_memberships[0].org if user.org_memberships else None
    if not active_org:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No organization assigned")

    token = create_access_token(user_id=user.id, org_id=active_org.id, email=user.email)
    user_read = UserRead.model_validate(user)
    user_read.active_org = OrgRead.model_validate(active_org)
    return Token(access_token=token, token_type="bearer", user=user_read)


@router.get("/me", response_model=UserRead)
async def get_me(
    current_user: User = Depends(get_current_user),
    current_org = Depends(get_current_org),
):
    """Get authenticated user profile and active organization context."""
    user_read = UserRead.model_validate(current_user)
    user_read.active_org = OrgRead.model_validate(current_org)
    return user_read
