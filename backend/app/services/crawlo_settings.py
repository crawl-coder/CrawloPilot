"""
Crawlo settings override 生成器 + Redis Key 命名空间管理（Wave D）

根据 distribution_mode 生成 Crawlo 运行时需要的 settings override 文件内容。
Crawlo 通过 `--settings <file>` 参数读取 override 配置。

命名空间规则：redis_namespace = f"{project_name}:{spider_name}"
Crawlo 内部所有 Redis Key 格式：crawlo:{redis_namespace}:{suffix}
"""
import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Crawlo Redis Key 后缀（对照 v2-design-revised.md 附录 14.2）
CRAWLO_KEY_SUFFIXES = [
    "stream:tasks",        # Redis Stream 任务队列
    "control:state",       # 控制状态（shutdown 等）
    "registry:workers",    # Worker 注册表
    "progress:stats",      # 进度统计 HASH
    "channel:control",     # Pub/Sub 控制通道
    "dead_letter:tasks",   # 死信队列
    "dedup:seen",          # 种子去重 SET
    "rate_limit:{domain}", # 限速令牌桶（Lua）
]


def build_redis_namespace(project_name: str, spider_name: str) -> str:
    """生成 Crawlo Redis Key 命名空间。

    格式：{project_name}:{spider_name}
    Crawlo 内部拼接为 crawlo:{namespace}:{suffix}
    """
    # 清理非法字符（Redis Key 不宜含空格/特殊字符）
    safe = lambda s: re.sub(r'[^a-zA-Z0-9_\-]', '_', s)
    return f"{safe(project_name)}:{safe(spider_name)}"


def build_crawlo_key(redis_namespace: str, suffix: str) -> str:
    """拼接 Crawlo 完整 Redis Key"""
    return f"crawlo:{redis_namespace}:{suffix}"


def generate_settings_override(
    distribution_mode: str,
    redis_url: Optional[str] = None,
    redis_namespace: Optional[str] = None,
    worker_count: int = 1,
    spider_name: Optional[str] = None,
    project_name: Optional[str] = None,
) -> str:
    """生成 Crawlo settings override 文件内容（INI 格式）。

    Args:
        distribution_mode: standalone / single_node_distributed / multi_node_distributed
        redis_url: Redis 连接地址（distributed 模式必需）
        redis_namespace: Redis Key 命名空间（distributed 模式必需）
        worker_count: 每节点 Worker 进程数（模式 B/C）
        spider_name: 爬虫名称
        project_name: 项目名称

    Returns:
        settings override 文件内容（字符串）
    """
    lines = ["# CrawloPilot 自动生成的 settings override（请勿手动编辑）"]

    if distribution_mode == "standalone":
        lines.append("RUN_MODE = standalone")
        lines.append("QUEUE_TYPE = memory")
        # standalone 不需要 Redis

    elif distribution_mode == "single_node_distributed":
        lines.append("RUN_MODE = distributed")
        lines.append("QUEUE_TYPE = redis_stream")
        if redis_url:
            # Crawlo 使用分散配置而非 REDIS_URL，但 settings override 支持 URL 形式
            lines.append(f"REDIS_URL = {redis_url}")
        if redis_namespace:
            lines.append(f"PROJECT_NAME = {redis_namespace}")

    elif distribution_mode == "multi_node_distributed":
        lines.append("RUN_MODE = distributed")
        lines.append("QUEUE_TYPE = redis_stream")
        if redis_url:
            lines.append(f"REDIS_URL = {redis_url}")
        if redis_namespace:
            lines.append(f"PROJECT_NAME = {redis_namespace}")

    else:
        raise ValueError(f"不支持的 distribution_mode: {distribution_mode}")

    if spider_name:
        lines.append(f"SPIDER_NAME = {spider_name}")

    return "\n".join(lines) + "\n"


def write_settings_override(
    distribution_mode: str,
    redis_url: Optional[str] = None,
    redis_namespace: Optional[str] = None,
    worker_count: int = 1,
    spider_name: Optional[str] = None,
    project_name: Optional[str] = None,
) -> Path:
    """生成 settings override 临时文件，返回文件路径。

    调用方负责清理临时文件（或由任务 workspace 生命周期管理）。
    """
    content = generate_settings_override(
        distribution_mode, redis_url, redis_namespace,
        worker_count, spider_name, project_name,
    )
    # 写入临时文件
    fd, path = tempfile.mkstemp(prefix="crawlo_settings_", suffix=".ini")
    with open(path, "w") as f:
        f.write(content)
    logger.info(f"settings override 已生成: {path} (mode={distribution_mode})")
    return Path(path)
