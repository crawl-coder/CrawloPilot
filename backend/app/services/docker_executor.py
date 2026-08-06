"""
Docker 远程执行器（直连节点 Docker API，不依赖 Celery）

执行流程：
1. 连接节点 Docker API（tcp://host:port）
2. 流式构建任务镜像：python:3.10-slim + crawlo + 爬虫代码
3. 创建并启动容器执行入口文件
4. 监控容器状态直到退出，解析日志指标
5. 回写任务状态 / 指标 / 爬虫统计，容器清理
"""

import io
import asyncio
import os
import re
import time
import tarfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass
from threading import Thread

from app.core.database import SessionLocal
from app.models import TaskInstance, TaskStatus, Spider
from app.services.docker_service import DockerService

logger = logging.getLogger(__name__)

# crawlo 版本（与 PyPI 最新保持一致）
CRAWLO_VERSION = "1.7.2"
# 本地 crawlo wheel（纯 Python，安装快），可通过环境变量覆盖
CRAWLO_WHEEL_PATH = os.environ.get(
    "CRAWLO_WHEEL_PATH",
    "/Users/oscar/projects/Crawlo/dist/crawlo-1.7.2-py3-none-any.whl",
)
# pip 国内镜像（默认清华源）
PIP_INDEX_URL = os.environ.get("PIP_INDEX_URL", "https://pypi.tuna.tsinghua.edu.cn/simple")
# 可复用基础镜像（crawlo 运行环境，构建一次后任务镜像秒级叠加）
BASE_IMAGE_TAG = f"crawlopilot/base:{CRAWLO_VERSION}"
# 备用基础镜像（无 wheel 且构建失败时兜底）
BASE_IMAGE_FALLBACK_TAG = "crawlopilot/spider-runner:latest"

# 日志目录（与本地执行器共用，容器清理后仍可读日志）
LOGS_DIR = Path(__file__).parent.parent.parent.parent / "uploads" / "_task_logs"


@dataclass
class DockerTaskConfig:
    """Docker 任务执行配置"""

    task_id: str
    spider_id: str
    spider_name: str
    code_dir: str
    entry_file: Optional[str] = None
    spider_name_to_run: Optional[str] = None
    node_host: str = ""
    node_port: int = 2375
    docker_host: Optional[str] = None  # 显式连接地址（如 unix socket），优先于 tcp://host:port
    timeout: int = 3600
    memory_limit: str = "512m"
    cpu_limit: float = 1.0


def _build_context_tar(code_dir: str, base_tag: str) -> bytes:
    """生成任务镜像构建上下文（基于已缓存的基础镜像 + 爬虫代码）"""
    dockerfile = (
        f"FROM {base_tag}\n"
        f"WORKDIR /app\n"
        f"COPY . /app\n"
        f"RUN if [ -f /app/requirements.txt ]; then "
        f"pip install --no-cache-dir -r /app/requirements.txt -i {PIP_INDEX_URL}; fi\n"
    )

    buf = io.BytesIO()
    now = int(time.time())
    with tarfile.open(fileobj=buf, mode="w") as tar:
        df_bytes = dockerfile.encode("utf-8")
        info = tarfile.TarInfo("Dockerfile")
        info.size = len(df_bytes)
        info.mtime = now
        tar.addfile(info, io.BytesIO(df_bytes))

        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "logs")]
            for fname in files:
                if fname.endswith(".pyc"):
                    continue
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, code_dir)
                try:
                    with open(full, "rb") as f:
                        data = f.read()
                except OSError:
                    continue
                ti = tarfile.TarInfo(rel)
                ti.size = len(data)
                ti.mtime = now
                ti.mode = 0o644
                tar.addfile(ti, io.BytesIO(data))

    return buf.getvalue()


