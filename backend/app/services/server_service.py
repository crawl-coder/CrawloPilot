"""
Server（真实服务器）服务层

负责服务器的创建/探测/状态聚合/删除/维护，以及服务器下的执行通道管理。
"""

import socket
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Server, ServerStatus, Node, NodeStatus, Container, ContainerStatus

logger = logging.getLogger(__name__)


class ServerService:
    """服务器管理服务"""

    def __init__(self, db: Session):
        self.db = db

    # ============ 基础 CRUD ============

    def create_server(
        self,
        name: str,
        host: str,
        region: Optional[str] = None,
        labels: Optional[Dict] = None,
        description: Optional[str] = None,
    ) -> Server:
        existing = self.db.query(Server).filter(Server.name == name).first()
        if existing:
            raise ValueError(f"服务器名称 '{name}' 已存在")

        server = Server(
            name=name,
            host=host,
            region=region,
            labels=labels or {},
            description=description,
            status=ServerStatus.UNKNOWN,
        )
        self.db.add(server)
        self.db.commit()
        self.db.refresh(server)
        logger.info(f"创建服务器: {name} ({host})")
        return server

    def get_server(self, server_id: int) -> Optional[Server]:
        return self.db.query(Server).filter(Server.id == server_id).first()

    def get_servers(
        self,
        status: Optional[ServerStatus] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ):
        query = self.db.query(Server)
        if status:
            query = query.filter(Server.status == status)
        if keyword:
            kw = f"%{keyword}%"
            query = query.filter(
                (Server.name.like(kw)) | (Server.host.like(kw))
            )
        total = query.count()
        servers = query.order_by(Server.id.desc()).offset(skip).limit(limit).all()
        return servers, total

    def update_server(
        self,
        server_id: int,
        name: Optional[str] = None,
        region: Optional[str] = None,
        labels: Optional[Dict] = None,
        description: Optional[str] = None,
    ) -> Optional[Server]:
        server = self.get_server(server_id)
        if not server:
            return None
        if name is not None:
            existing = self.db.query(Server).filter(
                Server.name == name, Server.id != server_id
            ).first()
            if existing:
                raise ValueError(f"服务器名称 '{name}' 已存在")
            server.name = name
        if region is not None:
            server.region = region
        if labels is not None:
            server.labels = labels
        if description is not None:
            server.description = description
        self.db.commit()
        self.db.refresh(server)
        return server

    def delete_server(self, server_id: int) -> bool:
        """删除服务器（约束：无在线通道；通道一并删除）"""
        server = self.get_server(server_id)
        if not server:
            return False

        online_nodes = self.db.query(Node).filter(
            Node.server_id == server_id,
            Node.status == NodeStatus.ONLINE,
        ).count()
        if online_nodes > 0:
            raise ValueError(
                f"服务器仍有 {online_nodes} 个在线通道，请先停用/删除通道"
            )

        # 删除服务器及其全部通道
        self.db.query(Node).filter(Node.server_id == server_id).delete()
        self.db.delete(server)
        self.db.commit()
        logger.info(f"删除服务器: {server.name}")
        return True

    # ============ 探测与状态聚合 ============

    def _tcp_ping(self, host: str, port: int) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            try:
                return sock.connect_ex((host, port)) == 0
            finally:
                sock.close()
        except Exception:
            return False

    def probe_server(self, server_id: int) -> Dict[str, Any]:
        """
        探测服务器：
        1. 端口可达性（22/2375）
        2. 若已有关联通道，逐通道真实握手并采集系统信息
        3. 聚合服务器状态
        """
        server = self.get_server(server_id)
        if not server:
            raise ValueError("服务器不存在")

        ports = {
            "ssh": self._tcp_ping(server.host, 22),
            "docker": self._tcp_ping(server.host, 2375),
        }

        # 逐通道真实握手（复用节点测试逻辑）
        from app.services.node_service import NodeService
        node_service = NodeService(self.db)
        nodes = self.db.query(Node).filter(Node.server_id == server_id).all()

        # 按可信度排序采集系统信息：ssh > docker > agent
        # ssh/docker 是对服务器主机端口的直接握手；agent 是代理自报，可能运行在其他机器
        _PRIORITY = {"ssh": 0, "docker": 1, "agent": 2}
        sorted_nodes = sorted(
            nodes,
            key=lambda n: _PRIORITY.get(
                n.connect_type.value if hasattr(n.connect_type, "value") else n.connect_type, 3
            )
        )
        filled = set()
        for node in sorted_nodes:
            try:
                result = node_service.test_connection(node.id)
                if result.get("status") != "connected":
                    continue
                # 每个字段只采信最高优先级通道的值，避免多机数据拼接
                for field in ("os_type", "os_version", "cpu_cores", "memory_total"):
                    if field not in filled and getattr(node, field):
                        setattr(server, field, getattr(node, field))
                        filled.add(field)
            except Exception as e:
                logger.warning(f"通道 {node.name} 握手失败: {e}")

        server.last_probed_at = datetime.utcnow()
        self.db.commit()
        self.aggregate_server_status(server)
        return {
            "server_id": server.id,
            "ports": ports,
            "status": server.status.value,
            "last_probed_at": server.last_probed_at.isoformat() if server.last_probed_at else None,
        }

    def aggregate_server_status(self, server: Optional[Server] = None):
        """聚合服务器总状态：任一通道在线 → online；无通道 → unknown；否则 offline"""
        servers = [server] if server else self.db.query(Server).all()
        for s in servers:
            if s.status == ServerStatus.MAINTENANCE:
                continue
            nodes = self.db.query(Node).filter(Node.server_id == s.id).all()
            if not nodes:
                s.status = ServerStatus.UNKNOWN
            elif any(n.status == NodeStatus.ONLINE for n in nodes):
                s.status = ServerStatus.ONLINE
            else:
                s.status = ServerStatus.OFFLINE
        self.db.commit()

    def aggregate_all_servers(self):
        """聚合所有服务器状态（后台健康检查调用）"""
        self.aggregate_server_status()

    # ============ 维护 ============

    def enter_maintenance(self, server_id: int) -> bool:
        """进入维护：先排空在线 Docker 通道，再置 maintenance"""
        server = self.get_server(server_id)
        if not server:
            return False

        from app.services.node_service import NodeService
        node_service = NodeService(self.db)
        docker_nodes = self.db.query(Node).filter(
            Node.server_id == server_id,
            Node.connect_type == "docker",
            Node.status == NodeStatus.ONLINE,
        ).all()
        for node in docker_nodes:
            try:
                node_service.drain_node(node.id)
            except Exception as e:
                logger.warning(f"排空通道 {node.name} 失败: {e}")

        server.status = ServerStatus.MAINTENANCE
        self.db.commit()
        return True

    # ============ 通道管理 ============

    def get_channel_summary(self, server_id: int) -> Dict[str, int]:
        nodes = self.db.query(Node).filter(Node.server_id == server_id).all()
        summary = {"ssh": 0, "docker": 0, "agent": 0}
        for n in nodes:
            if n.connect_type in summary:
                summary[n.connect_type] += 1
        return summary

    def get_server_nodes(self, server_id: int) -> List[Node]:
        return self.db.query(Node).filter(Node.server_id == server_id).all()

    def serialize_server(self, server: Server) -> Dict[str, Any]:
        nodes = self.db.query(Node).filter(Node.server_id == server.id).all()
        online_channels = sum(1 for n in nodes if n.status == NodeStatus.ONLINE)
        return {
            "id": server.id,
            "name": server.name,
            "host": server.host,
            "os_type": server.os_type,
            "os_version": server.os_version,
            "cpu_cores": server.cpu_cores,
            "memory_total": server.memory_total,
            "disk_total": server.disk_total,
            "region": server.region,
            "labels": server.labels,
            "description": server.description,
            "status": server.status.value if hasattr(server.status, "value") else server.status,
            "last_probed_at": server.last_probed_at,
            "channel_summary": self.get_channel_summary(server.id),
            "online_channels": online_channels,
            "created_at": server.created_at,
            "updated_at": server.updated_at,
        }
