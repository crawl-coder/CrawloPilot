"""
项目文件管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Project
from app.services.file_service import FileService
from app.services.upload_service import UploadService
from app.schemas.file import FileInfo, FileTreeItem, FileContent, FileOperationResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/projects", tags=["project-files"])


# ==================== Pydantic Schemas ====================

class FileWriteRequest(BaseModel):
    """文件写入请求"""
    path: str
    content: str


class FileCreateRequest(BaseModel):
    """文件创建请求"""
    path: str
    is_directory: bool = False


class FileRenameRequest(BaseModel):
    """文件重命名请求"""
    old_path: str
    new_name: str


# ==================== API Endpoints ====================

@router.get("/{project_id}/files/tree", response_model=dict)
async def get_project_file_tree(
    project_id: int,
    path: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目文件树"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 获取项目代码目录
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        return {"error": "项目代码目录不存在，请先上传或克隆代码"}
    
    try:
        file_service = FileService(project_code_dir)
        tree = file_service.get_file_tree(path, max_depth=3)
        return tree
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/files/content")
async def get_file_content(
    project_id: int,
    path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取文件内容"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    file_service = FileService(project_code_dir)
    result = file_service.read_file(path)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/{project_id}/files/content")
async def save_file_content(
    project_id: int,
    request: FileWriteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保存文件内容"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    file_service = FileService(project_code_dir)
    result = file_service.write_file(request.path, request.content)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/{project_id}/files/create")
async def create_file_or_dir(
    project_id: int,
    request: FileCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建文件或目录"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    file_service = FileService(project_code_dir)
    result = file_service.create_file(request.path, request.is_directory)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.delete("/{project_id}/files")
async def delete_file_or_dir(
    project_id: int,
    path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除文件或目录"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    file_service = FileService(project_code_dir)
    result = file_service.delete_file(path)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.put("/{project_id}/files/rename")
async def rename_file_or_dir(
    project_id: int,
    request: FileRenameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """重命名文件或目录"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    upload_service = UploadService()
    project_code_dir = upload_service.get_project_code_dir(project_id)
    
    if not project_code_dir:
        raise HTTPException(status_code=400, detail="项目代码目录不存在")
    
    file_service = FileService(project_code_dir)
    result = file_service.rename_file(request.old_path, request.new_name)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result
