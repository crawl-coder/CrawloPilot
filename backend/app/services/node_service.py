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
import socket
import uuid

logger = logging.getLogger(__name__)


class NodeService:
    """节点管理服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_node(
        self,
        name: str,
        host: str,
        port: int = 22,
        connect_type: str = "ssh",
        ssh_host: Optional[str] = None,
        ssh_port: Optional[int] = 22,
        ssh_user: Optional[str] = "root",
        ssh_pwd: Optional[str] = None,
        ssh_key: Optional[str] = None,
        docker_host: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        public_ip: Optional[str] = None,
        private_ip: Optional[str] = None
    ) -> Node:
        """
        创建节点
        
        Args:
            name: 节点名称
            host: 主机地址
            port: 连接端口（Docker API 或 SSH）
            connect_type: 连接方式 (ssh/agent/docker)
            ssh_host: SSH 连接地址
            ssh_port: SSH 端口
            ssh_user: SSH 用户
            ssh_pwd: SSH 密码
            ssh_key: SSH 私钥
            docker_host: Docker socket 路径
            labels: 节点标签
            public_ip: 公网 IP
            private_ip: 内网 IP
            
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
            connect_type=connect_type,
            agent_token=uuid.uuid4().hex if connect_type == "agent" else None,
            agent_status="offline" if connect_type == "agent" else None,
            ssh_host=ssh_host or host,
            ssh_port=ssh_port or 22,
            ssh_user=ssh_user or "root",
            ssh_pwd=ssh_pwd,
            ssh_key=ssh_key,
            docker_host=docker_host,
            labels=labels or {},
            public_ip=public_ip,
            private_ip=private_ip,
            status=NodeStatus.OFFLINE,
            created_at=datetime.utcnow()
        )
        
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        
        logger.info(f"Created node: {name} (type={connect_type})")
        return node
    
    def update_node(
        self,
        node_id: int,
        name: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        connect_type: Optional[str] = None,
        ssh_host: Optional[str] = None,
        ssh_port: Optional[int] = None,
        ssh_user: Optional[str] = None,
        ssh_pwd: Optional[str] = None,
        ssh_key: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        public_ip: Optional[str] = None,
        private_ip: Optional[str] = None
    ) -> Optional[Node]:
        """
        更新节点信息
        
        Args:
            node_id: 节点 ID
            其他字段: 要更新的字段（None 表示不更新）
            
        Returns:
            更新后的 Node 对象，不存在返回 None
        """
        node = self.db.query(Node).get(node_id)
        if not node:
            return None
        
        if name is not None:
            # 检查新名称是否与其他节点冲突
            existing = self.db.query(Node).filter(Node.name == name, Node.id != node_id).first()
            if existing:
                raise ValueError(f"Node name '{name}' already exists")
            node.name = name
        if host is not None:
            node.host = host
        if port is not None:
            node.port = port
        if connect_type is not None:
            node.connect_type = connect_type
        if ssh_host is not None:
            node.ssh_host = ssh_host
        if ssh_port is not None:
            node.ssh_port = ssh_port
        if ssh_user is not None:
            node.ssh_user = ssh_user
        if ssh_pwd is not None:
            node.ssh_pwd = ssh_pwd
        if ssh_key is not None:
            node.ssh_key = ssh_key
        if labels is not None:
            node.labels = labels
        if public_ip is not None:
            node.public_ip = public_ip
        if private_ip is not None:
            node.private_ip = private_ip
        
        self.db.commit()
        self.db.refresh(node)
        
        logger.info(f"Updated node: {node.name}")
        return node
    
    def test_connection(self, node_id: int) -> Dict[str, Any]:
        """
        测试节点连接
        
        根据节点的 connect_type 执行不同的连接测试：
        - docker: 通过 Docker API 测试
        - ssh: TCP ping 测试端口可达性
        - agent: 检查心跳时间
        
        Args:
            node_id: 节点 ID
            
        Returns:
            连接测试结果
        """
        node = self.db.query(Node).get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")
        
        try:
            if node.connect_type == "docker":
                return self._test_docker_connection(node)
            elif node.connect_type == "ssh":
                return self._test_ssh_connection(node)
            elif node.connect_type == "agent":
                return self._test_agent_connection(node)
            else:
                # 默认尝试 TCP ping
                return self._test_tcp_ping(node.host, node.port, node.name)
                
        except Exception as e:
            node.status = NodeStatus.OFFLINE
            self.db.commit()
            
            return {
                "status": "failed",
                "connect_type": node.connect_type,
                "error": str(e),
                "message": f"Failed to connect to {node.name}"
            }
    
    def _test_docker_connection(self, node: Node) -> Dict[str, Any]:
        """测试 Docker API 连接"""
        docker_url = node.docker_host or f"tcp://{node.host}:{node.port}"
        docker = DockerService(docker_host=docker_url)
        
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
        
        self.db.commit()
        
        return {
            "status": "connected",
            "connect_type": "docker",
            "info": info,
            "message": f"Successfully connected to {node.name} via Docker API"
        }
    
    def _test_ssh_connection(self, node: Node) -> Dict[str, Any]:
        """测试 SSH 连接（真实握手：认证 + Python 环境探测）"""
        target_host = node.ssh_host or node.host
        target_port = node.ssh_port or node.port or 22

        try:
            from app.services.ssh_executor import SshConnection
            conn = SshConnection(
                host=target_host,
                port=target_port,
                user=node.ssh_user or "root",
                password=node.ssh_pwd,
                key=node.ssh_key,
            )
            client = conn.connect()
            transport = client.get_transport()
            if not transport:
                raise ConnectionError("SSH transport unavailable")

            # 探测系统与 Python 环境
            info = {}

            def _run(cmd: str) -> str:
                try:
                    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
                    return (stdout.read().decode("utf-8", errors="replace") or "").strip()
                except Exception:
                    return ""

            info["python"] = _run("python3 --version 2>&1")
            info["os"] = _run("uname -s")
            info["release"] = _run("uname -r")
            info["cpu_cores"] = _run("nproc")
            info["mem_kb"] = _run(
                "awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || sysctl -n hw.memsize 2>/dev/null"
            )
            conn.close()

            if not info["python"].startswith("Python"):
                raise ConnectionError(f"节点缺少 Python3: {info['python'] or 'unknown'}")

            node.os_type = info["os"] or None
            node.os_version = info["release"] or None
            node.cpu_cores = int(info["cpu_cores"]) if info["cpu_cores"].isdigit() else 0
            if info["mem_kb"].isdigit():
                node.memory_total = int(info["mem_kb"]) * 1024
            node.resources = {
                "os": node.os_type,
                "os_version": node.os_version,
                "cpu_cores": node.cpu_cores,
                "memory_total": node.memory_total,
                "python": info["python"],
            }
            node.status = NodeStatus.ONLINE
            node.last_heartbeat = datetime.utcnow()
            self.db.commit()

            return {
                "status": "connected",
                "connect_type": "ssh",
                "message": f"SSH 握手成功: {node.ssh_user or 'root'}@{target_host}:{target_port}",
                "info": info,
            }

        except Exception as e:
            node.status = NodeStatus.OFFLINE
            self.db.commit()
            return {
                "status": "failed",
                "connect_type": "ssh",
                "message": f"SSH 连接失败: {target_host}:{target_port}",
                "error": str(e),
            }
    
    def _test_agent_connection(self, node: Node) -> Dict[str, Any]:
        """测试 Agent 连接（检查心跳时间）"""
        if not node.last_heartbeat:
            node.status = NodeStatus.OFFLINE
            self.db.commit()
            return {
                "status": "failed",
                "connect_type": "agent",
                "message": f"Agent on {node.name} has not reported heartbeat yet"
            }
        
        now = datetime.utcnow()
        diff_seconds = (now - node.last_heartbeat).total_seconds()
        
        if diff_seconds < 60:  # 1 分钟内有心跳
            node.status = NodeStatus.ONLINE
            self.db.commit()
            return {
                "status": "connected",
                "connect_type": "agent",
                "message": f"Agent on {node.name} is online (heartbeat {diff_seconds}s ago)"
            }
        else:
            node.status = NodeStatus.OFFLINE
            self.db.commit()
            return {
                "status": "failed",
                "connect_type": "agent",
                "message": f"Agent on {node.name} heartbeat lost ({diff_seconds}s ago)"
            }
    
    def _test_tcp_ping(self, host: str, port: int, name: str) -> Dict[str, Any]:
        """TCP ping 测试端口可达性"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            result = sock.connect_ex((host, port))
            if result == 0:
                return {
                    "status": "connected",
                    "message": f"Port {port} is open on {name} ({host})"
                }
            else:
                return {
                    "status": "failed",
                    "error": f"Port {port} is not reachable on {host}",
                    "message": f"Failed to connect to {name}"
                }
        finally:
            sock.close()
    
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
                result = self.test_connection(node.id)
                results.append({
                    "node_id": node.id,
                    "name": node.name,
                    "status": "online" if result["status"] == "connected" else "offline",
                    "connect_type": node.connect_type,
                    "resources": node.resources or {}
                })
            except Exception as e:
                node.status = NodeStatus.OFFLINE
                results.append({
                    "node_id": node.id,
                    "name": node.name,
                    "status": "offline",
                    "connect_type": node.connect_type,
                    "error": str(e)
                })
        
        self.db.commit()
        return results

    def check_all_nodes_health_light(self) -> List[Dict[str, Any]]:
        """
        轻量健康检查（后台定时任务用）
        - ssh/docker: TCP ping（快速探活）
        - agent: 心跳时间
        """
        nodes = self.db.query(Node).all()
        results = []
        now = datetime.utcnow()

        for node in nodes:
            status = "offline"
            try:
                if node.connect_type == "agent":
                    if node.last_heartbeat and (now - node.last_heartbeat).total_seconds() < 90:
                        status = "online"
                else:
                    target_host = node.ssh_host or node.host
                    target_port = node.ssh_port or node.port or 22
                    ping = self._test_tcp_ping(target_host, target_port, node.name)
                    status = "online" if ping["status"] == "connected" else "offline"
            except Exception:
                status = "offline"

            node.status = NodeStatus.ONLINE if status == "online" else NodeStatus.OFFLINE
            if status == "online":
                node.last_heartbeat = now
            results.append({
                "node_id": node.id,
                "name": node.name,
                "status": status,
                "connect_type": node.connect_type,
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
        """激活节点（必须先通过连接测试，避免"假在线"）"""
        node = self.db.query(Node).get(node_id)
        if not node:
            return False

        result = self.test_connection(node_id)
        connected = result.get("status") == "connected"

        # 关联服务器的，激活后立即聚合服务器状态
        if node.server_id:
            from app.services.server_service import ServerService
            try:
                ServerService(self.db).aggregate_all_servers()
            except Exception as e:
                logger.warning(f"激活后聚合服务器状态失败: {e}")

        return connected
    
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
