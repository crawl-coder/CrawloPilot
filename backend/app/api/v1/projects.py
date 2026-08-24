from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.models import Project, ProjectVersion, ProjectStatus
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectInDB, ProjectVersionCreate, ProjectVersionInDB

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目列表(带分页，排除已删除项目)"""
    from app.core.pagination import clamp_pagination
    skip, limit = clamp_pagination(skip, limit, default_limit=20)
    query = db.query(Project).filter(Project.status != ProjectStatus.DELETED)
    total = query.count()
    projects = (
        query.order_by(Project.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "items": projects,
        "skip": skip,
        "limit": limit
    }


@router.post("", response_model=ProjectInDB, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_project = Project(**project_data.model_dump())
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    from app.services.audit_service import record_audit
    record_audit("POST", "/projects", user_id=current_user.id, username=current_user.username,
                 resource_type="project", resource_id=str(new_project.id), resource_name=new_project.name)
    return new_project


@router.get("/{project_id}", response_model=ProjectInDB)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project


@router.put("/{project_id}", response_model=ProjectInDB)
def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    update_data = project_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    project.status = ProjectStatus.DELETED
    db.commit()
    from app.services.audit_service import record_audit
    record_audit("DELETE", f"/projects/{project_id}", user_id=current_user.id, username=current_user.username,
                 resource_type="project", resource_id=str(project_id), resource_name=project.name)
    return {"message": "删除成功", "id": project_id}


@router.post("/{project_id}/versions", response_model=ProjectVersionInDB, status_code=status.HTTP_201_CREATED)
def create_project_version(
    project_id: int,
    version_data: ProjectVersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    new_version = ProjectVersion(
        project_id=project_id,
        version=version_data.version,
        config_snapshot=version_data.config_snapshot
    )
    
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return new_version


@router.get("/{project_id}/versions", response_model=List[ProjectVersionInDB])
def list_project_versions(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    versions = db.query(ProjectVersion).filter(
        ProjectVersion.project_id == project_id
    ).order_by(ProjectVersion.created_at.desc()).all()
    return versions
