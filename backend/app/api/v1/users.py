"""
用户管理 API 路由（全部端点仅 admin 可用）
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.security import get_password_hash
from app.models import User, Role
from app.schemas.user import UserCreate, UserUpdate, UserInDB, RoleSimple

router = APIRouter(prefix="/users", tags=["用户管理"])


# ==================== 角色管理 ====================

@router.get("/roles", response_model=List[RoleSimple])
async def get_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """获取所有角色列表"""
    roles = db.query(Role).all()
    return roles


# ==================== 用户管理 ====================


@router.get("")
async def list_users(
    skip: int = 0,
    limit: int = 20,
    username: Optional[str] = None,
    is_active: Optional[bool] = None,
    role_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """获取用户列表(带分页)"""
    query = db.query(User).options(joinedload(User.roles))
    
    # 过滤条件
    if username:
        query = query.filter(User.username.contains(username))
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if role_id:
        query = query.filter(User.roles.any(Role.id == role_id))
    
    total = query.count()
    users = query.offset(skip).limit(limit).all()
    return {"total": total, "items": users, "skip": skip, "limit": limit}


@router.get("/{user_id}", response_model=UserInDB)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """获取用户详情"""
    user = db.query(User).options(joinedload(User.roles)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.post("", response_model=UserInDB, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """创建用户"""
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 检查邮箱是否已存在
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    
    # 验证角色是否存在
    roles = []
    if user_data.role_ids:
        roles = db.query(Role).filter(Role.id.in_(user_data.role_ids)).all()
        if len(roles) != len(user_data.role_ids):
            raise HTTPException(status_code=400, detail="部分角色不存在")
    
    # 创建新用户
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        password_hash=get_password_hash(user_data.password),
        is_active=True,
        roles=roles
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.put("/{user_id}", response_model=UserInDB)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """更新用户信息"""
    user = db.query(User).options(joinedload(User.roles)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新基本字段
    update_data = user_data.model_dump(exclude_unset=True, exclude={'role_ids'})
    for key, value in update_data.items():
        setattr(user, key, value)
    
    # 更新角色
    if user_data.role_ids is not None:
        roles = db.query(Role).filter(Role.id.in_(user_data.role_ids)).all()
        if len(roles) != len(user_data.role_ids):
            raise HTTPException(status_code=400, detail="部分角色不存在")
        user.roles = roles
    
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """删除用户"""
    # 不允许删除自己
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 软删除：设置为不活跃
    user.is_active = False
    db.commit()
    
    return None


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    new_password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """重置用户密码"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新密码
    user.password_hash = get_password_hash(new_password)
    db.commit()
    
    return {"message": "密码重置成功"}


@router.post("/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """切换用户启用/禁用状态"""
    # 不允许禁用自己
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    
    return {
        "message": "用户状态已更新",
        "is_active": user.is_active
    }
