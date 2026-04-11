"""
Docker Engine 服务层
封装 Docker API 操作，提供容器生命周期管理
"""
import docker
from docker.errors import DockerException, NotFound, APIError
from typing import Dict, List, Optional, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class DockerService:
    """Docker Engine 封装服务"""
    
    def __init__(self, docker_host: Optional[str] = None):
        """
        初始化 Docker 客户端
        
        Args:
            docker_host: Docker 守护进程地址，默认使用配置
        """
        self.docker_host = docker_host or settings.DOCKER_HOST
        try:
            self.client = docker.DockerClient(base_url=self.docker_host)
            self.ping()
            logger.info(f"Connected to Docker: {self.docker_host}")
        except DockerException as e:
            logger.error(f"Failed to connect to Docker: {e}")
            raise
    
    def ping(self) -> bool:
        """检查 Docker 连接"""
        try:
            return self.client.ping()
        except Exception:
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """获取 Docker 信息"""
        try:
            info = self.client.info()
            return {
                "containers": info.get("Containers", 0),
                "containers_running": info.get("ContainersRunning", 0),
                "containers_paused": info.get("ContainersPaused", 0),
                "containers_stopped": info.get("ContainersStopped", 0),
                "images": info.get("Images", 0),
                "driver": info.get("Driver"),
                "memory_total": info.get("MemTotal"),
                "cpus": info.get("NCPU"),
                "docker_version": info.get("ServerVersion"),
            }
        except Exception as e:
            logger.error(f"Failed to get Docker info: {e}")
            raise
    
    # ==================== 镜像操作 ====================
    
    def build_image(self, path: str, tag: str, dockerfile: str = "Dockerfile") -> Dict[str, Any]:
        """
        构建 Docker 镜像
        
        Args:
            path: 构建上下文路径
            tag: 镜像标签
            dockerfile: Dockerfile 路径
            
        Returns:
            镜像信息
        """
        try:
            logger.info(f"Building image {tag} from {path}")
            image, logs = self.client.images.build(
                path=path,
                tag=tag,
                dockerfile=dockerfile,
                rm=True,
                nocache=False
            )
            
            # 解析构建日志
            build_logs = []
            for log in logs:
                if "stream" in log:
                    build_logs.append(log["stream"].strip())
            
            return {
                "id": image.id,
                "tag": tag,
                "short_id": image.short_id,
                "logs": build_logs
            }
        except APIError as e:
            logger.error(f"Failed to build image: {e}")
            raise
    
    def pull_image(self, repository: str, tag: str = "latest") -> Dict[str, Any]:
        """
        拉取 Docker 镜像
        
        Args:
            repository: 镜像仓库
            tag: 镜像标签
            
        Returns:
            镜像信息
        """
        try:
            logger.info(f"Pulling image {repository}:{tag}")
            image = self.client.images.pull(repository, tag=tag)
            return {
                "id": image.id,
                "tag": f"{repository}:{tag}",
                "short_id": image.short_id
            }
        except APIError as e:
            logger.error(f"Failed to pull image: {e}")
            raise
    
    def list_images(self) -> List[Dict[str, Any]]:
        """列出所有镜像"""
        try:
            images = self.client.images.list()
            return [
                {
                    "id": img.id,
                    "short_id": img.short_id,
                    "tags": img.tags,
                    "created": img.attrs.get("Created"),
                    "size": img.attrs.get("Size", 0)
                }
                for img in images
            ]
        except Exception as e:
            logger.error(f"Failed to list images: {e}")
            raise
    
    def remove_image(self, image_tag: str, force: bool = False) -> bool:
        """删除镜像"""
        try:
            self.client.images.remove(image_tag, force=force)
            logger.info(f"Removed image: {image_tag}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove image: {e}")
            raise
    
    # ==================== 容器操作 ====================
    
    def create_container(
        self,
        image: str,
        name: str,
        environment: Optional[Dict[str, str]] = None,
        ports: Optional[Dict[str, int]] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        network: Optional[str] = None,
        resource_limits: Optional[Dict[str, Any]] = None,
        restart_policy: str = "unless-stopped",
        **kwargs
    ) -> Dict[str, Any]:
        """
        创建并启动容器
        
        Args:
            image: 镜像名称
            name: 容器名称
            environment: 环境变量
            ports: 端口映射 {"80/tcp": 8080}
            volumes: 卷映射 {"/host/path": {"bind": "/container/path", "mode": "rw"}}
            network: 网络名称
            resource_limits: 资源限制 {"cpu_limit": "1.0", "mem_limit": "512m"}
            restart_policy: 重启策略
            
        Returns:
            容器信息
        """
        try:
            logger.info(f"Creating container: {name}")
            
            # 准备容器参数
            container_kwargs = {
                "image": image,
                "name": name,
                "environment": environment or {},
                "detach": True,
                "restart_policy": {"Name": restart_policy},
            }
            
            if ports:
                container_kwargs["ports"] = ports
            
            if volumes:
                container_kwargs["volumes"] = volumes
            
            if network:
                container_kwargs["network"] = network
            
            if resource_limits:
                if "cpu_limit" in resource_limits:
                    container_kwargs["cpu_quota"] = int(float(resource_limits["cpu_limit"]) * 100000)
                if "mem_limit" in resource_limits:
                    container_kwargs["mem_limit"] = resource_limits["mem_limit"]
            
            container_kwargs.update(kwargs)
            
            container = self.client.containers.run(**container_kwargs)
            
            return {
                "id": container.id,
                "short_id": container.short_id,
                "name": container.name,
                "status": container.status,
                "image": image
            }
        except APIError as e:
            logger.error(f"Failed to create container: {e}")
            raise
    
    def get_container(self, container_id: str) -> Optional[Dict[str, Any]]:
        """获取容器信息"""
        try:
            container = self.client.containers.get(container_id)
            return {
                "id": container.id,
                "short_id": container.short_id,
                "name": container.name,
                "status": container.status,
                "image": container.image.tags[0] if container.image.tags else None,
                "created": container.attrs.get("Created"),
                "ports": container.attrs.get("NetworkSettings", {}).get("Ports", {}),
                "network_settings": container.attrs.get("NetworkSettings", {})
            }
        except NotFound:
            return None
        except Exception as e:
            logger.error(f"Failed to get container: {e}")
            raise
    
    def list_containers(self, all: bool = True) -> List[Dict[str, Any]]:
        """
        列出容器
        
        Args:
            all: 是否包含已停止的容器
        """
        try:
            containers = self.client.containers.list(all=all)
            return [
                {
                    "id": c.id,
                    "short_id": c.short_id,
                    "name": c.name,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else None,
                    "created": c.attrs.get("Created"),
                    "ports": c.attrs.get("NetworkSettings", {}).get("Ports", {})
                }
                for c in containers
            ]
        except Exception as e:
            logger.error(f"Failed to list containers: {e}")
            raise
    
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """停止容器"""
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info(f"Stopped container: {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop container: {e}")
            raise
    
    def start_container(self, container_id: str) -> bool:
        """启动容器"""
        try:
            container = self.client.containers.get(container_id)
            container.start()
            logger.info(f"Started container: {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to start container: {e}")
            raise
    
    def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """重启容器"""
        try:
            container = self.client.containers.get(container_id)
            container.restart(timeout=timeout)
            logger.info(f"Restarted container: {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to restart container: {e}")
            raise
    
    def remove_container(self, container_id: str, force: bool = False) -> bool:
        """删除容器"""
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=force)
            logger.info(f"Removed container: {container_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove container: {e}")
            raise
    
    def get_container_logs(
        self,
        container_id: str,
        tail: int = 100,
        since: Optional[int] = None,
        timestamps: bool = True
    ) -> str:
        """
        获取容器日志
        
        Args:
            container_id: 容器 ID
            tail: 最后 N 行
            since: 从这个时间戳开始的日志
            timestamps: 是否包含时间戳
        """
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(
                tail=tail,
                since=since,
                timestamps=timestamps,
                stdout=True,
                stderr=True
            )
            return logs.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to get container logs: {e}")
            raise
    
    def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """获取容器资源使用情况"""
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)
            
            # 计算 CPU 使用率
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            
            cpu_percent = 0.0
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * 100.0
            
            # 计算内存使用率
            memory_usage = stats["memory_stats"].get("usage", 0)
            memory_limit = stats["memory_stats"].get("limit", 0)
            memory_percent = (memory_usage / memory_limit * 100) if memory_limit > 0 else 0
            
            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_usage": memory_usage,
                "memory_limit": memory_limit,
                "memory_percent": round(memory_percent, 2),
                "network_rx_bytes": sum(
                    iface.get("rx_bytes", 0) 
                    for iface in stats.get("networks", {}).values()
                ),
                "network_tx_bytes": sum(
                    iface.get("tx_bytes", 0) 
                    for iface in stats.get("networks", {}).values()
                )
            }
        except Exception as e:
            logger.error(f"Failed to get container stats: {e}")
            raise
    
    # ==================== 网络操作 ====================
    
    def list_networks(self) -> List[Dict[str, Any]]:
        """列出网络"""
        try:
            networks = self.client.networks.list()
            return [
                {
                    "id": net.id,
                    "name": net.name,
                    "driver": net.attrs.get("Driver"),
                    "scope": net.attrs.get("Scope")
                }
                for net in networks
            ]
        except Exception as e:
            logger.error(f"Failed to list networks: {e}")
            raise
    
    def create_network(self, name: str, driver: str = "bridge") -> Dict[str, Any]:
        """创建网络"""
        try:
            network = self.client.networks.create(name, driver=driver)
            return {
                "id": network.id,
                "name": network.name,
                "driver": driver
            }
        except Exception as e:
            logger.error(f"Failed to create network: {e}")
            raise


# 单例模式
_docker_service_instance = None


def get_docker_service(docker_host: Optional[str] = None) -> DockerService:
    """获取 Docker 服务单例"""
    global _docker_service_instance
    if _docker_service_instance is None:
        _docker_service_instance = DockerService(docker_host)
    return _docker_service_instance
