"""
本地爬虫执行器（非Docker模式）

支持通过 subprocess 在本地运行爬虫，不依赖 Docker。
管理进程生命周期：启动/停止/暂停(暂停进程)/恢复/状态查询/日志获取。
支持日志持久化到文件，以及爬虫指标自动统计。
"""

import os
import asyncio
import sys
import re
import subprocess
import signal
import logging
import uuid
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from threading import Lock, Thread

from app.core.database import SessionLocal
from app.models import TaskInstance, TaskStatus, Spider
from app.core.config import settings

logger = logging.getLogger(__name__)

# 日志目录
LOGS_DIR = Path(settings.UPLOAD_DIR) / "_task_logs"


@dataclass
class LocalTaskConfig:
    """本地任务执行配置"""

    task_id: str
    spider_id: str
    spider_name: str
    
    # 代码目录（必填）
    code_dir: str
    
    # 入口文件（如 run.py），可选，不指定则尝试自动发现
    entry_file: Optional[str] = None
    
    # 爬虫名称 (用于 crawlo run spider_name)
    spider_name_to_run: Optional[str] = None
    
    # 超时配置
    timeout: int = 3600  # 1小时

    # 资源限制（MB / CPU 核数，None=不限制）
    memory_limit: Optional[int] = None
    cpu_limit: Optional[float] = None
    
    # 环境变量
    extra_env: Dict[str, str] = field(default_factory=dict)


class LocalSpiderProcess:
    """单个本地爬虫进程管理器"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.process: Optional[subprocess.Popen] = None
        self.status = TaskStatus.PENDING
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None
        self._log_file_path: Optional[str] = None
        self._log_file: object = None
        self._lock = Lock()
        
        # 爬虫指标
        self.pages_crawled: int = 0
        self.items_scraped: int = 0
        self.errors_count: int = 0

    def start(self, config: LocalTaskConfig):
        """启动爬虫进程"""
        with self._lock:
            code_dir = Path(config.code_dir)
            if not code_dir.exists():
                raise FileNotFoundError(f"代码目录不存在: {code_dir}")

            # 准备日志文件
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            self._log_file_path = str(LOGS_DIR / f"task_{self.task_id}.log")
            self._log_file = open(self._log_file_path, 'w', encoding='utf-8')

            # 确定执行命令
            cmd = self._build_command(config, code_dir)
            logger.info(f"[{self.task_id}] 启动命令: {' '.join(cmd)}")

            # 构建环境变量
            env = os.environ.copy()
            env.update({
                'TASK_ID': config.task_id,
                'SPIDER_NAME': config.spider_name,
                'PYTHONUNBUFFERED': '1',  # 确保实时输出
                'PYTHONIOENCODING': 'utf-8',
            })
            env.update(config.extra_env)

            try:
                # 资源限制（RLIMIT）：memory_limit 如 "256m"/"1g" → RLIMIT_AS，
                # cpu_limit 核 → 软限制用 RLIMIT_CPU（秒）近似
                def _set_limits():
                    # 尽力而为：个别平台（如 macOS RLIMIT_AS）不支持时
                    # 跳过对应限制，绝不因限制设置失败而阻塞任务启动。
                    try:
                        import resource
                        if config.memory_limit:
                            mem = str(config.memory_limit).strip().lower()
                            mult = 1024 * 1024
                            if mem.endswith("g"):
                                mult = 1024 ** 3
                                mem = mem[:-1]
                            elif mem.endswith("m"):
                                mem = mem[:-1]
                            try:
                                bytes_limit = int(float(mem) * mult)
                            except (TypeError, ValueError):
                                bytes_limit = None
                            if bytes_limit:
                                resource.setrlimit(
                                    resource.RLIMIT_AS, (bytes_limit, bytes_limit)
                                )
                        if config.cpu_limit:
                            cpu_secs = int(float(config.cpu_limit) * 3600)
                            resource.setrlimit(
                                resource.RLIMIT_CPU, (cpu_secs, cpu_secs + 60)
                            )
                    except (ValueError, OSError) as e:
                        # RLIMIT_AS 在 macOS 上可能让子进程无法启动，跳过
                        logger.warning(f"资源限制设置被跳过: {e}")

                self.process = subprocess.Popen(
                    cmd,
                    cwd=str(code_dir),
                    env=env,
                    preexec_fn=_set_limits if hasattr(os, "fork") else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1,  # 行缓冲
                    start_new_session=True,  # 独立进程组，暂停/停止可覆盖子进程
                )
                self.status = TaskStatus.RUNNING
                self.started_at = datetime.utcnow()
                logger.info(f"[{self.task_id}] 进程已启动, PID={self.process.pid}")

            except Exception as e:
                self.status = TaskStatus.FAILED
                if self._log_file:
                    self._log_file.write(f"[ERROR] 进程启动失败: {e}\n")
                    self._log_file.close()
                logger.error(f"[{self.task_id}] 进程启动失败: {e}")
                raise

    def _build_command(self, config: LocalTaskConfig, code_dir: Path) -> List[str]:
        """构建执行命令"""
        entry_file = config.entry_file
        spider_name_to_run = config.spider_name_to_run

        # 优先使用指定的入口文件
        if entry_file:
            entry_path = code_dir / entry_file
            if entry_path.exists():
                if str(entry_file).endswith('.py'):
                    return [sys.executable, str(entry_file)]
                elif str(entry_file).endswith('.sh'):
                    return ['bash', str(entry_file)]
                else:
                    return [sys.executable, str(entry_file)]

        # 尝试使用 crawlo 命令
        if spider_name_to_run:
            # 尝试 crawlo run
            try:
                subprocess.run(
                    ['crawlo', '--version'],
                    capture_output=True, timeout=5
                )
                return ['crawlo', 'run', spider_name_to_run]
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        # 尝试自动发现 run.py
        for candidate in ['run.py', 'main.py', 'crawl.py', 'start.py']:
            candidate_path = code_dir / candidate
            if candidate_path.exists():
                return [sys.executable, candidate]

        # 最后直接执行 crawlo run
        return [sys.executable, '-c', f"""
