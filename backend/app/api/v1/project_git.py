"""
项目 Git 操作和文件上传 API
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Project
from app.services.git_service import GitService
from app.services.upload_service import UploadService
from pydantic import BaseModel

router = APIRouter(prefix="/projects", tags=["projects-git-upload"])


# ==================== Pydantic Schemas ====================

class GitCloneRequest(BaseModel):
    """Git 克隆请求"""
    git_url: str
    branch: Optional[str] = None
    # 密码/Token认证
    username: Optional[str] = None
    password: Optional[str] = None
    # SSH认证
    auth_type: str = "password"  # password 或 ssh
    ssh_key: Optional[str] = None  # SSH私钥内容
    passphrase: Optional[str] = None  # SSH私钥密码


class GitPullRequest(BaseModel):
    """Git 拉取请求"""
    remote: str = "origin"
    branch: Optional[str] = None
    # 密码/Token认证
    username: Optional[str] = None
    password: Optional[str] = None
    # SSH认证
    auth_type: str = "password"
    ssh_key: Optional[str] = None
    passphrase: Optional[str] = None


class GitPushRequest(BaseModel):
    """Git 推送请求"""
    remote: str = "origin"
    branch: Optional[str] = None
    # 密码/Token认证
    username: Optional[str] = None
    password: Optional[str] = None
    # SSH认证
    auth_type: str = "password"
    ssh_key: Optional[str] = None
    passphrase: Optional[str] = None


class GitBranchRequest(BaseModel):
    """Git 分支操作请求"""
    action: str  # create, checkout
    branch_name: str
    start_point: Optional[str] = "HEAD"


class GitCommitRequest(BaseModel):
    """Git 提交请求"""
    message: str
    files: Optional[List[str]] = None


class GitTagRequest(BaseModel):
    """Git 标签请求"""
    action: str  # create
    tag_name: str
    message: Optional[str] = ""


# ==================== Git Operations ====================

@router.post("/{project_id}/git/clone")
def git_clone(
    project_id: int,
    request: GitCloneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """克隆 Git 仓库"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 获取项目代码目录
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        # 创建新的代码目录
        project_code_dir = os.path.join("uploads", f"project_{project_id}", "code")
    
    try:
        git_service = GitService(project_code_dir)
        result = git_service.clone_repository(
            url=request.git_url,
            branch=request.branch,
            username=request.username,
            password=request.password,
            auth_type=request.auth_type,
            ssh_key=request.ssh_key,
            passphrase=request.passphrase
        )
        
        # 更新项目的 git_url
        project.git_url = request.git_url
        db.commit()
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/git/pull")
def git_pull(
    project_id: int,
    request: GitPullRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """拉取远程更新"""
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir or not os.path.exists(os.path.join(project_code_dir, '.git')):
        raise HTTPException(status_code=400, detail="项目未初始化 Git 仓库")
    
    try:
        git_service = GitService(project_code_dir)
        result = git_service.pull(
            remote=request.remote,
            branch=request.branch
        )
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/git/push")
def git_push(
    project_id: int,
    request: GitPushRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """推送到远程仓库"""
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    try:
        git_service = GitService(project_code_dir)
        result = git_service.push(
            remote=request.remote,
            branch=request.branch,
            username=request.username,
            password=request.password,
            auth_type=request.auth_type,
            ssh_key=request.ssh_key,
            passphrase=request.passphrase
        )
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/git/branches")
def git_get_branches(
    project_id: int,
    remote: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取分支列表"""
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    try:
        git_service = GitService(project_code_dir)
        branches = git_service.get_branches(remote=remote)
        
        return {
            "success": True,
            "data": branches
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/git/branch")
def git_branch_operation(
    project_id: int,
    request: GitBranchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建或切换分支"""
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    try:
        git_service = GitService(project_code_dir)
        
        if request.action == "create":
            result = git_service.create_branch(
                branch_name=request.branch_name,
                start_point=request.start_point
            )
        elif request.action == "checkout":
            result = git_service.checkout_branch(request.branch_name)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的操作: {request.action}")
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/git/commits")
def git_get_commits(
    project_id: int,
    max_count: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取提交历史"""
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    try:
        git_service = GitService(project_code_dir)
        commits = git_service.get_commit_history(max_count=max_count)
        
        return {
            "success": True,
            "data": commits
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/git/tags")
def git_get_tags(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取标签列表"""
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    try:
        git_service = GitService(project_code_dir)
        tags = git_service.get_tags()
        
        return {
            "success": True,
            "data": tags
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/git/tag")
def git_tag_operation(
    project_id: int,
    request: GitTagRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建标签"""
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    if request.action != "create":
        raise HTTPException(status_code=400, detail="仅支持创建标签操作")
    
    try:
        git_service = GitService(project_code_dir)
        result = git_service.create_tag(
            tag_name=request.tag_name,
            message=request.message
        )
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/git/status")
def git_get_status(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取仓库状态"""
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    try:
        git_service = GitService(project_code_dir)
        status_data = git_service.get_status()
        
        return {
            "success": True,
            "data": status_data
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/git/commit")
def git_commit(
    project_id: int,
    request: GitCommitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """提交更改"""
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    try:
        git_service = GitService(project_code_dir)
        
        # 添加文件
        if request.files:
            git_service.add_files(request.files)
        else:
            git_service.add_files()
        
        # 提交
        result = git_service.commit(request.message)
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== File Upload Operations ====================

@router.post("/{project_id}/upload")
async def upload_code_package(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传代码包"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        upload_service = UploadService()
        result = await upload_service.upload_code_package(file, project_id)
        
        return {
            "success": True,
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/{project_id}/uploads")
def list_uploaded_files(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """列出上传的文件"""
    try:
        upload_service = UploadService()
        files = upload_service.list_uploaded_files(project_id)
        
        return {
            "success": True,
            "data": files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}/uploads/{filename}")
def delete_uploaded_file(
    project_id: int,
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除上传的文件"""
    try:
        upload_service = UploadService()
        success = upload_service.delete_uploaded_file(project_id, filename)
        
        if not success:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        return {
            "success": True,
            "message": "删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
