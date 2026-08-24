"""
CrawloDistributedAdapter：分布式模式适配器（Wave D）

将 CrawloPilot 的任务派发转换为 Crawlo 的三种运行模式：
1. standalone：单机内存队列，每个任务独立运行（V1 默认行为）
2. single_node_distributed：单机多 Worker，共享本机 Redis Stream
3. multi_node_distributed：多机共享 Redis，Worker 跨节点消费

适配器职责：
- 根据 distribution_mode 生成 settings override 文件
- 计算 Redis Key 命名空间
- 为执行器构造正确的启动命令（附加 --settings 参数）
- 读取 Crawlo 的 progress:stats 更新指标
"""
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

from app.core.config import settings
from app.core.redis import get_redis, is_redis_available
from app.services.crawlo_settings import (
    build_redis_namespace, build_crawlo_key,
    write_settings_override,
)

logger = logging.getLogger(__name__)


class DistributionMode:
    STANDALONE = "standalone"
    SINGLE_NODE_DISTRIBUTED = "single_node_distributed"
    MULTI_NODE_DISTRIBUTED = "multi_node_distributed"


class CrawloDistributedAdapter:
    """Crawlo 分布式模式适配器"""

    def __init__(self):
        self._redis_url = settings.REDIS_URL

    def prepare_task(
        self,
        task_id,
        spider_name: str,
        project_name: str,
        distribution_mode: str = DistributionMode.STANDALONE,
        shared_redis_url: Optional[str] = None,
        worker_count: int = 1,
    ) -> Dict[str, Any]:
        """为任务准备分布式运行环境。

        Returns:
            {
                "distribution_mode": str,
                "redis_namespace": str or None,
                "settings_file": Path or None,
                "worker_count": int,
                "extra_env": dict,
                "extra_args": list,
            }
        """
        redis_url = shared_redis_url or self._redis_url
        redis_ns = None
        settings_file = None
        extra_env = {}
        extra_args = []

        if distribution_mode == DistributionMode.STANDALONE:
            # V1 行为：无额外配置
            pass

        elif distribution_mode == DistributionMode.SINGLE_NODE_DISTRIBUTED:
            redis_ns = build_redis_namespace(project_name, spider_name)
            if not redis_url:
                raise ValueError("single_node_distributed 模式需要 Redis（REDIS_URL 未配置）")
            settings_file = write_settings_override(
                distribution_mode, redis_url, redis_ns, worker_count, spider_name, project_name)
            extra_args = ["--settings", str(settings_file)]

        elif distribution_mode == DistributionMode.MULTI_NODE_DISTRIBUTED:
            redis_ns = build_redis_namespace(project_name, spider_name)
            if not redis_url:
                raise ValueError("multi_node_distributed 模式需要 Redis（REDIS_URL 未配置）")
            settings_file = write_settings_override(
                distribution_mode, redis_url, redis_ns, worker_count, spider_name, project_name)
            extra_args = ["--settings", str(settings_file)]

        else:
            raise ValueError(f"不支持的 distribution_mode: {distribution_mode}")

        return {
            "distribution_mode": distribution_mode,
            "redis_namespace": redis_ns,
            "settings_file": settings_file,
            "worker_count": worker_count,
            "extra_env": extra_env,
            "extra_args": extra_args,
        }

    def read_progress_stats(self, redis_namespace: str) -> Dict[str, int]:
        """从 Crawlo 的 progress:stats Redis HASH 读取指标。

        Crawlo ProgressAggregator 每 10s 写入一次。
        返回 {"pages_crawled": N, "items_scraped": N, "errors_count": N}
        """
        r = get_redis()
        if not r or not redis_namespace:
            return {}
        try:
            key = build_crawlo_key(redis_namespace, "progress:stats")
            data = r.hgetall(key)
            if not data:
                return {}
            # Crawlo 统计 key 名
            pages = int(data.get("crawlo:response_received_count", data.get("response_received_count", 0)))
            items = int(data.get("crawlo:item_successful_count", data.get("item_successful_count", 0)))
            return {"pages_crawled": pages, "items_scraped": items}
        except Exception as e:
            logger.debug(f"读取 progress:stats 失败: {e}")
            return {}

    def check_shutdown_signal(self, redis_namespace: str) -> bool:
        """检查 Crawlo 的 control:state 是否为 shutdown。

        分布式模式下，Crawlo 协调退出时会设置此信号。
        """
        r = get_redis()
        if not r or not redis_namespace:
            return False
        try:
            key = build_crawlo_key(redis_namespace, "control:state")
            return r.get(key) == "shutdown"
        except Exception:
            return False

    def cleanup(self, settings_file: Optional[Path]):
        """清理 settings override 临时文件"""
        if settings_file and settings_file.exists():
            try:
                settings_file.unlink()
            except OSError:
                pass


# 全局单例
_adapter = CrawloDistributedAdapter()


def get_distributed_adapter() -> CrawloDistributedAdapter:
    return _adapter
