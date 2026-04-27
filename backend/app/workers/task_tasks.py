"""
任务执行 Celery 异步任务

负责异步执行爬虫任务
"""

import logging
from datetime import datetime
from typing import Dict

from app.core.database import SessionLocal
from app.models import TaskInstance, TaskStatus, Spider
from app.services.task_executor import TaskExecutor, TaskConfig
from celery import shared_task

logger = logging.getLogger(__name__)


def execute_spider_task(task_id: str, spider_id: str, spider_name: str, **kwargs) -> Dict:
    """
    执行爬虫任务
    
    Args:
        task_id: 任务 ID
        spider_id: 爬虫 ID
        spider_name: 爬虫名称
        **kwargs: 其他参数
            - git_url: Git 仓库地址
            - git_branch: Git 分支
            - node_id: 节点 ID
            - memory_limit: 内存限制
            - cpu_limit: CPU 限制
            - timeout: 超时时间
            
    Returns:
        执行结果
    """
    db = SessionLocal()
    executor = TaskExecutor()
    
    try:
        # 更新任务状态为 PENDING
        task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
        if task:
            task.status = TaskStatus.PENDING
            db.commit()
        
        # 构建任务配置
        config = TaskConfig(
            task_id=task_id,
            spider_id=spider_id,
            spider_name=spider_name,
            git_url=kwargs.get('git_url'),
            git_branch=kwargs.get('git_branch', 'main'),
            node_id=kwargs.get('node_id'),
            entry_file=kwargs.get('entry_file'),  # 入口文件
            memory_limit=kwargs.get('memory_limit', '512m'),
            cpu_limit=kwargs.get('cpu_limit', 1.0),
            timeout=kwargs.get('timeout', 3600),
        )
        
        logger.info(f"Starting task execution: {task_id}")
        
        # 执行任务
        import asyncio
        container_id = asyncio.run(executor.execute_task(config))
        
        logger.info(f"Task {task_id} started in container {container_id[:12]}")
        
        return {
            'success': True,
            'task_id': task_id,
            'container_id': container_id,
            'message': 'Task started successfully'
        }
        
    except Exception as e:
        logger.error(f"Task execution failed: {e}")
        
        # 更新任务状态为 FAILED
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                task.finished_at = datetime.utcnow()
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update task status: {db_error}")
        
        return {
            'success': False,
            'task_id': task_id,
            'error': str(e)
        }
    
    finally:
        db.close()


def stop_spider_task(task_id: str) -> Dict:
    """
    停止爬虫任务
    
    Args:
        task_id: 任务 ID
        
    Returns:
        停止结果
    """
    executor = TaskExecutor()
    
    try:
        import asyncio
        success = asyncio.run(executor.stop_task(task_id))
        
        return {
            'success': success,
            'task_id': task_id,
            'message': 'Task stopped' if success else 'Failed to stop task'
        }
        
    except Exception as e:
        logger.error(f"Failed to stop task: {e}")
        return {
            'success': False,
            'task_id': task_id,
            'error': str(e)
        }


def get_task_status(task_id: str) -> Dict:
    """
    获取任务状态
    
    Args:
        task_id: 任务 ID
        
    Returns:
        任务状态
    """
    executor = TaskExecutor()
    
    try:
        import asyncio
        status = asyncio.run(executor.get_task_status(task_id))
        
        if status:
            return {
                'success': True,
                'task_id': task_id,
                'status': status
            }
        else:
            return {
                'success': False,
                'task_id': task_id,
                'message': 'Task not found'
            }
            
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        return {
            'success': False,
            'task_id': task_id,
            'error': str(e)
        }


@shared_task(bind=True, max_retries=3)
def pause_spider_task(self, task_id: str) -> Dict:
    """
    暂停爬虫任务
    
    Args:
        task_id: 任务 ID
        
    Returns:
        暂停结果
    """
    from app.services.task_executor import TaskExecutor
    
    executor = TaskExecutor()
    
    try:
        import asyncio
        success = asyncio.run(executor.pause_task(task_id))
        
        if success:
            return {
                'success': True,
                'task_id': task_id,
                'message': 'Task paused'
            }
        else:
            return {
                'success': False,
                'task_id': task_id,
                'message': 'Failed to pause task'
            }
            
    except Exception as e:
        logger.error(f"Failed to pause task: {e}")
        return {
            'success': False,
            'task_id': task_id,
            'error': str(e)
        }


@shared_task(bind=True, max_retries=3)
def resume_spider_task(self, task_id: str) -> Dict:
    """
    恢复爬虫任务
    
    Args:
        task_id: 任务 ID
        
    Returns:
        恢复结果
    """
    from app.services.task_executor import TaskExecutor
    
    executor = TaskExecutor()
    
    try:
        import asyncio
        success = asyncio.run(executor.resume_task(task_id))
        
        if success:
            return {
                'success': True,
                'task_id': task_id,
                'message': 'Task resumed'
            }
        else:
            return {
                'success': False,
                'task_id': task_id,
                'message': 'Failed to resume task'
            }
            
    except Exception as e:
        logger.error(f"Failed to resume task: {e}")
        return {
            'success': False,
            'task_id': task_id,
            'error': str(e)
        }


def get_task_logs(task_id: str, tail: int = 100) -> Dict:
    """
    获取任务日志
    
    Args:
        task_id: 任务 ID
        tail: 日志行数
        
    Returns:
        任务日志
    """
    executor = TaskExecutor()
    
    try:
        import asyncio
        logs = asyncio.run(executor.get_task_logs(task_id, tail=tail))
        
        return {
            'success': True,
            'task_id': task_id,
            'logs': logs
        }
        
    except Exception as e:
        logger.error(f"Failed to get task logs: {e}")
        return {
            'success': False,
            'task_id': task_id,
            'error': str(e)
        }
