"""
SSH 远程爬虫执行器

支持通过 SSH 在远程服务器上直接运行爬虫（不依赖 Docker）。
管理远程进程生命周期：部署代码、启动、停止、状态查询、日志获取。

工作目录: /opt/crawlopilot/workspace/{task_id}/
"""

import os
import re
import io
import stat
import logging
import uuid
import tarfile
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from threading import Lock, Thread

import paramiko
from paramiko import SSHClient, AutoAddPolicy, RSAKey, Ed25519Key

from app.core.database import SessionLocal
from app.models import TaskInstance, TaskStatus, Node

logger = logging.getLogger(__name__)

# SSH 默认工作目录
SSH_WORKSPACE_ROOT = "/opt/crawlopilot/workspace"


@dataclass
class SshTaskConfig:
    """SSH 远程任务执行配置"""

    task_id: str
    spider_id: str
    spider_name: str

    # 节点 SSH 连接信息
    ssh_host: str
    # 代码目录（本地路径，需要上传到远程服务器）
    code_dir: str
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_pwd: Optional[str] = None
    ssh_key: Optional[str] = None

    # 入口文件（如 run.py），可选，不指定则尝试自动发现
    entry_file: Optional[str] = None

    # 爬虫名称 (用于 crawlo run spider_name)
    spider_name_to_run: Optional[str] = None

    # 远程工作目录（不指定则自动生成）
    remote_workspace: Optional[str] = None

    # 超时配置
    timeout: int = 3600  # 1小时

    # 环境变量
    extra_env: Dict[str, str] = field(default_factory=dict)


class SshConnection:
    """SSH 连接管理器（带自动重连）"""

    def __init__(self, host: str, port: int = 22, user: str = "root",
                 password: str = None, key: str = None):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.key = key
        self._client: Optional[SSHClient] = None
        self._lock = Lock()

    def connect(self) -> SSHClient:
        """建立 SSH 连接"""
        if self._client and self._client.get_transport() and self._client.get_transport().is_active():
            return self._client

        with self._lock:
            # 双重检查
            if self._client and self._client.get_transport() and self._client.get_transport().is_active():
                return self._client

            self._client = SSHClient()
            self._client.set_missing_host_key_policy(AutoAddPolicy())

            connect_kwargs = {
                'hostname': self.host,
                'port': self.port,
                'username': self.user,
                'timeout': 15,
                'allow_agent': False,
                'look_for_keys': False,
            }

            if self.password:
                connect_kwargs['password'] = self.password
            elif self.key:
                try:
                    pkey = RSAKey.from_private_key(io.StringIO(self.key))
                    connect_kwargs['pkey'] = pkey
                except Exception:
                    try:
                        pkey = Ed25519Key.from_private_key(io.StringIO(self.key))
                        connect_kwargs['pkey'] = pkey
                    except Exception as e:
                        raise ValueError(f"无法解析 SSH 私钥: {e}")
            else:
                # 没有密码也没有密钥，尝试使用 agent
                connect_kwargs['allow_agent'] = True
                connect_kwargs['look_for_keys'] = True

            self._client.connect(**connect_kwargs)
            logger.info(f"SSH 连接已建立: {self.user}@{self.host}:{self.port}")
            return self._client

    def exec_command(self, command: str, timeout: int = 30) -> tuple:
        """
        执行远程命令
        
        Returns:
            (stdout, stderr, exit_code)
        """
        client = self.connect()
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
        return out, err, exit_code

    def upload_dir(self, local_dir: str, remote_dir: str) -> bool:
        """
        上传本地目录到远程服务器
        
        使用 tar+gzip 打包传输，效率更高
        """
        client = self.connect()
        sftp = client.open_sftp()

        try:
            # 确保远程目录存在
            self.exec_command(f"mkdir -p {remote_dir}")

            # 创建临时 tar 文件
            with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
                tar_path = tmp.name

            try:
                # 打包本地目录
                import tarfile
                with tarfile.open(tar_path, 'w:gz') as tar:
                    tar.add(local_dir, arcname='.')

                # 上传 tar 包
                remote_tar = f"/tmp/{uuid.uuid4().hex}.tar.gz"
                sftp.put(tar_path, remote_tar)

                # 远程解压
                self.exec_command(f"tar xzf {remote_tar} -C {remote_dir}")
                # 清理远程 tar
                self.exec_command(f"rm -f {remote_tar}")

                logger.info(f"代码已上传: {local_dir} -> {remote_dir}")
                return True

            finally:
                # 清理本地临时文件
                try:
                    os.unlink(tar_path)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"上传代码失败: {e}")
            return False
        finally:
            sftp.close()

    def download_file(self, remote_path: str, local_path: str):
        """从远程服务器下载文件"""
        client = self.connect()
        sftp = client.open_sftp()
        try:
            sftp.get(remote_path, local_path)
        finally:
            sftp.close()

    def file_exists(self, remote_path: str) -> bool:
        """检查远程文件是否存在"""
        client = self.connect()
        sftp = client.open_sftp()
        try:
            sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False
        finally:
            sftp.close()

    def close(self):
        """关闭连接"""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
            logger.info(f"SSH 连接已关闭: {self.user}@{self.host}:{self.port}")

    def __del__(self):
        self.close()


