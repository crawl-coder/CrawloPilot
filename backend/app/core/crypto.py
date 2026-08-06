"""
对称加密工具（Fernet）

用于敏感凭据（Git 密码/Token、SSH 私钥）的落库加密。
密钥由 SECRET_KEY 派生（SHA-256 → urlsafe base64），无需额外配置。

注意：更换 SECRET_KEY 会导致历史密文无法解密，生产环境请勿轮换。
"""
import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
        _fernet = Fernet(key)
    return _fernet


def encrypt_text(plain: Optional[str]) -> Optional[str]:
    """加密文本；None/空串原样返回"""
    if not plain:
        return plain
    return _get_fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_text(token: Optional[str]) -> Optional[str]:
    """解密文本；None/空串原样返回。密文损坏时返回 None 并记日志（不抛异常）"""
    if not token:
        return token
    try:
        return _get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as e:
        logger.error(f"凭据解密失败（密钥可能已更换）: {e}")
        return None