def _build_base_context_tar() -> bytes:
    """生成基础镜像构建上下文（python + crawlo + aiomysql）

    优先使用本地 wheel（无需编译，秒级安装），否则 pip 安装并走国内镜像。
    """
    if CRAWLO_WHEEL_PATH and os.path.exists(CRAWLO_WHEEL_PATH):
        install_cmd = f"RUN pip install --no-cache-dir /tmp/crawlo.whl aiomysql -i {PIP_INDEX_URL}"
        wheel_name = os.path.basename(CRAWLO_WHEEL_PATH)
    else:
        install_cmd = (
            f"RUN pip install --no-cache-dir crawlo=={CRAWLO_VERSION} aiomysql "
            f"-i {PIP_INDEX_URL}"
        )
        wheel_name = None

    dockerfile = (
        f"FROM python:3.10-slim\n"
        f"{install_cmd}\n"
    )
    buf = io.BytesIO()
    now = int(time.time())
    with tarfile.open(fileobj=buf, mode="w") as tar:
        df_bytes = dockerfile.encode("utf-8")
        info = tarfile.TarInfo("Dockerfile")
        info.size = len(df_bytes)
        info.mtime = now
        tar.addfile(info, io.BytesIO(df_bytes))

        if wheel_name:
            with open(CRAWLO_WHEEL_PATH, "rb") as f:
                wheel_data = f.read()
            wi = tarfile.TarInfo("/tmp/crawlo.whl")
            wi.size = len(wheel_data)
            wi.mtime = now
            wi.mode = 0o644
            tar.addfile(wi, io.BytesIO(wheel_data))
    return buf.getvalue()


def _ensure_base_image(docker: DockerService) -> str:
    """
    确保节点上存在 crawlo 基础镜像，返回实际使用的基础镜像 tag
    - 优先 crawlopilot/base:1.7.2（wheel 安装，快）
    - 缺失时构建；构建失败则回退 crawlopilot/spider-runner:latest
    """
    images = docker.list_images()
    for img in images:
        if BASE_IMAGE_TAG in (img.get("tags") or []):
            logger.info(f"基础镜像已存在: {BASE_IMAGE_TAG}")
            return BASE_IMAGE_TAG

    logger.info(f"构建基础镜像: {BASE_IMAGE_TAG}")
    try:
        docker.build_image_from_tar(_build_base_context_tar(), BASE_IMAGE_TAG)
        return BASE_IMAGE_TAG
    except Exception as e:
        logger.warning(f"基础镜像构建失败: {e}，回退使用 {BASE_IMAGE_FALLBACK_TAG}")
        return BASE_IMAGE_FALLBACK_TAG


def parse_crawler_metrics(log_text: str) -> tuple:
    """从容器日志解析 pages/items/errors（兼容 mock 与 crawlo 统计格式）"""
    pages = items = errors = 0
    if not log_text:
        return pages, items, errors

    crawled_pattern = re.compile(
        r"(?:Crawled|crawled|已爬取)\s+(\d+)\s+(?:pages?|页).*?(\d+)\s+(?:items?|条)",
        re.IGNORECASE,
    )
    alt_pattern = re.compile(r"(\d+)\s+pages?.*?(\d+)\s+items?", re.IGNORECASE)
    # crawlo 1.7.x 统计 key 带 crawlo: 前缀，兼容旧格式
    crawlo_items_pattern = re.compile(r"['\"]crawlo:item_successful_count['\"]\s*:\s*(\d+)")
    crawlo_items_legacy = re.compile(r"['\"]item_successful_count['\"]\s*:\s*(\d+)")
    crawlo_pages_pattern = re.compile(r"['\"]crawlo:response_received_count['\"]\s*:\s*(\d+)")
    crawlo_pages_legacy = re.compile(r"['\"]response_received_count['\"]\s*:\s*(\d+)")
    error_pattern = re.compile(r"\[(?:ERROR|WARNING)\]", re.IGNORECASE)

    matches = list(crawled_pattern.finditer(log_text))
    if matches:
        pages = int(matches[-1].group(1))
        items = int(matches[-1].group(2))
    else:
        alt_matches = list(alt_pattern.finditer(log_text))
        if alt_matches:
            pages = int(alt_matches[-1].group(1))
            items = int(alt_matches[-1].group(2))

    if not items:
        m = crawlo_items_pattern.search(log_text)
        if not m:
            m = crawlo_items_legacy.search(log_text)
        if m:
            items = int(m.group(1))
    if not pages:
        m = crawlo_pages_pattern.search(log_text)
        if not m:
            m = crawlo_pages_legacy.search(log_text)
        if m:
            pages = int(m.group(1))

    errors = len(error_pattern.findall(log_text))
    return pages, items, errors


