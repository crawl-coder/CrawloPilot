# CrawloPilot 默认账号

## 🔐 开发环境默认账号

系统已预设默认管理员账号，用于开发和测试：

### 管理员账号

| 字段 | 值 |
|------|-----|
| **用户名** | `admin` |
| **密码** | `admin123` |
| **邮箱** | `admin@crawlopilot.com` |
| **角色** | 系统管理员 |
| **权限** | 所有权限 |

### 登录方式

1. 访问前端界面：http://localhost:3000
2. 输入用户名和密码
3. 点击登录

或直接使用 API：

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin" \
  -d "password=admin123"
```

---

## 📋 初始化说明

### 自动初始化

使用启动脚本时，系统会自动初始化数据库：

```bash
./start-dev.sh
```

启动流程：
1. ✓ 检查环境
2. ✓ 安装依赖
3. ✓ 运行数据库迁移
4. ✓ **创建默认管理员账号**
5. ✓ 启动后端服务
6. ✓ 启动前端服务

### 手动初始化

如果需要手动初始化或重新初始化：

```bash
cd backend
python init_db.py
```

这会：
- 创建默认管理员账号（如不存在）
- 创建默认团队
- 初始化角色和权限系统
- 为管理员分配所有权限

---

## 🔒 安全提醒

⚠️ **重要**：
- 默认账号仅供开发环境使用
- 生产环境部署前务必：
  1. 修改默认密码
  2. 或删除默认账号
  3. 或禁用自动初始化功能

---

## 👥 角色系统

系统预定义了两种角色：

### Admin（管理员）
- 所有权限
- 用户管理
- 项目管理
- 部署管理
- 调度管理
- 监控告警配置

### User（普通用户）
- 查看权限
- 创建权限
- 无删除权限

---

## 🛠️ 权限列表

系统初始化了 18 个权限：

**用户管理**
- user:read - 查看用户
- user:create - 创建用户
- user:update - 更新用户
- user:delete - 删除用户

**项目管理**
- project:read - 查看项目
- project:create - 创建项目
- project:update - 更新项目
- project:delete - 删除项目

**部署管理**
- deploy:read - 查看部署
- deploy:create - 创建部署
- deploy:cancel - 取消部署

**调度管理**
- schedule:read - 查看调度
- schedule:create - 创建调度
- schedule:update - 更新调度
- schedule:delete - 删除调度

**监控告警**
- monitor:read - 查看监控
- alert:read - 查看告警
- alert:config - 配置告警

---

## 📝 测试账号管理

### 查看当前用户

```bash
# 使用 admin 账号获取用户列表
curl http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer <token>"
```

### 创建测试用户

```bash
# 注册新用户
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "Test123!",
    "full_name": "测试用户"
  }'
```

---

## 🔧 修改默认账号

如需修改默认账号，编辑 `backend/init_db.py`：

```python
# 修改用户名和密码
admin_user = User(
    username="your_username",  # 修改这里
    email="admin@crawlopilot.com",
    password_hash=get_password_hash("your_password"),  # 修改这里
    ...
)
```

然后重新运行：

```bash
cd backend
python init_db.py
```

---

**最后更新**: 2026-04-11
