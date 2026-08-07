"""
爬虫管理 Pydantic Schemas
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class SpiderType(str, Enum):
    CRAWLO = "crawlo"              # Crawlo 框架(主打)
    SCRAPY = "scrapy"              # Scrapy 框架
    SELENIUM = "selenium"          # Selenium
    PLAYWRIGHT = "playwright"      # Playwright
    REQUESTS = "requests"          # Requests
    CUSTOM = "custom"              # 自定义


class SpiderStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class SpiderBase(BaseModel):
    """爬虫基础信息"""
    name: str
    project_id: int
    description: Optional[str] = None
    spider_type: SpiderType = SpiderType.CRAWLO
    entry_file: Optional[str] = None  # 入口文件 (如 run.py)
    spider_name: Optional[str] = None  # 爬虫名称 (用于 crawlo run)
    config: Optional[Dict[str, Any]] = None  # 运行配置 (超时/重试等)

    # Git相关
    git_url: Optional[str] = None
    git_auth_type: str = "password"
    git_username: Optional[str] = None
    git_password: Optional[str] = None
    git_ssh_key: Optional[str] = None
    git_passphrase: Optional[str] = None
    git_branch: str = "main"
    # 引用的共享 Git 凭据（团队机器人凭据）ID
    git_credential_id: Optional[int] = None


class SpiderCreate(SpiderBase):
    """创建爬虫"""
    # True 时忽略内联 git 凭据字段，使用当前用户的个人 Git 凭据
    use_my_git_credential: bool = False


class SpiderUpdate(BaseModel):
    """更新爬虫"""
    name: Optional[str] = None
    description: Optional[str] = None
    spider_type: Optional[SpiderType] = None
    status: Optional[SpiderStatus] = None
    entry_file: Optional[str] = None
    spider_name: Optional[str] = None  # 运行名称 (用于 crawlo run)
    config: Optional[Dict[str, Any]] = None
    git_credential_id: Optional[int] = None  # 更新引用的共享凭据（不传=不修改；显式传 null=清除引用）


class SpiderInDB(SpiderBase):
    """数据库中的爬虫"""
    id: int
    status: SpiderStatus
    code_path: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

    # 统计
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    run_count: int = 0
    success_count: int = 0
    error_count: int = 0
    
    # 部署节点信息
    deploy_nodes: List[Dict[str, Any]] = []
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
