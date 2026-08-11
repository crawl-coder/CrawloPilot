"""
Server（真实服务器）API 路由
"""

from typing import Optional, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.services.server_service import ServerService

router = APIRouter(prefix="/servers", tags=["服务器"])


# ==================== Schemas ====================

class ServerCreate(BaseModel):
    name: str
    host: str
    region: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    description: Optional[str] = None


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    description: Optional[str] = None


class ServerChannelCreate(BaseModel):
    """在服务器下创建执行通道（复用节点字段）"""

    name: str
    connect_type: str = "ssh"  # ssh / docker / agent
    port: Optional[int] = None
    ssh_user: Optional[str] = "root"
    ssh_pwd: Optional[str] = None
    ssh_key: Optional[str] = None
    docker_host: Optional[str] = None


class AgentBatchDeployRequest(BaseModel):
    """批量部署 Agent 请求"""

    server_ids: List[int]
    server_url: str


# ==================== API ====================

@router.post("/batch-deploy-agent")
async def batch_deploy_agent(
    data: AgentBatchDeployRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量一键部署 Agent（复用各服务器 SSH 通道，逐台报告结果）"""
    from app.services.agent_deploy_service import batch_deploy_agents

    server_url = data.server_url.strip().rstrip("/")
    if not server_url:
        raise HTTPException(status_code=422, detail="缺少管理服务器地址 server_url")
    results = batch_deploy_agents(db, data.server_ids, server_url)
    return {"results": results}


@router.post("")
async def create_server(
    data: ServerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建服务器（创建后自动探测）"""
    try:
        service = ServerService(db)
        server = service.create_server(
            name=data.name,
            host=data.host,
            region=data.region,
            labels=data.labels,
            description=data.description,
        )
        probe = service.probe_server(server.id)
        return {**service.serialize_server(server), "probe": probe}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_servers(
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """服务器列表（分页 + 关键字 + 状态筛选）"""
    from app.core.pagination import clamp_pagination
    skip, limit = clamp_pagination(skip, limit, default_limit=20)
    service = ServerService(db)
    servers, total = service.get_servers(
        status=status,
        keyword=keyword,
        skip=skip,
        limit=limit,
    )
    return {
        "total": total,
        "items": [service.serialize_server(s) for s in servers],
        "skip": skip,
        "limit": limit,
    }


@router.get("/{server_id}")
async def get_server(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """服务器详情"""
    service = ServerService(db)
    server = service.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    return service.serialize_server(server)


@router.put("/{server_id}")
async def update_server(
    server_id: int,
    data: ServerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新服务器基本信息"""
    try:
        service = ServerService(db)
        server = service.update_server(
            server_id,
            name=data.name,
            region=data.region,
            labels=data.labels,
            description=data.description,
        )
        if not server:
            raise HTTPException(status_code=404, detail="服务器不存在")
        return service.serialize_server(server)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{server_id}")
async def delete_server(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除服务器（无在线通道时）"""
    try:
        service = ServerService(db)
        if not service.delete_server(server_id):
            raise HTTPException(status_code=404, detail="服务器不存在")
        return {"message": "服务器已删除", "id": server_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{server_id}/probe")
async def probe_server(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新探测服务器"""
    try:
        service = ServerService(db)
        return service.probe_server(server_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{server_id}/maintenance")
async def enter_maintenance(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """服务器进入维护（先排空 Docker 通道）"""
    service = ServerService(db)
    if not service.enter_maintenance(server_id):
        raise HTTPException(status_code=404, detail="服务器不存在")
    return {"message": "服务器已进入维护模式", "id": server_id}


@router.post("/{server_id}/recover")
async def exit_maintenance(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """服务器退出维护（重新探测通道并聚合状态）"""
    service = ServerService(db)
    if not service.exit_maintenance(server_id):
        raise HTTPException(status_code=404, detail="服务器不存在")
    return {"message": "服务器已退出维护模式", "id": server_id}


@router.get("/{server_id}/nodes")
async def list_server_nodes(
    server_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """服务器下的执行通道列表"""
    service = ServerService(db)
    if not service.get_server(server_id):
        raise HTTPException(status_code=404, detail="服务器不存在")
    nodes = service.get_server_nodes(server_id)
    return [
        {
            "id": n.id,
            "name": n.name,
            "connect_type": n.connect_type,
            "status": n.status.value if hasattr(n.status, "value") else n.status,
            "host": n.host,
            "port": n.port,
            "os_type": n.os_type,
            "cpu_cores": n.cpu_cores,
            "memory_total": n.memory_total,
            "cpu_usage": float(n.cpu_usage) if n.cpu_usage is not None else 0,
            "memory_usage": float(n.memory_usage) if n.memory_usage is not None else 0,
            "agent_version": n.agent_version,
            "agent_status": n.agent_status,
            "last_heartbeat": n.last_heartbeat,
        }
        for n in nodes
    ]


@router.post("/{server_id}/nodes")
async def create_server_node(
    server_id: int,
    data: ServerChannelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """在服务器下创建执行通道"""
    service = ServerService(db)
    server = service.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")

    from app.services.node_service import NodeService
    try:
        node_service = NodeService(db)
        node = node_service.create_node(
            name=data.name,
            host=server.host,
            port=data.port or (22 if data.connect_type == "ssh" else 2375),
            connect_type=data.connect_type,
            ssh_host=server.host,
            ssh_port=data.port or 22,
            ssh_user=data.ssh_user or "root",
            ssh_pwd=data.ssh_pwd,
            ssh_key=data.ssh_key,
            docker_host=data.docker_host,
        )
        node.server_id = server_id
        db.commit()
        db.refresh(node)

        service.aggregate_server_status(server)
        return {
            "id": node.id,
            "name": node.name,
            "connect_type": node.connect_type,
            "server_id": server_id,
            "agent_token": node.agent_token,
            "status": node.status.value if hasattr(node.status, "value") else node.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