import asyncio, sys
sys.path.insert(0, '.')
from crawlo.crawler import CrawlerProcess
asyncio.run(CrawlerProcess().crawl('{spider_name_to_run or config.spider_name}'))
"""]

    def stop(self, timeout: int = 10) -> bool:
        """停止进程"""
        with self._lock:
            if not self.process:
                return False

            try:
                pid = self.process.pid
                if pid is None:
                    return False

                # 先发送 SIGTERM
                logger.info(f"[{self.task_id}] 发送 SIGTERM 到 PID={pid}")
                if sys.platform == 'win32':
                    self.process.terminate()
                else:
                    os.killpg(pid, signal.SIGTERM)

                try:
                    self.process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # 超时则强制 kill
                    logger.warning(f"[{self.task_id}] 进程未响应, 强制终止")
                    if sys.platform == 'win32':
                        self.process.kill()
                    else:
                        os.killpg(pid, signal.SIGKILL)
                    self.process.wait(timeout=5)

                self.status = TaskStatus.CANCELLED
                self.finished_at = datetime.utcnow()
                logger.info(f"[{self.task_id}] 进程已停止")
                
                # 关闭日志文件
                self._close_log_file()
                return True

            except Exception as e:
                logger.error(f"[{self.task_id}] 停止进程失败: {e}")
                return False

    def get_status(self) -> Dict:
        """获取进程状态"""
        with self._lock:
            if not self.process:
                return {
                    'task_id': self.task_id,
                    'status': self.status.value,
                    'pid': None,
                    'exit_code': None,
                    'started_at': self.started_at.isoformat() if self.started_at else None,
                    'finished_at': self.finished_at.isoformat() if self.finished_at else None,
                }

            poll_result = self.process.poll()
            exit_code = poll_result

            if poll_result is not None:
                # 进程已结束
                if self.status not in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    self.finished_at = datetime.utcnow()
                    if poll_result == 0:
                        self.status = TaskStatus.SUCCESS
                    else:
                        self.status = TaskStatus.FAILED

            return {
                'task_id': self.task_id,
                'status': self.status.value,
                'pid': self.process.pid,
                'exit_code': exit_code,
                'started_at': self.started_at.isoformat() if self.started_at else None,
                'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            }

    def _read_stdout_to_logfile(self):
        """持续读取进程 stdout 并写入日志文件（在单独线程中运行）"""
        try:
            if not self.process or not self.process.stdout:
                return
            for line in iter(self.process.stdout.readline, ''):
                if not line:
                    break
                if self._log_file and not self._log_file.closed:
                    self._log_file.write(line)
                    self._log_file.flush()
                # 实时广播日志行到 WebSocket 客户端
                try:
                    from app.services.log_broadcaster import get_log_broadcaster
                    get_log_broadcaster().broadcast(self.task_id, line)
                except Exception:
                    pass
        except (ValueError, OSError) as e:
            logger.debug(f"[{self.task_id}] stdout 读取结束: {e}")
        except Exception as e:
            logger.error(f"[{self.task_id}] stdout 读取异常: {e}")

    def _collect_remaining_output(self):
        """收集进程结束后的剩余输出"""
        try:
            if self.process and self.process.stdout:
                remaining = self.process.stdout.read()
                if remaining:
                    if self._log_file and not self._log_file.closed:
                        self._log_file.write(remaining)
                        self._log_file.flush()
        except Exception:
            pass

    def _close_log_file(self):
        """关闭日志文件"""
        try:
            if self._log_file and not self._log_file.closed:
                self._log_file.close()
        except Exception:
            pass

    def get_logs(self, tail: int = 100) -> str:
        """获取进程日志（从日志文件读取）"""
        # 先收集当前缓冲区的内容
        self._collect_remaining_output()
        
        if self._log_file_path and os.path.exists(self._log_file_path):
            try:
                with open(self._log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                recent = lines[-tail:] if len(lines) > tail else lines
                return ''.join(recent)
            except Exception as e:
                logger.error(f"[{self.task_id}] 读取日志文件失败: {e}")
                return f"读取日志失败: {e}"
        
        return ""

    def parse_metrics_from_logs(self):
        """从日志文件中解析爬虫指标"""
        if not self._log_file_path or not os.path.exists(self._log_file_path):
            return
        
        try:
            # 确保日志文件已刷新
            self._close_log_file()
            
            with open(self._log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # 重新打开日志文件以供后续写入
            self._log_file = open(self._log_file_path, 'a', encoding='utf-8')
            
            # 匹配 "Crawled X pages, Y items" 格式
            crawled_pattern = re.compile(
                r'(?:Crawled|crawled|已爬取)\s+(\d+)\s+(?:pages?|页).*?(\d+)\s+(?:items?|条)',
                re.IGNORECASE
            )
            # 匹配 "X pages, Y items" 格式
            alt_pattern = re.compile(r'(\d+)\s+pages?.*?(\d+)\s+items?', re.IGNORECASE)
            # 匹配 crawlo 统计 dict 格式: 'crawlo:item_successful_count': 42（兼容旧格式无前缀）
            crawlo_items_pattern = re.compile(r"['\"]crawlo:item_successful_count['\"]\s*:\s*(\d+)")
            crawlo_items_legacy = re.compile(r"['\"]item_successful_count['\"]\s*:\s*(\d+)")
            crawlo_pages_pattern = re.compile(r"['\"]crawlo:response_received_count['\"]\s*:\s*(\d+)")
            crawlo_pages_legacy = re.compile(r"['\"]response_received_count['\"]\s*:\s*(\d+)")
            # 匹配错误计数: ERROR/WARNING/error
            error_pattern = re.compile(r'\[(?:ERROR|WARNING)\]', re.IGNORECASE)
            
            # 找最后一行的统计（通常是最终统计）
            matches = list(crawled_pattern.finditer(content))
            if matches:
                last_match = matches[-1]
                self.pages_crawled = int(last_match.group(1))
                self.items_scraped = int(last_match.group(2))
            else:
                # 尝试 alt 模式
                alt_matches = list(alt_pattern.finditer(content))
                if alt_matches:
                    last_match = alt_matches[-1]
                    self.pages_crawled = int(last_match.group(1))
                    self.items_scraped = int(last_match.group(2))

            # 兼容 crawlo 统计 dict 格式（真实爬虫日志）
            if not self.items_scraped:
                m = crawlo_items_pattern.search(content)
                if not m:
                    m = crawlo_items_legacy.search(content)
                if m:
                    self.items_scraped = int(m.group(1))
            if not self.pages_crawled:
                m = crawlo_pages_pattern.search(content)
                if not m:
                    m = crawlo_pages_legacy.search(content)
                if m:
                    self.pages_crawled = int(m.group(1))
            
            # 统计错误数
            self.errors_count = len(error_pattern.findall(content))
            
            logger.info(
                f"[{self.task_id}] 指标解析: pages={self.pages_crawled}, "
                f"items={self.items_scraped}, errors={self.errors_count}"
            )
        except Exception as e:
            logger.error(f"[{self.task_id}] 指标解析失败: {e}")

    def poll(self) -> Optional[int]:
        """检查进程是否已退出，返回退出码或 None"""
        if self.process:
            return self.process.poll()
        return None

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def exit_code(self) -> Optional[int]:
        if self.process:
            return self.process.poll()
        return None


class LocalExecutor:
    """
    本地爬虫执行器

    管理多个本地爬虫进程，提供与 TaskExecutor 兼容的接口。
    当 Docker 不可用时自动使用此执行器。
    
    特性：
    - 进程生命周期管理（启动/停止/暂停/恢复）
    - 日志持久化到文件
    - 自动爬虫指标统计（pages/items/errors/duration）
    - 进程完成后自动更新数据库状态
    """

    # 进程完成后在 active_tasks 中保留的时间（秒）
    RETENTION_SECONDS = 300  # 5分钟

    def __init__(self):
        self.active_tasks: Dict[str, LocalSpiderProcess] = {}
        self._initialized = False

    async def initialize(self):
        """初始化执行器"""
        if not self._initialized:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            logger.info("LocalExecutor 初始化完成（本地进程模式）")
            self._initialized = True

    async def execute_task(self, config: LocalTaskConfig) -> str:
        """
        执行本地爬虫任务

        Args:
            config: 本地任务配置

        Returns:
            任务 ID
        """
        await self.initialize()

        logger.info(f"执行本地任务 {config.task_id}: {config.spider_name}")

        # 创建进程管理器
        process = LocalSpiderProcess(config.task_id)

        try:
            # 运行前安装项目依赖（requirements.txt，如存在）
            await asyncio.to_thread(self._install_requirements, config.code_dir)

            process.start(config)
            self.active_tasks[config.task_id] = process

            # 启动 stdout 读取线程（持续将输出写入日志文件）
            stdout_thread = Thread(
                target=process._read_stdout_to_logfile,
                daemon=True,
                name=f"stdout-{config.task_id}"
            )
            stdout_thread.start()

            # 更新数据库状态
            self._update_task_status(
                config.task_id,
                TaskStatus.RUNNING,
                process_id=process.process.pid if process.process else None
            )

            # 启动进程监控线程（等待进程结束后更新数据库）
            monitor_thread = Thread(
                target=self._monitor_process,
                args=(config.task_id, process, config.timeout),
                daemon=True,
                name=f"monitor-{config.task_id}"
            )
            monitor_thread.start()

            logger.info(f"本地任务已启动: {config.task_id}, PID={process.process.pid if process.process else 'N/A'}")
            return config.task_id

        except Exception as e:
            logger.error(f"本地任务启动失败: {e}")
            self._update_task_status(
                config.task_id,
                TaskStatus.FAILED,
                error_message=str(e)
            )
            raise

    def _install_requirements(self, code_dir: str):
        """安装爬虫项目依赖（requirements.txt），避免运行时缺库"""
        req_file = os.path.join(code_dir, "requirements.txt")
        if not os.path.exists(req_file):
            return
        logger.info(f"检测到 requirements.txt，安装依赖: {req_file}")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", req_file,
                 "-i", os.environ.get("PIP_INDEX_URL", "https://pypi.tuna.tsinghua.edu.cn/simple")],
                timeout=600,
                check=True,
            )
            logger.info("项目依赖安装完成")
        except Exception as e:
            logger.error(f"项目依赖安装失败: {e}")
            raise RuntimeError(f"requirements.txt 依赖安装失败: {e}") from e

    def _monitor_process(self, task_id: str, process: LocalSpiderProcess, timeout: int):
        """
        监控进程直到完成（在单独线程中运行）
        
        进程完成后：
        1. 收集剩余输出
        2. 解析爬虫指标
        3. 更新数据库状态
        4. 延迟清理
        """
        try:
            exit_code = process.process.wait(timeout=timeout)
            
            # 收集剩余输出
            process._collect_remaining_output()
            
            # 更新进程状态
            process.finished_at = datetime.utcnow()
            error_msg = None
            if process.status in (TaskStatus.RUNNING, TaskStatus.PENDING) and exit_code == 0:
                process.status = TaskStatus.SUCCESS
            elif process.status in (TaskStatus.RUNNING, TaskStatus.PENDING):
                process.status = TaskStatus.FAILED
                # 非零退出码：取日志尾部作为失败原因，便于定位问题
                try:
                    tail = process.get_logs(tail=30).strip()
                    error_msg = (
                        tail[-800:] if tail else f"进程退出码: {exit_code}"
                    )
                except Exception as e:
                    logger.error(f"[{task_id}] 读取失败日志失败: {e}")
                    error_msg = f"进程退出码: {exit_code}"
            
            # 解析日志中的指标
            process.parse_metrics_from_logs()
            
            # 关闭日志文件
            process._close_log_file()
            
            # 更新数据库
            self._update_task_completion(
                task_id,
                process.status,
                process.finished_at,
                process.pages_crawled,
                process.items_scraped,
                process.errors_count,
                error_message=error_msg
            )

            # 同步爬虫运行统计
            self._update_spider_stats(task_id, process.status)
            
            logger.info(
                f"[{task_id}] 进程完成: exit_code={exit_code}, "
                f"status={process.status.value}, "
                f"pages={process.pages_crawled}, items={process.items_scraped}"
            )
            
            # 延迟清理（保留一段时间以便查询状态）
            Thread(
                target=self._delayed_cleanup,
                args=(task_id,),
                daemon=True,
                name=f"cleanup-{task_id}"
            ).start()
            
        except subprocess.TimeoutExpired:
            logger.warning(f"[{task_id}] 进程超时 ({timeout}s)，强制终止")
            try:
                process.stop(timeout=5)
                process.status = TaskStatus.TIMEOUT
                process.finished_at = datetime.utcnow()
                process._collect_remaining_output()
                process.parse_metrics_from_logs()
                process._close_log_file()
                
                self._update_task_completion(
                    task_id,
                    TaskStatus.TIMEOUT,
                    process.finished_at,
                    process.pages_crawled,
                    process.items_scraped,
                    process.errors_count,
                    error_message=f"任务超时 ({timeout}s)"
                )
                self._update_spider_stats(task_id, TaskStatus.TIMEOUT)
            except Exception as e:
                logger.error(f"[{task_id}] 超时终止失败: {e}")
        except Exception as e:
            logger.error(f"[{task_id}] 进程监控异常: {e}")
            process.status = TaskStatus.FAILED
            process.finished_at = datetime.utcnow()
            process._close_log_file()
            
            self._update_task_completion(
                task_id,
                TaskStatus.FAILED,
                process.finished_at,
                0, 0, 0,
                error_message=str(e)
            )
            self._update_spider_stats(task_id, TaskStatus.FAILED)

    def _update_spider_stats(self, task_id: str, status: TaskStatus):
        """任务结束后同步爬虫的运行统计（last_run / 成功失败计数）"""
        db = SessionLocal()
        try:
            if not str(task_id).isdigit():
                return
            task = db.query(TaskInstance).filter(TaskInstance.id == int(task_id)).first()
            if not task or not task.spider_id:
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
            logger.info(f"[{task_id}] 已更新爬虫统计: {spider.name} -> {status.value}")
        except Exception as e:
            logger.error(f"[{task_id}] 更新爬虫统计失败: {e}")
            db.rollback()
        finally:
            db.close()

    def _delayed_cleanup(self, task_id: str):
        """延迟清理活动任务"""
        import time
        time.sleep(self.RETENTION_SECONDS)
        self.active_tasks.pop(task_id, None)
        logger.debug(f"[{task_id}] 已从活动任务中清理")

    async def stop_task(self, task_id: str) -> bool:
        """停止本地任务"""
        process = self.active_tasks.get(task_id)
        if not process:
            logger.warning(f"未找到任务进程: {task_id}")
            return False

        success = process.stop()
        if success:
            process.status = TaskStatus.CANCELLED
            process.parse_metrics_from_logs()
            self._update_task_completion(
                task_id,
                TaskStatus.CANCELLED,
                process.finished_at or datetime.utcnow(),
                process.pages_crawled,
                process.items_scraped,
                process.errors_count
            )
            # 延迟清理
            Thread(
                target=self._delayed_cleanup,
                args=(task_id,),
                daemon=True
            ).start()

        return success

    async def pause_task(self, task_id: str) -> bool:
        """暂停本地任务（暂停进程）"""
        process = self.active_tasks.get(task_id)
        if not process or not process.process:
            return False

        try:
            pid = process.process.pid
            if sys.platform == 'win32':
                # Windows: 使用 SIGBREAK
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            else:
                # 暂停整个进程组（含 crawlo 派生的子进程/协程）
                os.killpg(pid, signal.SIGSTOP)

            process.status = TaskStatus.PAUSED
            self._update_task_status(task_id, TaskStatus.PAUSED)
            logger.info(f"任务 {task_id} 已暂停")
            return True
        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
            return False

    async def resume_task(self, task_id: str) -> bool:
        """恢复本地任务"""
        process = self.active_tasks.get(task_id)
        if not process or not process.process:
            return False

        try:
            pid = process.process.pid
            if sys.platform != 'win32':
                os.killpg(pid, signal.SIGCONT)

            process.status = TaskStatus.RUNNING
            self._update_task_status(task_id, TaskStatus.RUNNING)
            logger.info(f"任务 {task_id} 已恢复")
            return True
        except Exception as e:
            logger.error(f"恢复任务失败: {e}")
            return False

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取本地任务状态（先查活动进程，再查数据库）"""
        process = self.active_tasks.get(task_id)
        if process:
            status = process.get_status()
            # 补充爬虫指标
            status['pages_crawled'] = process.pages_crawled
            status['items_scraped'] = process.items_scraped
            status['errors_count'] = process.errors_count
            return status

        # 尝试从数据库查询
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
            if task:
                return {
                    'task_id': task_id,
                    'status': task.status.value if hasattr(task.status, 'value') else str(task.status),
                    'pid': task.process_id,
                    'exit_code': None,
                    'started_at': task.started_at.isoformat() if task.started_at else None,
                    'finished_at': task.finished_at.isoformat() if task.finished_at else None,
                    'pages_crawled': task.pages_crawled or 0,
                    'items_scraped': task.items_scraped or 0,
                    'errors_count': task.errors_count or 0,
                    'duration': float(task.duration) if task.duration else None,
                }
        except Exception as e:
            logger.error(f"查询数据库任务状态失败: {e}")
        finally:
            db.close()
        return None

    def get_task_logs(self, task_id: str, tail: int = 100) -> str:
        """获取本地任务日志"""
        process = self.active_tasks.get(task_id)
        if process:
            logs = process.get_logs(tail=tail)
            if logs:
                return logs

        # 尝试从日志文件读取
        log_file_path = LOGS_DIR / f"task_{task_id}.log"
        if log_file_path.exists():
            try:
                with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                recent = lines[-tail:] if len(lines) > tail else lines
                return ''.join(recent)
            except Exception as e:
                logger.error(f"从文件读取日志失败: {e}")
                return f"读取日志失败: {e}"

        return "无日志（进程可能尚未启动或日志已清理）"

    def _update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        process_id: int = None,
        error_message: str = None
    ):
        """更新数据库中的任务状态"""
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()

            if task:
                task.status = status
                if process_id is not None:
                    task.process_id = process_id
                if error_message:
                    task.error_message = error_message
                if status == TaskStatus.RUNNING and not task.started_at:
                    task.started_at = datetime.utcnow()
                elif status in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
                    if not task.finished_at:
                        task.finished_at = datetime.utcnow()
                    if task.started_at and not task.duration:
                        task.duration = (task.finished_at - task.started_at).total_seconds()

                db.commit()
                logger.debug(f"任务 {task_id} 状态更新为 {status.value}")
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
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
        error_message: str = None
    ):
        """更新任务完成信息（原子终态保护，复用公共实现）"""
        from app.services.task_updater import update_task_completion
        return update_task_completion(
            task_id,
            status,
            finished_at,
            pages_crawled=pages_crawled,
            items_scraped=items_scraped,
            errors_count=errors_count,
            error_message=error_message,
        )

    async def cleanup(self):
        """清理所有活动任务"""
        logger.info("清理 LocalExecutor...")
        for task_id in list(self.active_tasks.keys()):
            await self.stop_task(task_id)
        self.active_tasks.clear()


# 全局实例
_local_executor: Optional[LocalExecutor] = None


def get_local_executor() -> LocalExecutor:
    """获取全局本地执行器实例"""
    global _local_executor
    if _local_executor is None:
        _local_executor = LocalExecutor()
    return _local_executor
