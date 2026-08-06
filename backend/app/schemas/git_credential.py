"""
共享 Git 凭据（团队机器人凭据）Pydantic Schemas
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class GitCredentialCreate(BaseModel):
    """创建共享凭据"""
    name: str
    description: Optional[str] = None
    auth_type: str = "password"  # password 或 ssh
    username: Optional[str] = None
    password: Optional[str] = None
    ssh_key: Optional[str] = None
    passphrase: Optional[str] = None
    default_branch: Optional[str] = None
    is_active: bool = True


class GitCredentialUpdate(BaseModel):
    """更新共享凭据（秘密字段留空表示保留原值）"""
    name: Optional[str] = None
    description: Optional[str] = None
    auth_type: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None      # 留空=保留原值
    ssh_key: Optional[str] = None       # 留空=保留原值
    passphrase: Optional[str] = None    # 留空=保留原值
    default_branch: Optional[str] = None
    is_active: Optional[bool] = None


class GitCredentialOut(BaseModel):
    """共享凭据的脱敏输出（不回传秘密本体）"""
    id: int
    name: str
    description: Optional[str] = None
    auth_type: str
    username: Optional[str] = None
    default_branch: Optional[str] = None
    has_password: bool = False
    has_ssh_key: bool = False
    is_active: bool = True
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
