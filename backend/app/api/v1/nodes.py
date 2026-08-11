"""
节点管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Node, NodeStatus
from app.services.node_service import NodeService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nodes", tags=["节点管理"])


# ==================== Pydantic Schemas ====================

class NodeCreate(BaseModel):
    """创建节点请求"""
    name: str
    host: str
    port: int = 22
    connect_type: str = "ssh"  # ssh / agent / docker
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = 22
    ssh_user: Optional[str] = "root"
    ssh_pwd: Optional[str] = None
    ssh_key: Optional[str] = None
    docker_host: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None


class NodeUpdate(BaseModel):
    """更新节点请求"""
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    connect_type: Optional[str] = None
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = None
    ssh_user: Optional[str] = None
    ssh_pwd: Optional[str] = None
    ssh_key: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None


class NodeResponse(BaseModel):
    """节点响应"""
    id: int
    name: str
    host: str
    port: int
    connect_type: str
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = None
    ssh_user: Optional[str] = None
    status: NodeStatus
    labels: Optional[Dict[str, Any]]
    resources: Optional[Dict[str, Any]]
    os_type: Optional[str] = None
    os_version: Optional[str] = None
    cpu_cores: int = 0
    memory_total: int = 0
    disk_total: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    agent_version: Optional[str] = None
    agent_status: str = "offline"
    agent_token: Optional[str] = None
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None
    container_count: int
    last_heartbeat: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class NodeTestResult(BaseModel):
    """节点测试结果"""
    status: str
    message: str
    info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ==================== API Endpoints ====================

@router.post("", response_model=NodeResponse)
async def create_node(
    node_data: NodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建节点
    
    - **name**: 节点名称
    - **host**: 主机地址
    - **port**: Docker API 端口（默认 2375）
    - **docker_host**: Docker socket 路径
    - **labels**: 节点标签
    """
    try:
        node_service = NodeService(db)
        node = node_service.create_node(
            name=node_data.name,
            host=node_data.host,
            port=node_data.port,
            connect_type=node_data.connect_type,
            ssh_host=node_data.ssh_host,
            ssh_port=node_data.ssh_port,
            ssh_user=node_data.ssh_user,
            ssh_pwd=node_data.ssh_pwd,
            ssh_key=node_data.ssh_key,
            docker_host=node_data.docker_host,
            labels=node_data.labels,
            public_ip=node_data.public_ip,
            private_ip=node_data.private_ip
        )
        return node
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建节点失败: {str(e)}")


@router.put("/{node_id}", response_model=NodeResponse)
async def update_node(
    node_id: int,
    node_data: NodeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新节点信息
    
    - **node_id**: 节点 ID
    """
    try:
        node_service = NodeService(db)
        node = node_service.update_node(
            node_id=node_id,
            name=node_data.name,
            host=node_data.host,
            port=node_data.port,
            connect_type=node_data.connect_type,
            ssh_host=node_data.ssh_host,
            ssh_port=node_data.ssh_port,
            ssh_user=node_data.ssh_user,
            ssh_pwd=node_data.ssh_pwd,
            ssh_key=node_data.ssh_key,
            labels=node_data.labels,
            public_ip=node_data.public_ip,
            private_ip=node_data.private_ip
        )
        
        if not node:
            raise HTTPException(status_code=404, detail="节点不存在")
        
        return node
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新节点失败: {str(e)}")


@router.get("", response_model=List[NodeResponse])
async def list_nodes(
    status: Optional[NodeStatus] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取节点列表"""
    try:
        from app.core.pagination import clamp_pagination
        offset, limit = clamp_pagination(offset, limit, default_limit=100)
        node_service = NodeService(db)
        nodes = node_service.get_nodes(
            status=status,
            limit=limit,
            offset=offset
        )
        # 列表不暴露令牌
        for n in nodes:
            n.agent_token = None
        return nodes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取节点列表失败: {str(e)}")


@router.get("/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取节点详情"""
    try:
        node_service = NodeService(db)
        node = node_service.get_node(node_id)
        
        if not node:
            raise HTTPException(status_code=404, detail="节点不存在")

        return node
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取节点详情失败: {str(e)}")


@router.post("/{node_id}/test", response_model=NodeTestResult)
async def test_node_connection(
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    测试节点连接
    
    - **node_id**: 节点 ID
    """
    try:
        node_service = NodeService(db)
        result = node_service.test_connection(node_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试连接失败: {str(e)}")


@router.post("/health-check")
async def check_all_nodes_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查所有节点健康状态"""
    try:
        node_service = NodeService(db)
        results = node_service.check_all_nodes_health()
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")


@router.post("/{node_id}/drain")
async def drain_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    排空节点（停止所有容器，准备维护）
    
    - **node_id**: 节点 ID
    """
    try:
        node_service = NodeService(db)
        success = node_service.drain_node(node_id)
        
        if success:
            return {"message": "节点排空成功"}
        else:
            raise HTTPException(status_code=500, detail="节点排空失败")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"排空节点失败: {str(e)}")


@router.post("/{node_id}/activate")
async def activate_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    激活节点
    
    - **node_id**: 节点 ID
    """
    try:
        node_service = NodeService(db)
        node_service.activate_node(node_id)
        return {"message": "节点激活成功"}
    except ValueError as e:
        # 节点不存在
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        # 节点存在但连接测试失败，返回真实原因
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"激活节点失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"激活节点失败: {str(e)}")


@router.delete("/{node_id}")
async def delete_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除节点（需要先排空）
    
    - **node_id**: 节点 ID
    """
    try:
        node_service = NodeService(db)
        success = node_service.delete_node(node_id)
        
        if success:
            return {"message": "节点删除成功"}
        else:
            raise HTTPException(status_code=404, detail="节点不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除节点失败: {str(e)}")


@router.get("/{node_id}/containers")
async def get_node_containers(
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取节点上的所有容器"""
    try:
        node_service = NodeService(db)
        node = node_service.get_node(node_id)
        
        if not node:
            raise HTTPException(status_code=404, detail="节点不存在")
        
        containers = node_service.get_node_containers(node_id)
        return {
            "node_id": node_id,
            "node_name": node.name,
            "containers": [
                {
                    "id": c.id,
                    "container_id": c.container_id,
                    "name": c.name,
                    "status": c.status.value,
                    "image": c.image,
                    "created_at": str(c.created_at)
                }
                for c in containers
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取容器列表失败: {str(e)}")
