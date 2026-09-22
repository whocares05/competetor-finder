"""Feedback API Endpoints"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.org import Org
from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.core.auth import get_current_user, get_current_org

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])


@router.post("", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Submit user feedback regarding competitors for eval set refinement."""
    feedback = Feedback(
        org_id=current_org.id,
        user_id=current_user.id,
        search_id=payload.search_id,
        search_result_id=payload.search_result_id,
        feedback_type=payload.feedback_type,
        competitor_name=payload.competitor_name,
        notes=payload.notes,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return FeedbackRead.model_validate(feedback)
