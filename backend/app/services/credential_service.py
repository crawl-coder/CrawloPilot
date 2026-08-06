"""
Git 凭据服务

职责：
1. 个人凭据（user.git_credentials，加密 JSON）的打包/解包/展示
2. 爬虫 Git 操作的凭据解析：共享凭据池（GitCredential）> 爬虫内联凭据
3. 管理员权限校验依赖
"""
import json
from types import SimpleNamespace
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_text, decrypt_text
from app.core.dependencies import get_current_user
from app.models import User, GitCredential


# ==================== 权限 ====================

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """仅 admin 角色可访问"""
    if not any(r.name == "admin" for r in current_user.roles):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


# ==================== 个人凭据（User.git_credentials） ====================

def pack_user_credentials(payload: dict) -> str:
    """将个人凭据打包为加密 JSON 字符串"""
    data = {
        "auth_type": payload.get("auth_type") or "password",
        "username": payload.get("username") or "",
        "password": payload.get("password") or "",
        "ssh_key": payload.get("ssh_key") or "",
        "passphrase": payload.get("passphrase") or "",
        "default_branch": payload.get("default_branch") or "",
    }
    return encrypt_text(json.dumps(data, ensure_ascii=False))


def unpack_user_credentials(user: User) -> Optional[dict]:
    """解包个人凭据；未配置或解密失败返回 None"""
    if not user.git_credentials:
        return None
    plain = decrypt_text(user.git_credentials)
    if not plain:
        return None
    try:
        return json.loads(plain)
    except json.JSONDecodeError:
        return None


def mask_user_credentials(user: User) -> Optional[dict]:
    """个人凭据的脱敏展示（不回传秘密本体）"""
    data = unpack_user_credentials(user)
    if data is None:
        return None
    return {
        "auth_type": data.get("auth_type") or "password",
        "username": data.get("username") or "",
        "default_branch": data.get("default_branch") or "",
        "has_password": bool(data.get("password")),
        "has_ssh_key": bool(data.get("ssh_key")),
        "has_passphrase": bool(data.get("passphrase")),
    }


# ==================== 爬虫凭据解析 ====================

def resolve_spider_git_credentials(db: Session, spider) -> SimpleNamespace:
    """
    解析爬虫 Git 操作实际使用的凭据，返回带 git_* 属性的轻量对象：
    - spider.git_credential_id 指向有效共享凭据 → 解密后使用（蜘蛛自身内联凭据留空时）
    - 否则 → 使用蜘蛛自身内联凭据
    """
    if spider.git_credential_id:
        cred = db.query(GitCredential).filter(
            GitCredential.id == spider.git_credential_id,
            GitCredential.is_active == True,  # noqa: E712
        ).first()
        if cred:
            return SimpleNamespace(
                git_url=spider.git_url,
                git_auth_type=cred.auth_type or "password",
                git_username=cred.username,
                git_password=decrypt_text(cred.password),
                git_ssh_key=decrypt_text(cred.ssh_key),
                git_passphrase=decrypt_text(cred.passphrase),
            )
    return SimpleNamespace(
        git_url=spider.git_url,
        git_auth_type=spider.git_auth_type,
        git_username=spider.git_username,
        git_password=spider.git_password,
        git_ssh_key=spider.git_ssh_key,
        git_passphrase=spider.git_passphrase,
    )