class DockerExecutor:
    """Docker 直连执行器"""

    RETENTION_SECONDS = 300

    def __init__(self):
        # task_id -> {"docker": DockerService, "container_id": str, "image": str}
        self.active_tasks: Dict[str, Dict] = {}

    def _docker_for_node(self, node_host: str, node_port: int) -> DockerService:
        return DockerService(docker_host=f"tcp://{node_host}:{node_port}")

    async def execute_task(self, config: DockerTaskConfig) -> str:
        """在远程 Docker 节点上执行爬虫任务（阻塞操作放入线程池，避免阻塞事件循环）"""
        return await asyncio.to_thread(self._execute_sync, config)

    def _execute_sync(self, config: DockerTaskConfig) -> str:
        """同步执行（镜像构建/容器操作耗时较长，在线程中运行）"""
        logger.info(
            f"执行 Docker 远程任务 {config.task_id}: {config.spider_name} "
            f"-> {config.node_host}:{config.node_port}"
        )

        try:
            docker = DockerService(
                docker_host=config.docker_host
                or f"tcp://{config.node_host}:{config.node_port}"
            )
            if not docker.ping():
                raise ConnectionError(
                    f"无法连接节点 Docker API: {config.node_host}:{config.node_port}"
                )

            # 1. 确保基础镜像（crawlo 运行环境）已存在
            base_tag = _ensure_base_image(docker)

            # 2. 流式构建任务镜像（基础镜像 + 爬虫代码）
            tag = f"crawlopilot-task-{config.task_id}"
            tar_bytes = _build_context_tar(config.code_dir, base_tag)
            docker.build_image_from_tar(tar_bytes, tag)

            # 3. 创建并启动容器
            cmd = ["python", config.entry_file or "run.py"]
            env = {
                "TASK_ID": config.task_id,
                "SPIDER_NAME": config.spider_name_to_run or config.spider_name,
                "PYTHONUNBUFFERED": "1",
                "PYTHONIOENCODING": "utf-8",
            }
            container = docker.create_container(
                image=tag,
                name=f"task-{str(config.task_id)[:8]}",
                entrypoint=["python", config.entry_file or "run.py"],
                command=cmd,
                environment=env,
                resource_limits={
                    "mem_limit": config.memory_limit,
                    "cpu_limit": str(config.cpu_limit),
                },
                restart_policy="no",
            )
            container_id = container["id"]
            self.active_tasks[config.task_id] = {
                "docker": docker,
                "container_id": container_id,
                "image": tag,
            }

            # 4. 更新数据库状态
            self._update_task_started(config.task_id, container_id)

            # 5. 启动监控线程
            Thread(
                target=self._monitor_process,
                args=(config, container_id),
                daemon=True,
                name=f"docker-monitor-{config.task_id}",
            ).start()

            logger.info(f"Docker 任务已启动: {config.task_id}, container={container_id[:12]}")
            return config.task_id

        except Exception as e:
            logger.error(f"Docker 任务启动失败: {e}")
            self._update_task_completion(
                config.task_id,
                TaskStatus.FAILED,
                datetime.utcnow(),
                0, 0, 0,
                error_message=str(e),
            )
            raise

    def _monitor_process(self, config: DockerTaskConfig, container_id: str):
        """监控容器直到退出"""
        entry = self.active_tasks.get(config.task_id)
        if not entry:
            return
        docker = entry["docker"]

        try:
            deadline = time.time() + config.timeout
            exit_code = None
            status = TaskStatus.TIMEOUT

            while time.time() < deadline:
                try:
                    info = docker.get_container(container_id)
                except Exception:
                    info = None
                if info is None:
                    # 容器已不存在
                    status = TaskStatus.FAILED
                    break
                if info.get("status") == "exited":
                    exit_code = info.get("exit_code")
                    status = TaskStatus.SUCCESS if exit_code == 0 else TaskStatus.FAILED
                    break
                time.sleep(5)

            if status == TaskStatus.TIMEOUT:
                logger.warning(f"[{config.task_id}] 容器运行超时，强制停止")
                try:
                    docker.stop_container(container_id, timeout=10)
                except Exception:
                    pass

            # 收集日志与指标
            logs_text = ""
            try:
                logs_text = docker.get_container_logs(container_id, tail=10000)
            except Exception as e:
                logger.warning(f"[{config.task_id}] 获取容器日志失败: {e}")

            pages, items, errors = parse_crawler_metrics(logs_text)

            self._update_task_completion(
                config.task_id,
                status,
                datetime.utcnow(),
                pages,
                items,
                errors,
                container_id=container_id,
                logs=logs_text,
            )
            logger.info(
                f"[{config.task_id}] Docker 任务完成: status={status.value}, "
                f"pages={pages}, items={items}, errors={errors}"
            )

            # 清理容器（镜像保留以便复用）
            try:
                docker.remove_container(container_id, force=True)
            except Exception as e:
                logger.warning(f"[{config.task_id}] 清理容器失败: {e}")

            Thread(
                target=self._delayed_cleanup,
                args=(config.task_id,),
                daemon=True,
            ).start()

        except Exception as e:
            logger.error(f"[{config.task_id}] Docker 任务监控异常: {e}")
            self._update_task_completion(
                config.task_id,
                TaskStatus.FAILED,
                datetime.utcnow(),
                0, 0, 0,
                container_id=container_id,
                error_message=str(e),
            )

    async def stop_task(self, task_id: str) -> bool:
        """停止 Docker 任务"""
        entry = self.active_tasks.get(task_id)
        if not entry:
            logger.warning(f"未找到 Docker 任务: {task_id}")
            return False

        try:
            docker = entry["docker"]
            cid = entry["container_id"]
            docker.stop_container(cid, timeout=10)
            logs_text = ""
            try:
                logs_text = docker.get_container_logs(cid, tail=10000)
            except Exception:
                pass
            docker.remove_container(cid, force=True)
            self._update_task_completion(
                task_id,
                TaskStatus.CANCELLED,
                datetime.utcnow(),
                0, 0, 0,
                container_id=cid,
                logs=logs_text,
            )
            Thread(target=self._delayed_cleanup, args=(task_id,), daemon=True).start()
            return True
        except Exception as e:
            logger.error(f"停止 Docker 任务失败: {e}")
            return False

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取 Docker 任务状态"""
        entry = self.active_tasks.get(task_id)
        if entry:
            try:
                info = entry["docker"].get_container(entry["container_id"])
                if info:
                    return {
                        "task_id": task_id,
                        "status": info.get("status"),
                        "container_id": entry["container_id"],
                        "exit_code": info.get("exit_code"),
                        "started_at": info.get("created"),
                    }
            except Exception as e:
                logger.warning(f"获取容器状态失败: {e}")

        # 从数据库兜底
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == int(task_id)).first() \
                if str(task_id).isdigit() else None
            if task:
                return {
                    "task_id": task_id,
                    "status": task.status.value if hasattr(task.status, "value") else str(task.status),
                    "container_id": task.container_id,
                    "pages_crawled": task.pages_crawled or 0,
                    "items_scraped": task.items_scraped or 0,
                    "errors_count": task.errors_count or 0,
                    "duration": float(task.duration) if task.duration is not None else None,
                }
        except Exception as e:
            logger.error(f"查询 Docker 任务状态失败: {e}")
        finally:
            db.close()
        return None

    def get_task_logs(self, task_id: str, tail: int = 100) -> str:
        """获取 Docker 任务日志"""
        entry = self.active_tasks.get(task_id)
        if entry:
            try:
                logs = entry["docker"].get_container_logs(entry["container_id"], tail=tail)
                if logs:
                    return logs
            except Exception:
                pass

        # 容器清理后读取本地落盘日志
        log_file = LOGS_DIR / f"task_{task_id}.log"
        if log_file.exists():
            try:
                lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
                return "\n".join(lines[-tail:])
            except Exception:
                pass
        return "无日志（容器可能已清理）"

    def _update_task_started(self, task_id: str, container_id: str):
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == int(task_id)).first()
            if task:
                task.status = TaskStatus.RUNNING
                task.deploy_mode = "docker"
                task.container_id = container_id
                task.started_at = task.started_at or datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.error(f"更新 Docker 任务启动状态失败: {e}")
            db.rollback()
        finally:
            db.close()

    def _update_task_completion(
        self,
        task_id: str,
        status: TaskStatus,
        finished_at: datetime,
        pages_crawled: int = 0,
        items_scraped: int = 0,
        errors_count: int = 0,
        container_id: str = None,
        logs: str = None,
        error_message: str = None,
    ):
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == int(task_id)).first()
            if task:
                task.status = status
                task.finished_at = finished_at
                task.pages_crawled = pages_crawled
                task.items_scraped = items_scraped
                task.errors_count = errors_count
                task.deploy_mode = "docker"
                if container_id:
                    task.container_id = container_id
                if error_message:
                    task.error_message = error_message
                if task.started_at:
                    task.duration = (finished_at - task.started_at).total_seconds()
                db.commit()

                # 落盘日志，容器清理后仍可查询
                if logs:
                    try:
                        LOGS_DIR.mkdir(parents=True, exist_ok=True)
                        (LOGS_DIR / f"task_{task_id}.log").write_text(logs, encoding="utf-8")
                    except Exception as e:
                        logger.warning(f"写 Docker 日志失败: {e}")

                self._update_spider_stats(db, task, status)
                logger.info(
                    f"任务 {task_id} 完成: status={status.value}, "
                    f"pages={pages_crawled}, items={items_scraped}, "
                    f"errors={errors_count}, duration={task.duration}s"
                )
        except Exception as e:
            logger.error(f"更新 Docker 任务完成信息失败: {e}")
            db.rollback()
        finally:
            db.close()

    def _update_spider_stats(self, db, task: TaskInstance, status: TaskStatus):
        """同步爬虫运行统计"""
        try:
            if not task.spider_id:
                return
            spider = db.query(Spider).filter(Spider.id == task.spider_id).first()
            if not spider:
                return
            spider.last_run_at = datetime.utcnow()
            spider.last_run_status = status.value
            if status == TaskStatus.SUCCESS:
                spider.success_count = (spider.success_count or 0) + 1
            elif status in (TaskStatus.FAILED, TaskStatus.TIMEOUT):
                spider.error_count = (spider.error_count or 0) + 1
            db.commit()
            logger.info(f"任务 {task.id} 已更新爬虫统计: {spider.name} -> {status.value}")
        except Exception as e:
            logger.error(f"更新爬虫统计失败: {e}")
            db.rollback()

    def _delayed_cleanup(self, task_id: str):
        time.sleep(self.RETENTION_SECONDS)
        self.active_tasks.pop(task_id, None)
        logger.debug(f"[{task_id}] 已从活动任务中清理")


# 全局实例
_docker_executor: Optional[DockerExecutor] = None


def get_docker_executor() -> DockerExecutor:
    """获取全局 Docker 执行器实例"""
    global _docker_executor
    if _docker_executor is None:
        _docker_executor = DockerExecutor()
    return _docker_executor