class SshSpiderProcess:
    """远程爬虫进程管理器（通过 SSH）"""

    def __init__(self, task_id: str, ssh_conn: SshConnection):
        self.task_id = task_id
        self.ssh = ssh_conn
        self.remote_pid: Optional[int] = None
        self.status = TaskStatus.PENDING
        self.workspace: Optional[str] = None
        self.entry_file: Optional[str] = None
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None
        self._lock = Lock()

        # 爬虫指标（从日志解析）
        self.pages_crawled: int = 0
        self.items_scraped: int = 0
        self.errors_count: int = 0

    def _ensure_python(self) -> bool:
        """确保远程服务器上有可用的 Python"""
        out, err, code = self.ssh.exec_command("which python3 || which python")
        if code != 0 or not out:
            logger.error(f"[{self.task_id}] 远程服务器上没有 Python")
            return False
        self._python_path = out.split('\n')[0].strip()
        logger.info(f"[{self.task_id}] 远程 Python: {self._python_path}")
        return True

    def _ensure_workspace(self) -> bool:
        """确保远程工作目录存在"""
        if not self.workspace:
            return False
        out, err, code = self.ssh.exec_command(f"mkdir -p {self.workspace}")
        if code != 0:
            logger.error(f"[{self.task_id}] 创建工作目录失败: {err}")
            return False
        return True

    def _install_dependencies(self) -> bool:
        """安装远程项目的依赖"""
        if not self.workspace:
            return False

        # 检查 requirements.txt
        if self.ssh.file_exists(f"{self.workspace}/requirements.txt"):
            logger.info(f"[{self.task_id}] 安装 Python 依赖...")
            out, err, code = self.ssh.exec_command(
                f"cd {self.workspace} && {self._python_path} -m pip install -r requirements.txt -q",
                timeout=120
            )
            if code != 0:
                logger.warning(f"[{self.task_id}] 安装依赖失败: {err[:200]}")
                # 不阻塞继续执行
            else:
                logger.info(f"[{self.task_id}] 依赖安装完成")

        # 检查 package.json (Node.js 项目)
        if self.ssh.file_exists(f"{self.workspace}/package.json"):
            logger.info(f"[{self.task_id}] 安装 Node.js 依赖...")
            self.ssh.exec_command(f"cd {self.workspace} && npm install --production", timeout=120)

        return True

    def start(self, config: SshTaskConfig):
        """
        在远程服务器上启动爬虫
        
        流程：
        1. 连接 SSH
        2. 创建远程工作目录
        3. 上传代码
        4. 安装依赖
        5. 通过 nohup 启动爬虫
        6. 记录 PID
        """
        with self._lock:
            from app.core.database import SessionLocal

            self.workspace = config.remote_workspace or f"{SSH_WORKSPACE_ROOT}/{config.task_id}"

            # 1. 确保远程环境可用
            if not self._ensure_python():
                raise RuntimeError("远程服务器 Python 不可用")

            # 2. 创建工作目录
            if not self._ensure_workspace():
                raise RuntimeError("无法创建远程工作目录")

            # 3. 上传代码
            logger.info(f"[{self.task_id}] 上传代码到 {self.workspace}...")
            success = self.ssh.upload_dir(config.code_dir, self.workspace)
            if not success:
                raise RuntimeError("代码上传失败")

            # 4. 安装依赖
            self._install_dependencies()

            # 5. 构建启动命令
            start_cmd = self._build_start_command(config)

            # 6. 通过 nohup 启动（获取 PID）
            # 使用 setsid 确保进程独立于 SSH 会话
            run_cmd = (
                f"cd {self.workspace} && "
                f"nohup {start_cmd} > task.log 2>&1 & echo $!"
            )
            out, err, code = self.ssh.exec_command(run_cmd, timeout=10)
            # 检查输出是否为有效的 PID
            out = out.strip()
            if out and out.isdigit():
                self.remote_pid = int(out)
            else:
                # 尝试从输出中提取 PID
                logger.warning(f"[{self.task_id}] 无法获取 PID，输出: {out}, 错误: {err}")
                # 尝试 ps 查找
                pid_out, _, _ = self.ssh.exec_command(
                    f"ps aux | grep 'task_{config.task_id}' | grep -v grep | "
                    f"awk '{{print $2}}' | head -1"
                )
                if pid_out.strip().isdigit():
                    self.remote_pid = int(pid_out.strip())

            self.status = TaskStatus.RUNNING
            self.started_at = datetime.utcnow()

            # 写 PID 到文件以便管理
            if self.remote_pid:
                self.ssh.exec_command(f"echo {self.remote_pid} > {self.workspace}/spider.pid")

            logger.info(
                f"[{self.task_id}] 远程爬虫已启动: PID={self.remote_pid}, "
                f"workspace={self.workspace}"
            )

    def _build_start_command(self, config: SshTaskConfig) -> str:
        """构建远程启动命令"""
        entry_file = config.entry_file
        spider_name_to_run = config.spider_name_to_run

        # 优先使用指定的入口文件
        if entry_file:
            if self.ssh.file_exists(f"{self.workspace}/{entry_file}"):
                return f"{self._python_path} {entry_file}"

        # 尝试使用 crawlo 命令
        if spider_name_to_run:
            has_crawlo, _, _ = self.ssh.exec_command("which crawlo")
            if has_crawlo.strip():
                return f"crawlo run {spider_name_to_run}"

        # 尝试自动发现 run.py
        for candidate in ['run.py', 'main.py', 'crawl.py', 'start.py']:
            if self.ssh.file_exists(f"{self.workspace}/{candidate}"):
                return f"{self._python_path} {candidate}"

        # 最后尝试 crawlo (可能已通过 pip 安装但不在 PATH)
        return f"cd {self.workspace} && {self._python_path} -m crawlo.crawler run {spider_name_to_run or config.spider_name}"

    def stop(self, timeout: int = 10) -> bool:
        """停止远程爬虫进程"""
        with self._lock:
            if not self.remote_pid:
                return False

            try:
                # 先尝试优雅停止
                logger.info(f"[{self.task_id}] 停止远程进程 PID={self.remote_pid}")
                self.ssh.exec_command(f"kill {self.remote_pid}", timeout=5)

                # 等待进程结束
                import time
                for _ in range(timeout):
                    alive, _, _ = self.ssh.exec_command(
                        f"kill -0 {self.remote_pid} 2>/dev/null && echo alive || echo dead"
                    )
                    if 'dead' in alive:
                        break
                    time.sleep(1)
                else:
                    # 超时强制杀死
                    logger.warning(f"[{self.task_id}] 进程未响应，强制终止")
                    self.ssh.exec_command(f"kill -9 {self.remote_pid}", timeout=5)

                self.status = TaskStatus.CANCELLED
                self.finished_at = datetime.utcnow()
                logger.info(f"[{self.task_id}] 远程进程已停止")
                return True

            except Exception as e:
                logger.error(f"[{self.task_id}] 停止远程进程失败: {e}")
                return False

    def get_status(self) -> Dict:
        """获取远程进程状态"""
        with self._lock:
            if not self.remote_pid:
                return {
                    'task_id': self.task_id,
                    'status': self.status.value,
                    'pid': None,
                    'workspace': self.workspace,
                    'started_at': self.started_at.isoformat() if self.started_at else None,
                    'finished_at': self.finished_at.isoformat() if self.finished_at else None,
                }

            # 检查进程是否存活
            alive, _, _ = self.ssh.exec_command(
                f"kill -0 {self.remote_pid} 2>/dev/null && echo alive || echo dead"
            )

            if 'dead' in alive.strip():
                # 进程已结束，检查退出码
                if self.status not in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    # 检查日志最后是否有错误
                    log_tail, _, _ = self.ssh.exec_command(
                        f"tail -5 {self.workspace}/task.log 2>/dev/null || echo ''"
                    )
                    if 'Traceback' in log_tail or 'Error' in log_tail or 'error' in log_tail:
                        self.status = TaskStatus.FAILED
                    else:
                        self.status = TaskStatus.SUCCESS
                    self.finished_at = datetime.utcnow()

            return {
                'task_id': self.task_id,
                'status': self.status.value,
                'pid': self.remote_pid,
                'workspace': self.workspace,
                'started_at': self.started_at.isoformat() if self.started_at else None,
                'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            }

    def get_logs(self, tail: int = 100) -> str:
        """获取远程日志"""
        if not self.workspace:
            return ""

        out, err, code = self.ssh.exec_command(
            f"tail -n {tail} {self.workspace}/task.log 2>/dev/null || echo '日志文件不存在'"
        )
        return out if code == 0 else f"获取日志失败: {err}"

    def parse_metrics_from_logs(self):
        """从远程日志中解析爬虫指标"""
        if not self.workspace:
            return

        log_content, _, _ = self.ssh.exec_command(
            f"cat {self.workspace}/task.log 2>/dev/null || echo ''"
        )
        if not log_content:
            return

        try:
            # 匹配 "Crawled X pages, Y items" 格式
            crawled_pattern = re.compile(
                r'(?:Crawled|crawled|已爬取)\s+(\d+)\s+(?:pages?|页).*?(\d+)\s+(?:items?|条)',
                re.IGNORECASE
            )
            alt_pattern = re.compile(r'(\d+)\s+pages?.*?(\d+)\s+items?', re.IGNORECASE)
            error_pattern = re.compile(r'\[(?:ERROR|WARNING)\]', re.IGNORECASE)

            matches = list(crawled_pattern.finditer(log_content))
            if matches:
                last_match = matches[-1]
                self.pages_crawled = int(last_match.group(1))
                self.items_scraped = int(last_match.group(2))
            else:
                alt_matches = list(alt_pattern.finditer(log_content))
                if alt_matches:
                    last_match = alt_matches[-1]
                    self.pages_crawled = int(last_match.group(1))
                    self.items_scraped = int(last_match.group(2))

            self.errors_count = len(error_pattern.findall(log_content))

            logger.info(
                f"[{self.task_id}] 指标解析: pages={self.pages_crawled}, "
                f"items={self.items_scraped}, errors={self.errors_count}"
            )
        except Exception as e:
            logger.error(f"[{self.task_id}] 指标解析失败: {e}")

    def cleanup_workspace(self):
        """清理远程工作目录"""
        if self.workspace:
            logger.info(f"[{self.task_id}] 清理远程工作目录: {self.workspace}")
            self.ssh.exec_command(f"rm -rf {self.workspace}")


class SshExecutor:
    """
    SSH 远程爬虫执行器

    通过 SSH 在远程服务器上直接运行爬虫，不依赖 Docker。
    支持代码上传、依赖安装、进程管理、日志获取。

    特性：
    - SSH 连接管理（自动重连）
    - 代码打包上传（tar+gzip）
    - 远程进程生命周期管理
    - 远程日志获取
    - 爬虫指标自动统计
    - 进程完成后自动更新数据库
    """

    # 进程完成后的保留时间
    RETENTION_SECONDS = 300  # 5分钟

    def __init__(self):
        self.active_tasks: Dict[str, SshSpiderProcess] = {}

    async def execute_task(self, config: SshTaskConfig) -> str:
        """
        执行远程 SSH 爬虫任务

        Args:
            config: SSH 任务配置

        Returns:
            任务 ID
        """
        logger.info(f"执行 SSH 远程任务 {config.task_id}: {config.spider_name}")

        # 创建 SSH 连接
        ssh_conn = SshConnection(
            host=config.ssh_host,
            port=config.ssh_port,
            user=config.ssh_user,
            password=config.ssh_pwd,
            key=config.ssh_key,
        )

        # 创建远程进程管理器
        process = SshSpiderProcess(config.task_id, ssh_conn)

        try:
            process.start(config)
            self.active_tasks[config.task_id] = process

            # 更新数据库状态
            self._update_task_status(
                config.task_id,
                TaskStatus.RUNNING,
                process_id=process.remote_pid,
                workspace=process.workspace
            )

            # 启动进程监控线程
            monitor_thread = Thread(
                target=self._monitor_process,
                args=(config.task_id, process, config.timeout),
                daemon=True,
                name=f"ssh-monitor-{config.task_id}"
            )
            monitor_thread.start()

            logger.info(
                f"SSH 远程任务已启动: {config.task_id}, "
                f"PID={process.remote_pid}, host={config.ssh_host}"
            )
            return config.task_id

        except Exception as e:
            logger.error(f"SSH 远程任务启动失败: {e}")
            self._update_task_status(
                config.task_id,
                TaskStatus.FAILED,
                error_message=str(e)
            )
            ssh_conn.close()
            raise

    def _monitor_process(self, task_id: str, process: SshSpiderProcess, timeout: int):
        """
        监控远程进程直到完成（在单独线程中运行）
        """
        try:
            # 轮询进程状态
            import time
            deadline = time.time() + timeout

            while time.time() < deadline:
                alive, _, _ = process.ssh.exec_command(
                    f"kill -0 {process.remote_pid} 2>/dev/null && echo alive || echo dead"
                )
                if 'dead' in alive.strip():
                    break
                time.sleep(5)  # 每 5 秒检查一次

            else:
                # 超时
                logger.warning(f"[{task_id}] 远程任务超时 ({timeout}s)")
                process.stop(timeout=5)
                process.status = TaskStatus.TIMEOUT
                process.finished_at = datetime.utcnow()

            # 进程结束后的处理
            if process.status not in [TaskStatus.TIMEOUT, TaskStatus.CANCELLED]:
                process.finished_at = datetime.utcnow()
                # 检查日志判断成功/失败
                log_tail, _, _ = process.ssh.exec_command(
                    f"tail -10 {process.workspace}/task.log 2>/dev/null || echo ''"
                )
                if 'Traceback' in log_tail or 'Error' in log_tail:
                    process.status = TaskStatus.FAILED
                else:
                    process.status = TaskStatus.SUCCESS

            # 解析指标
            process.parse_metrics_from_logs()

            # 更新数据库
            self._update_task_completion(
                task_id,
                process.status,
                process.finished_at or datetime.utcnow(),
                process.pages_crawled,
                process.items_scraped,
                process.errors_count
            )

            logger.info(
                f"[{task_id}] 远程任务完成: status={process.status.value}, "
                f"pages={process.pages_crawled}, items={process.items_scraped}"
            )

            # 延迟清理
            Thread(
                target=self._delayed_cleanup,
                args=(task_id,),
                daemon=True,
                name=f"ssh-cleanup-{task_id}"
            ).start()

        except Exception as e:
            logger.error(f"[{task_id}] 远程进程监控异常: {e}")
            process.status = TaskStatus.FAILED
            process.finished_at = datetime.utcnow()
            self._update_task_completion(
                task_id,
                TaskStatus.FAILED,
                process.finished_at,
                0, 0, 0,
                error_message=str(e)
            )

    def _delayed_cleanup(self, task_id: str):
        """延迟清理活动任务"""
        import time
        time.sleep(self.RETENTION_SECONDS)
        process = self.active_tasks.pop(task_id, None)
        if process:
            try:
                process.ssh.close()
            except Exception:
                pass
        logger.debug(f"[{task_id}] 已从活动任务中清理")

    async def stop_task(self, task_id: str) -> bool:
        """停止 SSH 远程任务"""
        process = self.active_tasks.get(task_id)
        if not process:
            logger.warning(f"未找到远程任务: {task_id}")
            return False

        success = process.stop()
        if success:
            process.parse_metrics_from_logs()
            self._update_task_completion(
                task_id,
                TaskStatus.CANCELLED,
                process.finished_at or datetime.utcnow(),
                process.pages_crawled,
                process.items_scraped,
                process.errors_count
            )
            Thread(
                target=self._delayed_cleanup,
                args=(task_id,),
                daemon=True
            ).start()

        return success

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取远程任务状态"""
        process = self.active_tasks.get(task_id)
        if process:
            status = process.get_status()
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
                    'workspace': task.workspace,
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
        """获取远程任务日志"""
        process = self.active_tasks.get(task_id)
        if process:
            logs = process.get_logs(tail=tail)
            if logs:
                return logs
        return "无日志（进程可能尚未启动或连接已断开）"

    def _update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        process_id: int = None,
        workspace: str = None,
        error_message: str = None
    ):
        """更新数据库中的任务状态"""
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
            if task:
                task.status = status
                task.deploy_mode = "ssh"
                if process_id is not None:
                    task.process_id = process_id
                if workspace:
                    task.workspace = workspace
                if error_message:
                    task.error_message = error_message
                if status == TaskStatus.RUNNING and not task.started_at:
                    task.started_at = datetime.utcnow()
                elif status in [TaskStatus.SUCCESS, TaskStatus.FAILED,
                                TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
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
        """更新任务完成信息"""
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
            if task:
                task.status = status
                task.finished_at = finished_at
                task.pages_crawled = pages_crawled
                task.items_scraped = items_scraped
                task.errors_count = errors_count
                task.deploy_mode = "ssh"
                if error_message:
                    task.error_message = error_message
                if task.started_at:
                    task.duration = (finished_at - task.started_at).total_seconds()
                db.commit()
                logger.info(
                    f"任务 {task_id} 完成: status={status.value}, "
                    f"pages={pages_crawled}, items={items_scraped}, "
                    f"errors={errors_count}, duration={task.duration}s"
                )
        except Exception as e:
            logger.error(f"更新任务完成信息失败: {e}")
            db.rollback()
        finally:
            db.close()

    async def cleanup(self):
        """清理所有活动任务"""
        logger.info("清理 SshExecutor...")
        for task_id in list(self.active_tasks.keys()):
            await self.stop_task(task_id)
        self.active_tasks.clear()


# 全局实例
_ssh_executor: Optional[SshExecutor] = None


def get_ssh_executor() -> SshExecutor:
    """获取全局 SSH 执行器实例"""
    global _ssh_executor
    if _ssh_executor is None:
        _ssh_executor = SshExecutor()
    return _ssh_executor
