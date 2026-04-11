"""
部署相关异步任务
"""
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.deploy_service import DeployService
from app.models import Deploy
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="deploy.execute", queue="deploy")
def execute_deploy_task(self, deploy_id: int):
    """
    异步执行部署任务
    
    Args:
        deploy_id: 部署 ID
    """
    db = SessionLocal()
    try:
        logger.info(f"Starting deploy task: {deploy_id}")
        
        deploy_service = DeployService(db)
        result = deploy_service.execute_deploy_sync(deploy_id)
        
        logger.info(f"Deploy task {deploy_id} completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Deploy task {deploy_id} failed: {e}")
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="deploy.rollback", queue="deploy")
def rollback_deploy_task(self, deploy_id: int):
    """
    异步回滚部署
    
    Args:
        deploy_id: 部署 ID
    """
    db = SessionLocal()
    try:
        logger.info(f"Starting rollback for deploy: {deploy_id}")
        
        deploy_service = DeployService(db)
        result = deploy_service.rollback_deploy(deploy_id)
        
        logger.info(f"Rollback completed for deploy {deploy_id}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Rollback failed for deploy {deploy_id}: {e}")
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="deploy.retry", queue="deploy", max_retries=3)
def retry_deploy_task(self, deploy_id: int):
    """
    重试部署任务
    
    Args:
        deploy_id: 部署 ID
    """
    db = SessionLocal()
    try:
        logger.info(f"Retrying deploy task: {deploy_id}")
        
        deploy_service = DeployService(db)
        result = deploy_service.execute_deploy_sync(deploy_id)
        
        logger.info(f"Deploy retry {deploy_id} completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Deploy retry {deploy_id} failed: {e}")
        # 自动重试
        self.retry(exc=e, countdown=60 * (self.request.retries + 1))
    finally:
        db.close()
