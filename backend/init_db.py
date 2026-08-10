"""
数据库初始化脚本 - 用于开发环境
创建默认管理员账号和初始数据
"""
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.core.security import get_password_hash
from app.models import User, Team, Role, Permission, UserRole
from datetime import datetime
from app.core.time_utils import cn_now


def init_admin_user(db: Session):
    """创建默认管理员账号"""
    # 检查是否已存在 admin 用户
    existing_user = db.query(User).filter(User.username == "admin").first()
    if existing_user:
        print("  ⚠️  管理员账号已存在，跳过创建")
        return existing_user
    
    # 创建管理员用户
    admin_user = User(
        username="admin",
        email="admin@crawlopilot.com",
        password_hash=get_password_hash("admin123"),
        full_name="系统管理员",
        is_active=True,
        created_at=cn_now()
    )
    
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    
    print("  ✓ 创建管理员账号: admin / admin123")
    return admin_user


def init_default_team(db: Session):
    """创建默认团队"""
    existing_team = db.query(Team).filter(Team.name == "默认团队").first()
    if existing_team:
        print("  ⚠️  默认团队已存在，跳过创建")
        return existing_team
    
    team = Team(
        name="默认团队",
        description="系统默认团队",
        created_at=cn_now()
    )
    
    db.add(team)
    db.commit()
    db.refresh(team)
    
    print("  ✓ 创建默认团队")
    return team


def init_roles_and_permissions(db: Session):
    """初始化角色和权限"""
    # 检查是否已有权限数据
    existing_permissions = db.query(Permission).first()
    if existing_permissions:
        print("  ⚠️  权限数据已存在，跳过创建")
        return
    
    # 定义权限
    permissions_data = [
        # 用户管理
        {"code": "user:read", "name": "查看用户", "description": "查看用户列表和详情"},
        {"code": "user:create", "name": "创建用户", "description": "创建新用户"},
        {"code": "user:update", "name": "更新用户", "description": "修改用户信息"},
        {"code": "user:delete", "name": "删除用户", "description": "删除用户"},
        
        # 项目管理
        {"code": "project:read", "name": "查看项目", "description": "查看项目列表和详情"},
        {"code": "project:create", "name": "创建项目", "description": "创建新项目"},
        {"code": "project:update", "name": "更新项目", "description": "修改项目信息"},
        {"code": "project:delete", "name": "删除项目", "description": "删除项目"},
        
        # 部署管理
        {"code": "deploy:read", "name": "查看部署", "description": "查看部署状态"},
        {"code": "deploy:create", "name": "创建部署", "description": "部署项目"},
        {"code": "deploy:cancel", "name": "取消部署", "description": "取消正在进行的部署"},
        
        # 调度管理
        {"code": "schedule:read", "name": "查看调度", "description": "查看调度配置"},
        {"code": "schedule:create", "name": "创建调度", "description": "创建调度任务"},
        {"code": "schedule:update", "name": "更新调度", "description": "修改调度配置"},
        {"code": "schedule:delete", "name": "删除调度", "description": "删除调度任务"},
        
        # 监控告警
        {"code": "monitor:read", "name": "查看监控", "description": "查看监控数据"},
        {"code": "alert:read", "name": "查看告警", "description": "查看告警记录"},
        {"code": "alert:config", "name": "配置告警", "description": "配置告警规则"},
    ]
    
    # 创建权限
    permissions = []
    for perm_data in permissions_data:
        perm = Permission(**perm_data)
        db.add(perm)
        permissions.append(perm)
    
    db.commit()
    
    # 创建管理员角色
    admin_role = Role(
        name="admin",
        description="系统管理员",
        created_at=cn_now()
    )
    admin_role.permissions = permissions
    
    db.add(admin_role)
    
    # 创建普通用户角色
    user_role = Role(
        name="user",
        description="普通用户",
        created_at=cn_now()
    )
    # 普通用户只有读取和创建权限
    user_role.permissions = [p for p in permissions if ":read" in p.code or ":create" in p.code]
    
    db.add(user_role)
    db.commit()
    
    print(f"  ✓ 创建 {len(permissions_data)} 个权限")
    print("  ✓ 创建角色: admin, user")


def assign_admin_role(db: Session, admin_user: User):
    """给管理员用户分配管理员角色"""
    # 检查是否已分配
    existing_role = db.query(UserRole).filter(
        UserRole.user_id == admin_user.id
    ).first()
    
    if existing_role:
        print("  ⚠️  管理员角色已分配，跳过")
        return
    
    # 获取管理员角色
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if not admin_role:
        print("  ⚠️  管理员角色不存在")
        return
    
    # 分配角色
    user_role = UserRole(
        user_id=admin_user.id,
        role_id=admin_role.id
    )
    
    db.add(user_role)
    db.commit()
    
    print("  ✓ 为 admin 用户分配管理员角色")


def init_database():
    """初始化数据库"""
    print("\n" + "="*50)
    print("  CrawloPilot 数据库初始化")
    print("="*50 + "\n")
    
    db = SessionLocal()
    
    try:
        # 1. 创建默认团队
        print("[1/4] 初始化默认团队...")
        init_default_team(db)
        
        # 2. 创建角色和权限
        print("\n[2/4] 初始化角色和权限...")
        init_roles_and_permissions(db)
        
        # 3. 创建管理员账号
        print("\n[3/4] 创建管理员账号...")
        admin_user = init_admin_user(db)
        
        # 4. 分配管理员角色
        print("\n[4/4] 分配管理员角色...")
        if admin_user:
            assign_admin_role(db, admin_user)
        
        print("\n" + "="*50)
        print("  ✓ 数据库初始化完成！")
        print("="*50)
        print("\n默认管理员账号:")
        print("  用户名: admin")
        print("  密码: admin123")
        print("  邮箱: admin@crawlopilot.com")
        print("\n")
        
    except Exception as e:
        print(f"\n✗ 初始化失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
