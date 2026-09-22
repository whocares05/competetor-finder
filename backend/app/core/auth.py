"""Core Authentication, Password Hashing, and JWT Management"""
import uuid
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import settings
from app.db.session import get_db
from app.models.user import User
from app.models.org import Org, OrgMember
from app.models.credit_ledger import CreditLedger
from app.schemas.auth import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check plain password against stored hash using native bcrypt."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash plain password using native bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")


def create_access_token(
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    email: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Mint signed JWT access token containing user_id and active org_id."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "email": email,
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        org_id: str = payload.get("org_id")
        email: str = payload.get("email")
        exp: int = payload.get("exp")
        if not user_id or not org_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return TokenPayload(sub=user_id, org_id=org_id, email=email, exp=exp)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_or_create_default_demo_user(db: AsyncSession) -> tuple[User, Org]:
    """Retrieve or auto-provision a default demo workspace with test credits for testing without sign-in."""
    demo_email = "demo@compfinder.ai"
    query = (
        select(User)
        .where(User.email == demo_email)
        .options(selectinload(User.org_memberships).selectinload(OrgMember.org))
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if user and user.org_memberships:
        return user, user.org_memberships[0].org

    # Create demo user and organization
    user, org = await create_user_with_default_org(
        db=db,
        email=demo_email,
        password="DemoPassword123!",
        full_name="Demo User",
        org_name="Demo Workspace",
    )
    # Refresh to load relationships
    res = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.org_memberships).selectinload(OrgMember.org))
    )
    user = res.scalar_one()
    return user, user.org_memberships[0].org


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency resolving authenticated user, or falling back to demo user for testing without signing in."""
    if token:
        try:
            payload = decode_access_token(token)
            user_uuid = uuid.UUID(payload.sub)
            query = (
                select(User)
                .where(User.id == user_uuid, User.is_active == True)
                .options(selectinload(User.org_memberships).selectinload(OrgMember.org))
            )
            result = await db.execute(query)
            user = result.scalar_one_or_none()
            if user:
                return user
        except Exception:
            pass

    # Seamless development fallback: auto-provision / use demo user
    user, _ = await get_or_create_default_demo_user(db)
    return user


async def get_current_org(
    user: User = Depends(get_current_user),
    x_org_id: Optional[str] = Header(None, description="Optional organization switch header"),
) -> Org:
    """FastAPI dependency resolving active tenant organization for the current user."""
    if user.org_memberships:
        if x_org_id:
            try:
                target_uuid = uuid.UUID(x_org_id)
                for membership in user.org_memberships:
                    if membership.org_id == target_uuid:
                        return membership.org
            except ValueError:
                pass
        return user.org_memberships[0].org

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="User is not a member of any organization",
    )


async def create_user_with_default_org(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    org_name: Optional[str] = None,
) -> tuple[User, Org]:
    """Atomically provisions a user, default organization, membership, and initial credit grant."""
    # Check if user already exists
    existing = await db.execute(select(User).where(User.email == email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    # 1. Create User
    user = User(
        email=email.lower(),
        hashed_password=get_password_hash(password),
        full_name=full_name,
    )
    db.add(user)
    await db.flush()

    # 2. Create Default Org
    slug_base = re.sub(r"[^a-zA-Z0-9]", "-", (org_name or email.split("@")[0])).lower().strip("-")
    slug = f"{slug_base}-{uuid.uuid4().hex[:6]}"
    org = Org(
        name=org_name or f"{user.full_name or 'User'}'s Workspace",
        slug=slug,
        plan_tier=settings.PLAN_TIER,
    )
    db.add(org)
    await db.flush()

    # 3. Create Org Member (Owner)
    membership = OrgMember(
        org_id=org.id,
        user_id=user.id,
        role="owner",
    )
    db.add(membership)

    # 4. Grant Initial Free Credits in Append-Only Ledger
    initial_credits = 50 if settings.PLAN_TIER == "free" else 500
    credit_entry = CreditLedger(
        org_id=org.id,
        amount=initial_credits,
        entry_type="grant",
        balance_after=initial_credits,
        description="Initial account registration grant",
    )
    db.add(credit_entry)
    await db.commit()
    await db.refresh(user)
    await db.refresh(org)

    return user, org
