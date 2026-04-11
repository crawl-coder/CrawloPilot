"""
部署服务层
实现不同的部署策略：蓝绿部署、滚动更新、重新创建
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Deploy, DeployStatus, DeployStrategy, Container, ContainerStatus, Node, ProjectVersion
from app.services.docker_service import get_docker_service
import logging
import uuid

logger = logging.getLogger(__name__)


class DeployService:
    """部署服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.docker = get_docker_service()
    
    async def create_deploy(
        self,
        project_id: int,
        version_id: int,
        strategy: DeployStrategy,
        node_id: int,
        target_env: str = "production",
        deployed_by: Optional[int] = None
    ) -> Deploy:
        """
        创建部署任务
        
        Args:
            project_id: 项目 ID
            version_id: 版本 ID
            strategy: 部署策略
            node_id: 目标节点 ID
            target_env: 目标环境
            deployed_by: 部署人 ID
            
        Returns:
            Deploy 对象
        """
        deploy = Deploy(
            project_id=project_id,
            version_id=version_id,
            strategy=strategy,
            status=DeployStatus.PENDING,
            target_env=target_env,
            node_id=node_id,
            deployed_by=deployed_by,
            created_at=datetime.utcnow()
        )
        
        self.db.add(deploy)
        self.db.commit()
        self.db.refresh(deploy)
        
        logger.info(f"Created deploy task: {deploy.id}")
        return deploy
    
    async def execute_deploy(self, deploy_id: int) -> Dict[str, Any]:
        """
        执行部署（异步版本）
        
        Args:
            deploy_id: 部署 ID
            
        Returns:
            部署结果
        """
        return self.execute_deploy_sync(deploy_id)
    
    def execute_deploy_sync(self, deploy_id: int) -> Dict[str, Any]:
        """
        执行部署（同步版本,用于 Celery 任务）
            
        Args:
            deploy_id: 部署 ID
                
        Returns:
            部署结果
        """
        deploy = self.db.query(Deploy).get(deploy_id)
        if not deploy:
            raise ValueError(f"Deploy {deploy_id} not found")
            
        # 获取版本信息
        version = self.db.query(ProjectVersion).get(deploy.version_id)
        if not version:
            raise ValueError(f"Version {deploy.version_id} not found")
            
        # 获取节点信息
        node = self.db.query(Node).get(deploy.node_id)
        if not node:
            raise ValueError(f"Node {deploy.node_id} not found")
            
        try:
            # 更新状态为部署中
            deploy.status = DeployStatus.DEPLOYING
            deploy.started_at = datetime.utcnow()
            self.db.commit()
                
            # 根据策略执行部署（使用同步版本）
            if deploy.strategy == DeployStrategy.BLUE_GREEN:
                import asyncio
                result = asyncio.run(self._blue_green_deploy(deploy, version, node))
            elif deploy.strategy == DeployStrategy.ROLLING:
                import asyncio
                result = asyncio.run(self._rolling_deploy(deploy, version, node))
            else:  # RECREATE
                import asyncio
                result = asyncio.run(self._recreate_deploy(deploy, version, node))
                
            # 更新部署状态
            deploy.status = DeployStatus.SUCCESS
            deploy.finished_at = datetime.utcnow()
            deploy.container_ids = result.get("container_ids", [])
            self.db.commit()
                
            logger.info(f"Deploy {deploy_id} completed successfully")
            return result
                
        except Exception as e:
            logger.error(f"Deploy {deploy_id} failed: {e}")
            deploy.status = DeployStatus.FAILED
            deploy.error_message = str(e)
            deploy.finished_at = datetime.utcnow()
            self.db.commit()
                
            # 尝试回滚
            self.rollback_deploy_sync(deploy_id)
                
            raise
        
    def rollback_deploy_sync(self, deploy_id: int) -> bool:
        """回滚部署（同步版本）"""
        deploy = self.db.query(Deploy).get(deploy_id)
        if not deploy:
            return False
            
        try:
            logger.info(f"Rolling back deploy: {deploy_id}")
                
            # 停止本次部署创建的容器
            if deploy.container_ids:
                for container_id in deploy.container_ids:
                    try:
                        self.docker.stop_container(container_id)
                        self.docker.remove_container(container_id)
                    except Exception as e:
                        logger.warning(f"Failed to remove container during rollback: {e}")
                
            deploy.status = DeployStatus.ROLLED_BACK
            self.db.commit()
                
            logger.info(f"Deploy {deploy_id} rolled back successfully")
            return True
                
        except Exception as e:
            logger.error(f"Failed to rollback deploy: {e}")
            return False
    
    async def _recreate_deploy(
        self,
        deploy: Deploy,
        version: ProjectVersion,
        node: Node
    ) -> Dict[str, Any]:
        """
        重新创建部署（最简单）
        1. 停止旧容器
        2. 删除旧容器
        3. 创建新容器
        """
        container_ids = []
        
        # 1. 停止并删除该项目的旧容器
        old_containers = self.db.query(Container).filter(
            Container.project_id == deploy.project_id,
            Container.node_id == deploy.node_id,
            Container.status == ContainerStatus.RUNNING
        ).all()
        
        for old_container in old_containers:
            try:
                self.docker.stop_container(old_container.container_id)
                self.docker.remove_container(old_container.container_id)
                old_container.status = ContainerStatus.EXITED
                old_container.stopped_at = datetime.utcnow()
            except Exception as e:
                logger.warning(f"Failed to remove old container: {e}")
        
        self.db.commit()
        
        # 2. 创建新容器
        container_name = f"{version.project.name}-{version.version}-{uuid.uuid4().hex[:8]}"
        image_tag = version.image_tag or f"{version.project.name}:{version.version}"
        
        container_info = self.docker.create_container(
            image=image_tag,
            name=container_name,
            environment={
                "PROJECT_ID": str(deploy.project_id),
                "VERSION": version.version,
                "ENV": deploy.target_env
            }
        )
        
        # 3. 记录容器信息
        container = Container(
            container_id=container_info["id"],
            name=container_name,
            node_id=deploy.node_id,
            project_id=deploy.project_id,
            version_id=deploy.version_id,
            image=image_tag,
            status=ContainerStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        
        self.db.add(container)
        self.db.commit()
        
        container_ids.append(container_info["id"])
        
        return {
            "status": "success",
            "container_ids": container_ids,
            "message": f"Deployed {container_name} successfully"
        }
    
    async def _blue_green_deploy(
        self,
        deploy: Deploy,
        version: ProjectVersion,
        node: Node
    ) -> Dict[str, Any]:
        """
        蓝绿部署
        1. 创建新版本容器（绿）
        2. 等待绿容器健康检查通过
        3. 切换流量（更新端口映射）
        4. 停止旧容器（蓝）
        """
        container_ids = []
        
        # 1. 获取当前运行的容器（蓝）
        blue_containers = self.db.query(Container).filter(
            Container.project_id == deploy.project_id,
            Container.node_id == deploy.node_id,
            Container.status == ContainerStatus.RUNNING
        ).all()
        
        # 2. 创建新容器（绿）
        green_container_name = f"{version.project.name}-{version.version}-green-{uuid.uuid4().hex[:6]}"
        image_tag = version.image_tag or f"{version.project.name}:{version.version}"
        
        # 使用不同的端口（+1000）避免冲突
        green_ports = {"80/tcp": 8001} if not blue_containers else {"80/tcp": 8002}
        
        green_container_info = self.docker.create_container(
            image=image_tag,
            name=green_container_name,
            environment={
                "PROJECT_ID": str(deploy.project_id),
                "VERSION": version.version,
                "ENV": deploy.target_env,
                "DEPLOY_TYPE": "blue-green-green"
            },
            ports=green_ports
        )
        
        green_container = Container(
            container_id=green_container_info["id"],
            name=green_container_name,
            node_id=deploy.node_id,
            project_id=deploy.project_id,
            version_id=deploy.version_id,
            image=image_tag,
            status=ContainerStatus.RUNNING,
            ports=green_ports,
            started_at=datetime.utcnow()
        )
        
        self.db.add(green_container)
        container_ids.append(green_container_info["id"])
        
        # 3. 等待健康检查（简化版，实际应该检查健康状态）
        import asyncio
        await asyncio.sleep(5)  # 等待 5 秒
        
        # 4. 停止蓝容器
        for blue_container in blue_containers:
            try:
                self.docker.stop_container(blue_container.container_id)
                blue_container.status = ContainerStatus.EXITED
                blue_container.stopped_at = datetime.utcnow()
            except Exception as e:
                logger.warning(f"Failed to stop blue container: {e}")
        
        self.db.commit()
        
        return {
            "status": "success",
            "container_ids": container_ids,
            "message": f"Blue-green deploy completed: {green_container_name}"
        }
    
    async def _rolling_deploy(
        self,
        deploy: Deploy,
        version: ProjectVersion,
        node: Node
    ) -> Dict[str, Any]:
        """
        滚动更新
        1. 逐个替换容器
        2. 每次替换一个，等待健康后继续
        """
        container_ids = []
        
        # 获取当前容器
        old_containers = self.db.query(Container).filter(
            Container.project_id == deploy.project_id,
            Container.node_id == deploy.node_id,
            Container.status == ContainerStatus.RUNNING
        ).all()
        
        image_tag = version.image_tag or f"{version.project.name}:{version.version}"
        
        # 逐个替换
        for idx, old_container in enumerate(old_containers):
            # 创建新容器
            new_container_name = f"{version.project.name}-{version.version}-rolling-{idx}-{uuid.uuid4().hex[:6]}"
            
            new_container_info = self.docker.create_container(
                image=image_tag,
                name=new_container_name,
                environment={
                    "PROJECT_ID": str(deploy.project_id),
                    "VERSION": version.version,
                    "ENV": deploy.target_env,
                    "DEPLOY_TYPE": "rolling"
                }
            )
            
            new_container = Container(
                container_id=new_container_info["id"],
                name=new_container_name,
                node_id=deploy.node_id,
                project_id=deploy.project_id,
                version_id=deploy.version_id,
                image=image_tag,
                status=ContainerStatus.RUNNING,
                started_at=datetime.utcnow()
            )
            
            self.db.add(new_container)
            container_ids.append(new_container_info["id"])
            
            # 等待新容器启动
            import asyncio
            await asyncio.sleep(3)
            
            # 停止旧容器
            try:
                self.docker.stop_container(old_container.container_id)
                old_container.status = ContainerStatus.EXITED
                old_container.stopped_at = datetime.utcnow()
            except Exception as e:
                logger.warning(f"Failed to stop old container: {e}")
        
        self.db.commit()
        
        return {
            "status": "success",
            "container_ids": container_ids,
            "message": f"Rolling deploy completed: {len(container_ids)} containers"
        }
    
    async def rollback_deploy(self, deploy_id: int) -> bool:
        """
        回滚部署
        
        Args:
            deploy_id: 部署 ID
            
        Returns:
            是否成功
        """
        deploy = self.db.query(Deploy).get(deploy_id)
        if not deploy:
            return False
        
        try:
            logger.info(f"Rolling back deploy: {deploy_id}")
            
            # 停止本次部署创建的容器
            if deploy.container_ids:
                for container_id in deploy.container_ids:
                    try:
                        self.docker.stop_container(container_id)
                        self.docker.remove_container(container_id)
                    except Exception as e:
                        logger.warning(f"Failed to remove container during rollback: {e}")
            
            deploy.status = DeployStatus.ROLLED_BACK
            self.db.commit()
            
            logger.info(f"Deploy {deploy_id} rolled back successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rollback deploy: {e}")
            return False
    
    def get_deploy(self, deploy_id: int) -> Optional[Deploy]:
        """获取部署详情"""
        return self.db.query(Deploy).get(deploy_id)
    
    def get_deploys(
        self,
        project_id: Optional[int] = None,
        status: Optional[DeployStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Deploy]:
        """获取部署列表"""
        query = self.db.query(Deploy)
        
        if project_id:
            query = query.filter(Deploy.project_id == project_id)
        
        if status:
            query = query.filter(Deploy.status == status)
        
        return query.order_by(Deploy.created_at.desc()).limit(limit).offset(offset).all()
