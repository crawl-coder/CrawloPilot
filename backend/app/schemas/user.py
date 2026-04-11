from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class RoleSimple(BaseModel):
    """简单角色信息"""
    id: int
    name: str
    description: Optional[str] = None
    
    class Config:
        from_attributes = True


class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str
    role_ids: Optional[List[int]] = None  # 角色ID列表


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role_ids: Optional[List[int]] = None  # 角色ID列表


class UserInDB(UserBase):
    id: int
    is_active: bool
    roles: List[RoleSimple] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
