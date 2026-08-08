#!/usr/bin/env python3
"""
迁移节点 SSH 凭据：将存量明文 ssh_pwd/ssh_key 加密为 Fernet 密文。

幂等：已是密文（gAAAA 前缀）的跳过；重复执行安全。
密钥由 SECRET_KEY 派生，与 Git 凭据加密同源，更换 SECRET_KEY 会导致无法解密。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.core.crypto import encrypt_if_plain
from app.core.database import SessionLocal
from app.models import Node


def main() -> None:
    db = SessionLocal()
    try:
        nodes = db.query(Node).all()
        migrated_pwd = migrated_key = 0
        for n in nodes:
            if n.ssh_pwd and not str(n.ssh_pwd).startswith("gAAAA"):
                n.ssh_pwd = encrypt_if_plain(n.ssh_pwd)
                migrated_pwd += 1
            if n.ssh_key and not str(n.ssh_key).startswith("gAAAA"):
                n.ssh_key = encrypt_if_plain(n.ssh_key)
                migrated_key += 1
        db.commit()
        print(f"✅ 节点凭据迁移完成: 密码加密 {migrated_pwd} 条, 私钥加密 {migrated_key} 条")
    finally:
        db.close()


if __name__ == "__main__":
    main()
