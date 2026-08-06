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


# ==================== 个人 Git 凭据 ====================

class GitCredentialPayload(BaseModel):
    """保存个人 Git 凭据（秘密字段留空表示保留原值）"""
    auth_type: str = "password"  # password 或 ssh
    username: Optional[str] = None
    password: Optional[str] = None      # 留空=保留原值
    ssh_key: Optional[str] = None       # 留空=保留原值
    passphrase: Optional[str] = None    # 留空=保留原值
    default_branch: Optional[str] = None


class GitCredentialInfo(BaseModel):
    """个人 Git 凭据的脱敏信息"""
    configured: bool = False
    auth_type: Optional[str] = None
    username: Optional[str] = None
    default_branch: Optional[str] = None
    has_password: bool = False
    has_ssh_key: bool = False
    has_passphrase: bool = False
