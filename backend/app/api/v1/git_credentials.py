"""
共享 Git 凭据（团队机器人凭据）管理 API

- 列表/详情：所有登录用户可读（用于创建爬虫时选择），输出脱敏
- 创建/更新/删除/启停：仅 admin
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.crypto import encrypt_text
from app.models import User, GitCredential, Spider
from app.schemas.git_credential import (
    GitCredentialCreate, GitCredentialUpdate, GitCredentialOut,
)
from app.services.credential_service import require_admin

router = APIRouter(prefix="/git-credentials", tags=["共享Git凭据"])


def _to_out(cred: GitCredential) -> GitCredentialOut:
    return GitCredentialOut(
        id=cred.id,
        name=cred.name,
        description=cred.description,
        auth_type=cred.auth_type,
        username=cred.username,
        default_branch=cred.default_branch,
        has_password=bool(cred.password),
        has_ssh_key=bool(cred.ssh_key),
        is_active=cred.is_active,
        created_by=cred.created_by,
        created_at=cred.created_at,
        updated_at=cred.updated_at,
    )


def _validate_payload(auth_type: str, password: str, ssh_key: str):
    if auth_type not in ("password", "ssh"):
        raise HTTPException(status_code=400, detail="认证方式仅支持 password 或 ssh")
    if auth_type == "password" and not password:
        raise HTTPException(status_code=400, detail="密码/Token 不能为空")
    if auth_type == "ssh" and not ssh_key:
        raise HTTPException(status_code=400, detail="SSH 私钥不能为空")


@router.get("", response_model=List[GitCredentialOut])
async def list_git_credentials(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """共享凭据列表（脱敏）；默认仅返回启用中的"""
    query = db.query(GitCredential)
    if not include_inactive:
        query = query.filter(GitCredential.is_active == True)  # noqa: E712
    return [_to_out(c) for c in query.order_by(GitCredential.created_at.desc()).all()]


@router.post("", response_model=GitCredentialOut, status_code=status.HTTP_201_CREATED)
async def create_git_credential(
    payload: GitCredentialCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """创建共享凭据（仅 admin）"""
    if db.query(GitCredential).filter(GitCredential.name == payload.name).first():
        raise HTTPException(status_code=400, detail="同名凭据已存在")

    _validate_payload(payload.auth_type, payload.password, payload.ssh_key)

    cred = GitCredential(
        name=payload.name,
        description=payload.description,
        auth_type=payload.auth_type,
        username=payload.username,
        password=encrypt_text(payload.password),
        ssh_key=encrypt_text(payload.ssh_key),
        passphrase=encrypt_text(payload.passphrase),
        default_branch=payload.default_branch,
        is_active=payload.is_active,
        created_by=admin.id,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return _to_out(cred)


@router.put("/{cred_id}", response_model=GitCredentialOut)
async def update_git_credential(
    cred_id: int,
    payload: GitCredentialUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """更新共享凭据（仅 admin）；秘密字段留空表示保留原值"""
    cred = db.query(GitCredential).filter(GitCredential.id == cred_id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="凭据不存在")

    data = payload.dict(exclude_unset=True)

    if "name" in data and data["name"] != cred.name:
        if db.query(GitCredential).filter(GitCredential.name == data["name"]).first():
            raise HTTPException(status_code=400, detail="同名凭据已存在")

    new_auth_type = data.get("auth_type") or cred.auth_type
    _validate_payload(
        new_auth_type,
        data.get("password") or ("x" if cred.password else ""),
        data.get("ssh_key") or ("x" if cred.ssh_key else ""),
    )

    for key in ("name", "description", "auth_type", "username", "default_branch", "is_active"):
        if key in data:
            setattr(cred, key, data[key])
    # 秘密字段：仅在显式提供非空值时更新
    if data.get("password"):
        cred.password = encrypt_text(data["password"])
    if data.get("ssh_key"):
        cred.ssh_key = encrypt_text(data["ssh_key"])
    if data.get("passphrase"):
        cred.passphrase = encrypt_text(data["passphrase"])

    db.commit()
    db.refresh(cred)
    return _to_out(cred)


@router.delete("/{cred_id}")
async def delete_git_credential(
    cred_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """删除共享凭据（仅 admin）；被爬虫引用时拒绝删除"""
    cred = db.query(GitCredential).filter(GitCredential.id == cred_id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="凭据不存在")

    ref_count = db.query(Spider).filter(Spider.git_credential_id == cred_id).count()
    if ref_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"该凭据正被 {ref_count} 个爬虫引用，请先解除引用或改为停用",
        )

    db.delete(cred)
    db.commit()
    return {"message": "删除成功"}
