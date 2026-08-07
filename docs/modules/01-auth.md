# 认证与权限

## 职责

提供用户登录、注册、Token 管理与基于角色的权限控制（JWT + RBAC），
是所有 API 和前端页面的入口。

## 数据模型

- `user`：用户（username 唯一；email 可选可空；password_hash；is_active；git_credentials 为 Fernet 加密的个人 Git 凭据 JSON）
- `role` / `permission` / `user_role` / `role_permission`：RBAC 四表
- `team` / `team_member`：团队（项目归属团队）

## 后端实现

### 认证接口（`backend/app/api/v1/auth.py`）

| 接口 | 说明 |
|------|------|
| `POST /auth/login` | 表单登录（OAuth2PasswordRequestForm），返回 JWT；用户名支持手机号 |
| `POST /auth/register` | 注册新用户；受 `ALLOW_OPEN_REGISTER` 开关控制，关闭时仅 admin 可用（邮箱可选、姓名不在注册采集） |
| `GET /auth/me` | 当前用户信息 |
| `GET/PUT/DELETE /auth/me/git-credentials` | 个人 Git 凭据（Fernet 加密落库；查询脱敏；秘密字段留空=保留原值） |

> 用户管理接口（`/users/*`）仅 admin 可用（`require_admin`），见 `backend/app/api/v1/users.py`。

### 权限控制

- `backend/app/core/dependencies.py`：
  - `get_current_user`：解析 JWT → 校验用户 → 返回 User
  - `require_permission(code)`：校验用户角色是否含指定权限码
- 受保护接口统一 `Depends(get_current_user)`

### 团队接口（`backend/app/api/v1/teams.py`）

V1 精简版：仅提供 `GET /teams` 列表，供创建项目时选择团队。

## 前端实现

- `frontend/src/views/Login.vue`：登录页
- `frontend/src/api/auth.js`：登录/注册/当前用户
- `frontend/src/router/index.js`：路由守卫，无 Token 跳转登录页
- `frontend/src/api/request.js`：axios 拦截器自动携带 `Authorization: Bearer <token>`，
  401 时清理 Token 并跳转登录

## 默认账号

`admin / admin123`（`backend/init_db.py` 初始化，幂等）

## 安全说明

- 登录表单采用 OAuth2 表单协议（不是 JSON），客户端需以 `application/x-www-form-urlencoded` 提交
- 登录频率限制：V1 未启用（原 Redis 实现已随 Celery/Redis 依赖一同移除）；
  如需限流，建议在网关层（Nginx limit_req）或中间件实现
- 审计中间件已移除（V2 可恢复）
