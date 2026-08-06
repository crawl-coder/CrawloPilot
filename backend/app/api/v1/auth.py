import hashlib
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
import redis
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models import User
from app.schemas.user import UserCreate, UserInDB, Token, GitCredentialPayload, GitCredentialInfo

router = APIRouter(prefix="/auth", tags=["authentication"])

logger = logging.getLogger(__name__)


def _get_client_ip(request: Request) -> str:
    """从请求中提取客户端IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_redis_client():
    """获取Redis客户端（用于登录保护）"""
    try:
        return redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    except Exception:
        return None


def _check_login_attempts(username: str, ip: str) -> bool:
    """
    检查登录尝试是否触发限制（临时IP封禁）
    5分钟内连续失败5次则封禁15分钟
    """
    r = _get_redis_client()
    if r is None:
        return True  # Redis不可用时放行

    key = f"login_fail:{hashlib.md5(f'{ip}:{username}'.encode()).hexdigest()}"
    banned_key = f"login_banned:{ip}"

    # 检查是否被封禁
    if r.exists(banned_key):
        ttl = r.ttl(banned_key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录尝试过于频繁，请在 {ttl} 秒后重试",
        )

    return True


def _record_login_failure(username: str, ip: str):
    """记录登录失败并检查是否触发封禁"""
    r = _get_redis_client()
    if r is None:
        return

    key = f"login_fail:{hashlib.md5(f'{ip}:{username}'.encode()).hexdigest()}"
    banned_key = f"login_banned:{ip}"

    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 300)  # 5分钟过期
    result = pipe.execute()

    attempt_count = result[0]
    if attempt_count >= 5:
        logger.warning(f"Login rate limit triggered for IP={ip}, username={username}")
        # 封禁IP 15分钟
        r.setex(banned_key, 900, "1")


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    ip = _get_client_ip(request)
    # 登录频率限制已注释 — 如需启用请取消注释下两行
    # _check_login_attempts(form_data.username, ip)

    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        # _record_login_failure(form_data.username, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )

    logger.info(f"User {user.username} logged in from IP {ip}")
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=UserInDB)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    # Check if user exists
    existing_user = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        password_hash=get_password_hash(user_data.password)
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.get("/me", response_model=UserInDB)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    return current_user


# ==================== 个人 Git 凭据 ====================

@router.get("/me/git-credentials", response_model=GitCredentialInfo)
def get_my_git_credentials(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的个人 Git 凭据（脱敏，不回传秘密本体）"""
    from app.services.credential_service import mask_user_credentials

    masked = mask_user_credentials(current_user)
    if masked is None:
        return GitCredentialInfo(configured=False)
    return GitCredentialInfo(configured=True, **masked)


@router.put("/me/git-credentials", response_model=GitCredentialInfo)
def save_my_git_credentials(
    payload: GitCredentialPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    保存/更新当前用户的个人 Git 凭据（加密落库）
    秘密字段（password/ssh_key/passphrase）留空表示保留原值
    """
    from app.services.credential_service import (
        pack_user_credentials, unpack_user_credentials, mask_user_credentials,
    )

    if payload.auth_type not in ("password", "ssh"):
        raise HTTPException(status_code=400, detail="认证方式仅支持 password 或 ssh")

    existing = unpack_user_credentials(current_user) or {}

    new_password = payload.password if payload.password else existing.get("password")
    new_ssh_key = payload.ssh_key if payload.ssh_key else existing.get("ssh_key")
    if payload.auth_type == "password" and not new_password:
        raise HTTPException(status_code=400, detail="密码/Token 不能为空")
    if payload.auth_type == "ssh" and not new_ssh_key:
        raise HTTPException(status_code=400, detail="SSH 私钥不能为空")

    current_user.git_credentials = pack_user_credentials({
        "auth_type": payload.auth_type,
        "username": payload.username if payload.username is not None else existing.get("username"),
        "password": new_password,
        "ssh_key": new_ssh_key,
        "passphrase": payload.passphrase if payload.passphrase else existing.get("passphrase"),
        "default_branch": payload.default_branch if payload.default_branch is not None else existing.get("default_branch"),
    })
    db.commit()

    masked = mask_user_credentials(current_user)
    return GitCredentialInfo(configured=True, **masked)


@router.delete("/me/git-credentials")
def delete_my_git_credentials(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清除当前用户的个人 Git 凭据"""
    current_user.git_credentials = None
    db.commit()
    return {"message": "已清除个人 Git 凭据"}
