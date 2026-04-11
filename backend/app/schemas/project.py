from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class ProjectStatusEnum(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    git_url: Optional[str] = None


class ProjectCreate(ProjectBase):
    team_id: int


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    git_url: Optional[str] = None
    status: Optional[ProjectStatusEnum] = None


class ProjectInDB(ProjectBase):
    id: int
    team_id: int
    status: ProjectStatusEnum
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProjectVersionStatusEnum(str, Enum):
    BUILDING = "building"
    READY = "ready"
    DEPLOYED = "deployed"


class ProjectVersionBase(BaseModel):
    version: str


class ProjectVersionCreate(ProjectVersionBase):
    config_snapshot: Optional[dict] = None


class ProjectVersionInDB(ProjectVersionBase):
    id: int
    project_id: int
    package_url: Optional[str] = None
    config_snapshot: Optional[dict] = None
    image_tag: Optional[str] = None
    status: ProjectVersionStatusEnum
    created_at: datetime
    
    class Config:
        from_attributes = True
