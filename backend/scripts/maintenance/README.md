# maintenance/ 一次性维护脚本

> 本目录归档**早期的一次性数据修复/迁移脚本**，均已由正式迁移或代码覆盖，
> **仅供历史追溯与紧急恢复参考**，新环境无需运行。

## 脚本说明

| 脚本 | 用途 | 现状 |
|------|------|------|
| `migrate_node_credentials.py` | 将存量明文 `ssh_pwd`/`ssh_key` 加密为 Fernet 密文 | 已被 `node_service.create_node` 自动加密覆盖，幂等 |
| `add_missing_columns.py` | 手动补齐缺失的 DB 列（spider_id 等） | 已被 alembic 迁移覆盖 |
| `_fix_db.py` | 全库明文凭据脱敏 | 已被凭据加密链路覆盖 |
| `add_sample_data.py` | 注入示例数据 | 仅开发用 |

## 运行注意

- 脚本内含硬编码路径（`sys.path.insert`），运行前需按当前项目路径调整。
- 均幂等设计，重复执行安全；但建议先在测试库验证。
