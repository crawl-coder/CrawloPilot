"""
爬虫 Git 管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Spider
from app.services.git_service import GitService
from app.services.upload_service import UploadService
from pydantic import BaseModel

router = APIRouter(prefix="/spiders", tags=["spider-git"])


# ==================== Pydantic Schemas ====================

class GitCloneRequest(BaseModel):
    """Git克隆请求"""
    url: str
    username: Optional[str] = None
    password: Optional[str] = None
    branch: str = "main"
    auth_type: str = "password"
    ssh_key: Optional[str] = None
    passphrase: Optional[str] = None


class GitPullRequest(BaseModel):
    """Git拉取请求"""
    username: Optional[str] = None
    password: Optional[str] = None
    auth_type: str = "password"
    ssh_key: Optional[str] = None
    passphrase: Optional[str] = None


class GitPushRequest(BaseModel):
    """Git推送请求"""
    username: Optional[str] = None
    password: Optional[str] = None
    auth_type: str = "password"
    ssh_key: Optional[str] = None
    passphrase: Optional[str] = None


class GitBranchRequest(BaseModel):
    """Git分支操作请求"""
    branch_name: str
    create: bool = False
    checkout: bool = False


# ==================== API Endpoints ====================

@router.post("/{spider_id}/git/clone")
async def git_clone(
    spider_id: int,
    request: GitCloneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """克隆Git仓库到爬虫"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    git_service = GitService(spider_code_dir)
    
    result = git_service.clone_repository(
        url=request.url,
        branch=request.branch,
        username=request.username,
        password=request.password,
        auth_type=request.auth_type,
        ssh_key=request.ssh_key,
        passphrase=request.passphrase
    )
    
    # 更新爬虫的Git配置
    spider.git_url = request.url
    spider.git_auth_type = request.auth_type
    spider.git_username = request.username
    spider.git_branch = request.branch
    
    db.commit()
    
    return result


@router.post("/{spider_id}/git/pull")
async def git_pull(
    spider_id: int,
    request: Optional[GitPullRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """拉取最新代码"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    if not spider.git_url:
        raise HTTPException(status_code=400, detail="未配置Git仓库")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    git_service = GitService(spider_code_dir)
    
    # 使用爬虫保存的Git配置
    result = git_service.pull(
        username=request.username if request else spider.git_username,
        password=request.password if request else spider.git_password,
        auth_type=request.auth_type if request else spider.git_auth_type,
        ssh_key=request.ssh_key if request else spider.git_ssh_key,
        passphrase=request.passphrase if request else spider.git_passphrase
    )
    
    return result


@router.post("/{spider_id}/git/push")
async def git_push(
    spider_id: int,
    request: Optional[GitPushRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """推送代码到远程仓库"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    if not spider.git_url:
        raise HTTPException(status_code=400, detail="未配置Git仓库")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    git_service = GitService(spider_code_dir)
    
    result = git_service.push(
        username=request.username if request else spider.git_username,
        password=request.password if request else spider.git_password,
        auth_type=request.auth_type if request else spider.git_auth_type,
        ssh_key=request.ssh_key if request else spider.git_ssh_key,
        passphrase=request.passphrase if request else spider.git_passphrase
    )
    
    return result


@router.get("/{spider_id}/git/branches")
async def git_get_branches(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取分支列表"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    git_service = GitService(spider_code_dir)
    return git_service.get_branches()


@router.post("/{spider_id}/git/branch")
async def git_branch_operation(
    spider_id: int,
    request: GitBranchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """分支操作（创建/切换）"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    git_service = GitService(spider_code_dir)
    
    if request.create:
        result = git_service.create_branch(request.branch_name)
    elif request.checkout:
        result = git_service.checkout_branch(request.branch_name)
        # 更新爬虫的分支配置
        spider.git_branch = request.branch_name
        db.commit()
    else:
        raise HTTPException(status_code=400, detail="需要指定create或checkout")
    
    return result


@router.get("/{spider_id}/git/commits")
async def git_get_commits(
    spider_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取提交历史"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    git_service = GitService(spider_code_dir)
    return git_service.get_commit_history(limit)


@router.get("/{spider_id}/git/status")
async def git_get_status(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取仓库状态"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    git_service = GitService(spider_code_dir)
    return git_service.get_status()
