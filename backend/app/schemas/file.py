"""
项目文件管理 Pydantic Schemas
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class FileInfo(BaseModel):
    """文件信息"""
    name: str
    path: str
    type: str  # file 或 directory
    size: Optional[int] = None
    extension: Optional[str] = None
    modified_at: Optional[str] = None
    is_binary: bool = False


class FileTreeItem(BaseModel):
    """文件树节点"""
    name: str
    path: str
    type: str  # file 或 directory
    children: Optional[List['FileTreeItem']] = None
    size: Optional[int] = None
    extension: Optional[str] = None


class FileContent(BaseModel):
    """文件内容"""
    path: str
    content: str
    encoding: str = "utf-8"
    size: int
    is_binary: bool = False


class FileOperationResponse(BaseModel):
    """文件操作响应"""
    success: bool
    message: str
    data: Optional[dict] = None
