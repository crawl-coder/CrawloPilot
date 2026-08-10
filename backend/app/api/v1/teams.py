"""
团队管理 API 路由（v1 精简版：仅提供列表供下拉选择）
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Team

router = APIRouter(prefix="/teams", tags=["团队"])


class TeamResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("", response_model=List[TeamResponse])
async def list_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取团队列表"""
    return db.query(Team).order_by(Team.created_at.desc()).all()
