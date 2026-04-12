"""
爬虫管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Spider, Project
from app.schemas.spider import SpiderCreate, SpiderUpdate, SpiderInDB
from app.services.upload_service import UploadService
import os

router = APIRouter(prefix="/spiders", tags=["爬虫管理"])


# ==================== 爬虫管理 ====================

@router.get("")
async def list_spiders(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取爬虫列表(带分页)"""
    query = db.query(Spider)
    
    if project_id:
        query = query.filter(Spider.project_id == project_id)
    if status:
        query = query.filter(Spider.status == status)
    
    # 获取总数
    total = query.count()
    
    # 获取分页数据
    spiders = query.offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "items": spiders,
        "skip": skip,
        "limit": limit
    }


@router.get("/{spider_id}", response_model=SpiderInDB)
async def get_spider(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取爬虫详情"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    return spider


@router.post("", response_model=SpiderInDB, status_code=status.HTTP_201_CREATED)
async def create_spider(
    spider_data: SpiderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建爬虫"""
    # 验证项目是否存在
    project = db.query(Project).filter(Project.id == spider_data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 检查爬虫名称是否重复
    existing = db.query(Spider).filter(
        Spider.project_id == spider_data.project_id,
        Spider.name == spider_data.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该项目下已存在同名爬虫")
    
    # 创建爬虫
    new_spider = Spider(
        **spider_data.dict(),
        status="draft"
    )
    
    db.add(new_spider)
    db.commit()
    db.refresh(new_spider)
    
    return new_spider


@router.put("/{spider_id}", response_model=SpiderInDB)
async def update_spider(
    spider_id: int,
    spider_data: SpiderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新爬虫"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    # 更新字段
    update_data = spider_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(spider, key, value)
    
    db.commit()
    db.refresh(spider)
    
    return spider


@router.delete("/{spider_id}")
async def delete_spider(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除爬虫"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    db.delete(spider)
    db.commit()
    
    return {"message": "删除成功"}


# ==================== 爬虫运行控制 ====================

@router.post("/{spider_id}/run")
async def run_spider(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """运行爬虫"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    if spider.status == "disabled":
        raise HTTPException(status_code=400, detail="爬虫已禁用，无法运行")
    
    # TODO: 实际运行逻辑
    return {"message": "爬虫运行指令已发送", "spider_id": spider_id}


@router.post("/{spider_id}/stop")
async def stop_spider(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """停止爬虫"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    # TODO: 实际停止逻辑
    return {"message": "爬虫停止指令已发送", "spider_id": spider_id}


# ==================== 爬虫代码管理 ====================

@router.get("/{spider_id}/files/tree")
async def get_spider_file_tree(
    spider_id: int,
    path: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取爬虫文件树"""
    from app.services.file_service import FileService
    
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    # 获取爬虫代码目录
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    if not spider_code_dir or not os.path.exists(spider_code_dir):
        return {"error": "爬虫代码目录不存在，请先上传代码"}
    
    try:
        file_service = FileService(spider_code_dir)
        tree = file_service.get_file_tree(path, max_depth=3)
        return tree
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{spider_id}/files/content")
async def get_spider_file_content(
    spider_id: int,
    path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取爬虫文件内容"""
    from app.services.file_service import FileService
    
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    if not spider_code_dir:
        raise HTTPException(status_code=400, detail="爬虫代码目录不存在")
    
    file_service = FileService(spider_code_dir)
    result = file_service.read_file(path)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/{spider_id}/files/content")
async def save_spider_file_content(
    spider_id: int,
    path: str,
    content: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保存爬虫文件内容"""
    from app.services.file_service import FileService
    
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    if not spider_code_dir:
        raise HTTPException(status_code=400, detail="爬虫代码目录不存在")
    
    file_service = FileService(spider_code_dir)
    result = file_service.write_file(path, content)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/{spider_id}/files/create")
async def create_spider_file(
    spider_id: int,
    path: str,
    is_directory: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建爬虫文件或目录"""
    from app.services.file_service import FileService
    
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    if not spider_code_dir:
        raise HTTPException(status_code=400, detail="爬虫代码目录不存在")
    
    file_service = FileService(spider_code_dir)
    result = file_service.create_file(path, is_directory)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.delete("/{spider_id}/files")
async def delete_spider_file(
    spider_id: int,
    path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除爬虫文件或目录"""
    from app.services.file_service import FileService
    
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    if not spider_code_dir:
        raise HTTPException(status_code=400, detail="爬虫代码目录不存在")
    
    file_service = FileService(spider_code_dir)
    result = file_service.delete_file(path)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result
