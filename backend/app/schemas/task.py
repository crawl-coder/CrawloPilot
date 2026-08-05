"""
任务相关 Schema
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime


class TaskCreate(BaseModel):
    """创建任务请求"""
    spider_id: str = Field(..., description="爬虫 ID")
    git_url: Optional[str] = Field(None, description="Git 仓库地址")
    git_branch: Optional[str] = Field("main", description="Git 分支")
    node_id: Optional[str] = Field(None, description="节点 ID")
    memory_limit: Optional[str] = Field("512m", description="内存限制")
    cpu_limit: Optional[float] = Field(1.0, description="CPU 限制")
    timeout: Optional[int] = Field(3600, description="超时时间(秒)")


class TaskResponse(BaseModel):
    """任务响应"""
    id: int
    spider_id: Optional[int] = None
    spider_name: str
    project_name: Optional[str] = None
    status: str
    schedule_id: Optional[int] = None
    worker_node: Optional[str] = None
    container_id: Optional[str] = None
    node_id: Optional[int] = None
    node_name: Optional[str] = None
    deploy_mode: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    db_status: str
    container_status: Optional[str] = None
    container_id: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    duration: Optional[float] = None


class TaskLogResponse(BaseModel):
    """任务日志响应"""
    task_id: str
    logs: str
    total_lines: int
