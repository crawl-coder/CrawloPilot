"""
日志采集器

负责:
- 从 Docker 容器采集日志
- 解析 Crawlo 框架日志格式
- 提取关键指标 (进度/错误/统计数据)
- 实时流式处理
"""

import re
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Optional, Callable, Awaitable
from dataclasses import dataclass, field

import docker
from docker.models.containers import Container

from app.core.database import SessionLocal
from app.models import TaskInstance

logger = logging.getLogger(__name__)


@dataclass
class ParsedLog:
    """解析后的日志数据"""
    timestamp: datetime
    level: str
    message: str
    task_id: Optional[str] = None
    
    # 提取的指标
    pages_crawled: int = 0
    items_scraped: int = 0
    errors_count: int = 0
    
    # 爬虫状态
    spider_status: Optional[str] = None  # started/running/finished/failed
    spider_name: Optional[str] = None


class LogCollector:
    """
    Docker 容器日志采集器
    
    零侵入方式采集 Crawlo 爬虫日志
    """
    
    def __init__(self):
        """初始化采集器"""
        self.docker_client = None
        self.active_collectors: Dict[str, asyncio.Task] = {}
        self._initialized = False
    
    async def initialize(self):
        """初始化"""
        if not self._initialized:
            self.docker_client = docker.from_env()
            self._initialized = True
            logger.info("LogCollector initialized")
    
    async def start_collecting(
        self,
        task_id: str,
        container_id: str,
        callback: Optional[Callable[[ParsedLog], Awaitable[None]]] = None
    ):
        """
        开始采集日志
        
        Args:
            task_id: 任务 ID
            container_id: 容器 ID
            callback: 日志处理回调函数
        """
        await self.initialize()
        
        # 检查是否已在采集
        if task_id in self.active_collectors:
            logger.warning(f"Already collecting logs for task {task_id}")
            return
        
        # 启动异步采集任务
        task = asyncio.create_task(
            self._collect_stream(task_id, container_id, callback)
        )
        self.active_collectors[task_id] = task
        
        logger.info(f"Started log collection for task {task_id}")
    
    async def stop_collecting(self, task_id: str):
        """
        停止采集日志
        
        Args:
            task_id: 任务 ID
        """
        task = self.active_collectors.pop(task_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"Stopped log collection for task {task_id}")
    
    async def _collect_stream(
        self,
        task_id: str,
        container_id: str,
        callback: Optional[Callable[[ParsedLog], Awaitable[None]]] = None
    ):
        """
        流式采集日志
        
        Args:
            task_id: 任务 ID
            container_id: 容器 ID
            callback: 回调函数
        """
        try:
            container = self.docker_client.containers.get(container_id)
            
            # 流式读取日志
            logs = container.logs(
                stream=True,
                follow=True,
                timestamps=True,
                stdout=True,
                stderr=True
            )
            
            for log_line in logs:
                try:
                    # 解析日志
                    parsed = self._parse_log_line(log_line.decode('utf-8'), task_id)
                    
                    if parsed:
                        # 更新数据库
                        await self._update_task_metrics(task_id, parsed)
                        
                        # 调用回调
                        if callback:
                            await callback(parsed)
                
                except Exception as e:
                    logger.error(f"Error processing log line: {e}")
        
        except docker.errors.NotFound:
            logger.error(f"Container {container_id} not found")
        except Exception as e:
            logger.error(f"Log collection failed for task {task_id}: {e}")
    
    def _parse_log_line(self, log_line: str, task_id: str) -> Optional[ParsedLog]:
        """
        解析 Crawlo 日志行
        
        日志格式:
        2024-04-12 10:00:00 [INFO] Spider of_week started
        2024-04-12 10:00:01 [INFO] Crawled 100 pages, 50 items
        2024-04-12 10:00:02 [ERROR] Failed to parse url: xxx
        
        Args:
            log_line: 日志行
            task_id: 任务 ID
            
        Returns:
            解析后的日志对象
        """
        # 匹配时间戳和级别
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\] (.+)'
        match = re.match(pattern, log_line.strip())
        
        if not match:
            return None
        
        timestamp_str, level, message = match.groups()
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        
        parsed = ParsedLog(
            timestamp=timestamp,
            level=level,
            message=message,
            task_id=task_id
        )
        
        # 提取指标
        self._extract_metrics(parsed)
        
        return parsed
    
    def _extract_metrics(self, parsed: ParsedLog):
        """
        从日志消息中提取指标
        
        Args:
            parsed: 解析后的日志对象
        """
        message = parsed.message
        
        # 提取爬虫状态
        if 'Spider' in message and 'started' in message:
            parsed.spider_status = 'started'
            # 提取爬虫名称
            match = re.search(r'Spider (\w+) started', message)
            if match:
                parsed.spider_name = match.group(1)
        
        elif 'Spider' in message and ('closed' in message or 'finished' in message):
            parsed.spider_status = 'finished'
            match = re.search(r'Spider (\w+) (closed|finished)', message)
            if match:
                parsed.spider_name = match.group(1)
        
        # 提取爬取数量
        # "Crawled 100 pages, 50 items"
        pages_match = re.search(r'Crawled (\d+) pages', message)
        if pages_match:
            parsed.pages_crawled = int(pages_match.group(1))
        
        items_match = re.search(r'(\d+) items', message)
        if items_match:
            parsed.items_scraped = int(items_match.group(1))
        
        # 提取错误
        if parsed.level == 'ERROR' or 'error' in message.lower():
            parsed.errors_count = 1
    
    async def _update_task_metrics(self, task_id: str, parsed: ParsedLog):
        """
        更新任务指标到数据库
        
        Args:
            task_id: 任务 ID
            parsed: 解析后的日志对象
        """
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
            
            if not task:
                return
            
            # 更新爬虫名称
            if parsed.spider_name:
                task.spider_name = parsed.spider_name
            
            # 累加指标
            if parsed.pages_crawled > 0:
                task.pages_crawled = (task.pages_crawled or 0) + parsed.pages_crawled
            
            if parsed.items_scraped > 0:
                task.items_scraped = (task.items_scraped or 0) + parsed.items_scraped
            
            if parsed.errors_count > 0:
                task.errors_count = (task.errors_count or 0) + parsed.errors_count
            
            # 更新状态
            if parsed.spider_status == 'started':
                from app.models import TaskStatus
                task.status = TaskStatus.RUNNING
            
            elif parsed.spider_status == 'finished':
                from app.models import TaskStatus
                if parsed.errors_count > 0:
                    task.status = TaskStatus.FAILED
                else:
                    task.status = TaskStatus.SUCCESS
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update task metrics: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def get_recent_logs(self, task_id: str, container_id: str, lines: int = 100) -> str:
        """
        获取最近的日志
        
        Args:
            task_id: 任务 ID
            container_id: 容器 ID
            lines: 日志行数
            
        Returns:
            日志内容
        """
        await self.initialize()
        
        try:
            container = self.docker_client.containers.get(container_id)
            logs = container.logs(tail=lines, timestamps=True)
            return logs.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return f"Error: {str(e)}"
    
    async def cleanup(self):
        """清理资源"""
        logger.info("Cleaning up LogCollector")
        
        for task_id in list(self.active_collectors.keys()):
            await self.stop_collecting(task_id)


# 全局采集器实例
_collector = None


def get_collector() -> LogCollector:
    """获取全局采集器实例"""
    global _collector
    if _collector is None:
        _collector = LogCollector()
    return _collector
