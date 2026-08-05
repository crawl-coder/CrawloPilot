# 认证与权限

## 职责

提供用户登录、注册、Token 管理与基于角色的权限控制（JWT + RBAC），
是所有 API 和前端页面的入口。

## 数据模型

- `user`：用户（username/email/password_hash/is_active）
- `role` / `permission` / `user_role` / `role_permission`：RBAC 四表
- `team` / `team_member`：团队（项目归属团队）

## 后端实现

### 认证接口（`backend/app/api/v1/auth.py`）

| 接口 | 说明 |
|------|------|
| `POST /auth/login` | 表单登录（OAuth2PasswordRequestForm），返回 JWT |
| `POST /auth/register` | 注册新用户 |
| `GET /auth/me` | 当前用户信息 |

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
- V1 未启用登录频率限制与审计中间件（已移除，V2 可恢复）
