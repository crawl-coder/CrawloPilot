"""
节点管理服务
管理 Docker 节点（服务器）的连接、状态监控
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Node, NodeStatus, Container, ContainerStatus
from app.services.docker_service import DockerService
import logging

logger = logging.getLogger(__name__)


class NodeService:
    """节点管理服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_node(
        self,
        name: str,
        host: str,
        port: int = 2375,
        docker_host: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> Node:
        """
        创建节点
        
        Args:
            name: 节点名称
            host: 主机地址
            port: Docker API 端口
            docker_host: Docker socket 路径
            labels: 节点标签
            
        Returns:
            Node 对象
        """
        # 检查名称是否已存在
        existing = self.db.query(Node).filter(Node.name == name).first()
        if existing:
            raise ValueError(f"Node name '{name}' already exists")
        
        node = Node(
            name=name,
            host=host,
            port=port,
            docker_host=docker_host,
            labels=labels or {},
            status=NodeStatus.OFFLINE,
            created_at=datetime.utcnow()
        )
        
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        
        logger.info(f"Created node: {name}")
        return node
    
    def test_connection(self, node_id: int) -> Dict[str, Any]:
        """
        测试节点连接
        
        Args:
            node_id: 节点 ID
            
        Returns:
            连接测试结果
        """
        node = self.db.query(Node).get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")
        
        try:
            # 创建临时 Docker 客户端
            docker_url = f"tcp://{node.host}:{node.port}"
            docker = DockerService(docker_host=docker_url)
            
            # 获取 Docker 信息
            info = docker.get_info()
            
            # 更新节点状态
            node.status = NodeStatus.ONLINE
            node.last_heartbeat = datetime.utcnow()
            node.resources = {
                "cpus": info.get("cpus", 0),
                "memory_total": info.get("memory_total", 0),
                "containers_total": info.get("containers", 0),
                "containers_running": info.get("containers_running", 0)
            }
            node.container_count = info.get("containers_running", 0)
            
            self.db.commit()
            
            return {
                "status": "connected",
                "info": info,
                "message": f"Successfully connected to {node.name}"
            }
            
        except Exception as e:
            node.status = NodeStatus.OFFLINE
            self.db.commit()
            
            return {
                "status": "failed",
                "error": str(e),
                "message": f"Failed to connect to {node.name}"
            }
    
    def update_heartbeat(self, node_id: int) -> bool:
        """更新节点心跳"""
        node = self.db.query(Node).get(node_id)
        if not node:
            return False
        
        node.last_heartbeat = datetime.utcnow()
        if node.status == NodeStatus.OFFLINE:
            node.status = NodeStatus.ONLINE
        
        self.db.commit()
        return True
    
    def check_all_nodes_health(self) -> List[Dict[str, Any]]:
        """检查所有节点健康状态"""
        nodes = self.db.query(Node).all()
        results = []
        
        for node in nodes:
            try:
                docker_url = f"tcp://{node.host}:{node.port}"
                docker = DockerService(docker_host=docker_url)
                
                if docker.ping():
                    info = docker.get_info()
                    node.status = NodeStatus.ONLINE
                    node.last_heartbeat = datetime.utcnow()
                    node.resources = {
                        "cpus": info.get("cpus", 0),
                        "memory_total": info.get("memory_total", 0),
                        "containers_total": info.get("containers", 0),
                        "containers_running": info.get("containers_running", 0)
                    }
                    node.container_count = info.get("containers_running", 0)
                    
                    results.append({
                        "node_id": node.id,
                        "name": node.name,
                        "status": "online",
                        "resources": node.resources
                    })
                else:
                    node.status = NodeStatus.OFFLINE
                    results.append({
                        "node_id": node.id,
                        "name": node.name,
                        "status": "offline",
                        "error": "Ping failed"
                    })
                    
            except Exception as e:
                node.status = NodeStatus.OFFLINE
                results.append({
                    "node_id": node.id,
                    "name": node.name,
                    "status": "offline",
                    "error": str(e)
                })
        
        self.db.commit()
        return results
    
    def drain_node(self, node_id: int) -> bool:
        """
        排空节点（停止所有容器，准备维护）
        
        Args:
            node_id: 节点 ID
            
        Returns:
            是否成功
        """
        node = self.db.query(Node).get(node_id)
        if not node:
            return False
        
        try:
            node.status = NodeStatus.DRAINING
            self.db.commit()
            
            # 获取该节点的所有运行中容器
            containers = self.db.query(Container).filter(
                Container.node_id == node_id,
                Container.status == ContainerStatus.RUNNING
            ).all()
            
            # 停止所有容器
            docker_url = f"tcp://{node.host}:{node.port}"
            docker = DockerService(docker_host=docker_url)
            
            for container in containers:
                try:
                    docker.stop_container(container.container_id)
                    container.status = ContainerStatus.EXITED
                    container.stopped_at = datetime.utcnow()
                except Exception as e:
                    logger.warning(f"Failed to stop container {container.container_id}: {e}")
            
            node.status = NodeStatus.MAINTENANCE
            node.container_count = 0
            self.db.commit()
            
            logger.info(f"Node {node.name} drained successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to drain node: {e}")
            return False
    
    def activate_node(self, node_id: int) -> bool:
        """激活节点"""
        node = self.db.query(Node).get(node_id)
        if not node:
            return False
        
        node.status = NodeStatus.ONLINE
        self.db.commit()
        return True
    
    def get_node(self, node_id: int) -> Optional[Node]:
        """获取节点详情"""
        return self.db.query(Node).get(node_id)
    
    def get_nodes(
        self,
        status: Optional[NodeStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Node]:
        """获取节点列表"""
        query = self.db.query(Node)
        
        if status:
            query = query.filter(Node.status == status)
        
        return query.order_by(Node.created_at.desc()).limit(limit).offset(offset).all()
    
    def get_node_containers(self, node_id: int) -> List[Container]:
        """获取节点上的所有容器"""
        return self.db.query(Container).filter(
            Container.node_id == node_id
        ).order_by(Container.created_at.desc()).all()
    
    def delete_node(self, node_id: int) -> bool:
        """
        删除节点（需要先排空）
        
        Args:
            node_id: 节点 ID
            
        Returns:
            是否成功
        """
        node = self.db.query(Node).get(node_id)
        if not node:
            return False
        
        # 检查是否有运行中的容器
        running_containers = self.db.query(Container).filter(
            Container.node_id == node_id,
            Container.status == ContainerStatus.RUNNING
        ).count()
        
        if running_containers > 0:
            raise ValueError(f"Node has {running_containers} running containers. Please drain first.")
        
        self.db.delete(node)
        self.db.commit()
        
        logger.info(f"Deleted node: {node.name}")
        return True
