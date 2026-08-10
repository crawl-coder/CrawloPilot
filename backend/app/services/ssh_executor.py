"""
SSH 远程爬虫执行器

支持通过 SSH 在远程服务器上直接运行爬虫（不依赖 Docker）。
管理远程进程生命周期：部署代码、启动、停止、状态查询、日志获取。

工作目录: /opt/crawlopilot/workspace/{task_id}/
"""

import os
import asyncio
import re
import io
import stat
import logging
import uuid
import tarfile
import tempfile
import shlex
from pathlib import Path
from datetime import datetime
from app.core.time_utils import cn_now
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from threading import Lock, Thread

import paramiko
from paramiko import SSHClient, AutoAddPolicy, RejectPolicy, RSAKey, Ed25519Key

from app.core.database import SessionLocal
from app.models import TaskInstance, TaskStatus, Node, Spider, DeployMode
from app.core.config import settings

logger = logging.getLogger(__name__)

# SSH 默认工作目录
SSH_WORKSPACE_ROOT = "/opt/crawlopilot/workspace"

# 控制面维护的 SSH known_hosts（TOFU：首次连接记录，后续变更即拒绝）
SSH_KNOWN_HOSTS = Path(os.environ.get(
    "SSH_KNOWN_HOSTS",
    os.path.join(settings.UPLOAD_DIR, "ssh_known_hosts"),
))


def _q(s: str) -> str:
    """shell 转义，防止命令注入"""
    return shlex.quote(str(s))


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
        # 命令锁：paramiko 同一连接并发开 channel 会排队超时
        # （"Timeout opening channel"），串行化所有远程命令
        self._cmd_lock = Lock()

    def connect(self) -> SSHClient:
        """建立 SSH 连接"""
        if self._client and self._client.get_transport() and self._client.get_transport().is_active():
            return self._client

        if not self._lock.acquire(timeout=120):
            raise TimeoutError("等待 SSH 连接锁超时")
        try:
            # 双重检查
            if self._client and self._client.get_transport() and self._client.get_transport().is_active():
                return self._client

            self._client = SSHClient()
            # TOFU host key 校验：已有记录则严格校验，首次连接才自动信任
            if SSH_KNOWN_HOSTS.exists():
                self._client.load_host_keys(str(SSH_KNOWN_HOSTS))
            if self.host in self._client.get_host_keys():
                self._client.set_missing_host_key_policy(RejectPolicy())
            else:
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
            # 连接保活：防止空闲连接被服务端断开导致间歇性 channel 超时
            if self._client.get_transport():
                self._client.get_transport().set_keepalive(30)
            # 首次连接：持久化 host key，供后续严格校验
            try:
                SSH_KNOWN_HOSTS.parent.mkdir(parents=True, exist_ok=True)
                self._client.get_host_keys().save(str(SSH_KNOWN_HOSTS))
            except OSError as e:
                logger.warning(f"保存 SSH host key 失败: {e}")
            logger.info(f"SSH 连接已建立: {self.user}@{self.host}:{self.port}")
            return self._client
        finally:
            self._lock.release()

    def exec_command(self, command: str, timeout: int = 30, get_pty: bool = True) -> tuple:
        """
        执行远程命令
        
        Returns:
            (stdout, stderr, exit_code)
        """
        # 串行化远程命令，避免并发 channel 竞争超时
        if not self._cmd_lock.acquire(timeout=timeout + 10):
            raise TimeoutError("等待 SSH 命令锁超时")
        try:
            return self._exec_command_locked(command, timeout, get_pty)
        finally:
            self._cmd_lock.release()

    def _exec_command_locked(self, command: str, timeout: int, get_pty: bool) -> tuple:
        # 断连自动重连一次：连接可能被服务端静默断开（空闲超时），
        # 首次失败时重建连接再试，避免偶发 "Timeout opening channel"
        for attempt in range(2):
            try:
                client = self.connect()
                stdin, stdout, stderr = client.exec_command(
                    command, timeout=timeout, get_pty=get_pty
                )
                exit_code = stdout.channel.recv_exit_status()
                # 注意：不能用 stdout.read()——它阻塞到通道关闭；远程命令若含后台驻留进程
                # （setsid nohup ... &），部分 sshd 会保持通道不关闭导致 read() 超时。
                # SSH 协议保证 exit-status 之前所有 stdout/stderr 数据已按序到达，
                # 因此 recv_exit_status 返回后直接排空缓冲即可。
                chan = stdout.channel
                out_chunks = []
                while chan.recv_ready():
                    out_chunks.append(chan.recv(65536))
                err_chunks = []
                while chan.recv_stderr_ready():
                    err_chunks.append(chan.recv_stderr(65536))
                out = b"".join(out_chunks).decode('utf-8', errors='replace').strip()
                err = b"".join(err_chunks).decode('utf-8', errors='replace').strip()
                return out, err, exit_code
            except (EOFError, OSError, paramiko.SSHException) as e:
                if attempt == 1:
                    raise
                logger.warning(
                    f"SSH 执行命令失败（尝试重连）: {e}"
                )
                self._client = None  # 强制下次 connect 重建连接

    def upload_dir(self, local_dir: str, remote_dir: str) -> bool:
        """
        上传本地目录到远程服务器
        
        使用 tar+gzip 打包传输，效率更高
        """
        client = self.connect()
        sftp = client.open_sftp()

        try:
            # 确保远程目录存在
            self.exec_command(f"mkdir -p {_q(remote_dir)}")

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
                self.exec_command(f"tar xzf {_q(remote_tar)} -C {_q(remote_dir)}")
                # 清理远程 tar
                self.exec_command(f"rm -f {_q(remote_tar)}")

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

    def _ensure_venv(self) -> bool:
        """在远程工作目录创建独立 venv，隔离任务依赖，避免污染节点系统 Python。

        成功后在 self._venv_python 记录 venv 内的 python 路径；
        失败时 self._venv_python 为空，调用方回退系统 Python。
        """
        self._venv_python = None
        if not self.workspace or not self._python_path:
            return False
        venv_dir = f"{self.workspace}/.venv"
        try:
            logger.info(f"[{self.task_id}] 创建任务 venv: {venv_dir}")
            # 幂等：已存在则直接复用
            out, _, code = self.ssh.exec_command(
                f"[ -d {_q(venv_dir)} ] && echo exists || echo missing"
            )
            if 'exists' not in out:
                # 优先 python -m venv；不支持时回退 virtualenv
                out, err, code = self.ssh.exec_command(
                    f"cd {_q(self.workspace)} && {_q(self._python_path)} -m venv {_q('.venv')}",
                    timeout=120,
                )
                if code != 0:
                    logger.warning(f"[{self.task_id}] python -m venv 失败，尝试 virtualenv: {err[:150]}")
                    _, _, vcode = self.ssh.exec_command(
                        f"cd {_q(self.workspace)} && {_q(self._python_path)} "
                        f"-m pip install --quiet virtualenv "
                        f"-i {os.environ.get('PIP_INDEX_URL', 'https://pypi.tuna.tsinghua.edu.cn/simple')}",
                        timeout=180,
                    )
                    if vcode != 0:
                        return False
                    out, err, code = self.ssh.exec_command(
                        f"cd {_q(self.workspace)} && virtualenv {_q('.venv')}", timeout=120
                    )
                    if code != 0:
                        logger.warning(f"[{self.task_id}] virtualenv 创建失败: {(err or out)[:150]}")
                        return False

            # 记录 venv python 路径
            self._venv_python = f"{venv_dir}/bin/python"
            logger.info(f"[{self.task_id}] venv Python: {self._venv_python}")
            return True
        except Exception as e:
            logger.warning(f"[{self.task_id}] venv 创建异常: {e}")
            return False

    def _ensure_workspace(self) -> bool:
        """确保远程工作目录存在"""
        if not self.workspace:
            return False
        out, err, code = self.ssh.exec_command(f"mkdir -p {_q(self.workspace)}")
        if code != 0:
            logger.error(f"[{self.task_id}] 创建工作目录失败: {err}")
            return False
        return True

    def _use_python(self) -> str:
        """返回实际使用的 Python：优先 venv 内 python，否则系统 python。"""
        return getattr(self, '_venv_python', None) or self._python_path

    def _append_task_log(self, message: str) -> None:
        """向远程 task.log 追加一行带时间戳的日志，使用户通过任务日志可见进度。

        调用方确保 self.ssh 已连接、self.workspace 已就绪。
        """
        try:
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.ssh.exec_command(
                f"printf '%s %s\\n' {_q(ts)} {_q(message)} >> {_q(self.workspace + '/task.log')}",
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"[{self.task_id}] 追加任务日志失败: {e}")

    def _install_dependencies(self) -> bool:
        """安装远程项目的依赖（在任务 venv 内安装，不污染系统环境）"""
        if not self.workspace:
            return False

        python = self._use_python()

        # 检查 requirements.txt
        if self.ssh.file_exists(f"{self.workspace}/requirements.txt"):
            logger.info(f"[{self.task_id}] 安装 Python 依赖...")
            self._append_task_log("检测到 requirements.txt，正在安装 Python 依赖（可能耗时较长）...")
            out, err, code = self.ssh.exec_command(
                f"cd {_q(self.workspace)} && {_q(python)} "
                f"-m pip install -r requirements.txt -q",
                timeout=120
            )
            if code != 0:
                logger.warning(f"[{self.task_id}] 安装依赖失败: {err[:200]}")
                self._append_task_log(f"依赖安装失败：{(err or out).strip()[:200] or '未知错误'}")
                # 不阻塞继续执行
            else:
                logger.info(f"[{self.task_id}] 依赖安装完成")
                self._append_task_log("Python 依赖安装完成")

        # 检查 package.json (Node.js 项目)
        if self.ssh.file_exists(f"{self.workspace}/package.json"):
            logger.info(f"[{self.task_id}] 安装 Node.js 依赖...")
            self._append_task_log("检测到 package.json，正在安装 Node.js 依赖...")
            self.ssh.exec_command(
                f"cd {_q(self.workspace)} && npm install --production", timeout=120
            )

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
        if not self._lock.acquire(timeout=180):
            raise TimeoutError("等待任务启动锁超时")
        try:
            from app.core.database import SessionLocal

            self.workspace = config.remote_workspace or f"{SSH_WORKSPACE_ROOT}/{config.task_id}"

            # 1. 确保远程环境可用
            if not self._ensure_python():
                raise RuntimeError("远程服务器 Python 不可用")

            # 2. 创建工作目录
            if not self._ensure_workspace():
                raise RuntimeError("无法创建远程工作目录")
            self._append_task_log("SSH 执行器已连接远程节点，开始准备执行环境")

            # 3. 上传代码
            logger.info(f"[{self.task_id}] 上传代码到 {self.workspace}...")
            self._append_task_log("上传爬虫代码到远程节点...")
            success = self.ssh.upload_dir(config.code_dir, self.workspace)
            if not success:
                raise RuntimeError("代码上传失败")
            self._append_task_log("代码上传完成")

            # 4. 创建任务隔离 venv（避免污染节点系统 Python 环境）
            if not self._ensure_venv():
                logger.warning(f"[{self.task_id}] 创建 venv 失败，回退使用系统 Python")
                self._append_task_log("创建独立运行环境失败，将使用节点系统 Python")
            else:
                self._append_task_log("已创建任务独立运行环境 (venv)")

            # 5. 安装依赖（venv 内安装）
            self._append_task_log("开始安装爬虫依赖...")
            self._install_dependencies()
            self._ensure_crawlo()
            self._append_task_log("依赖安装完成")

            # 6. 构建启动命令
            self._append_task_log("准备启动爬虫...")
            start_cmd = self._build_start_command(config)

            # 6. 通过 nohup 启动（获取 PID）
            # 使用 setsid 确保进程独立于 SSH 会话
            run_cmd = (
                f"cd {_q(self.workspace)} && "
                # 追加日志，保留启动阶段的进度信息（venv/依赖/crawlo 准备日志）
                f"setsid nohup bash -c {_q(start_cmd + ' >> task.log 2>&1; echo $? > exit.code')} "
                f"</dev/null >/dev/null 2>&1 & echo $!"
            )
            out, err, code = self.ssh.exec_command(run_cmd, timeout=10, get_pty=False)
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
            self.started_at = cn_now()

            # 写 PID 到文件以便管理
            if self.remote_pid:
                self.ssh.exec_command(
                    f"echo {_q(str(self.remote_pid))} > {_q(self.workspace)}/spider.pid"
                )
                self._append_task_log(f"爬虫已启动 (PID: {self.remote_pid})，开始执行")
            else:
                self._append_task_log("爬虫进程已启动，但未获取到 PID")

            logger.info(
                f"[{self.task_id}] 远程爬虫已启动: PID={self.remote_pid}, "
                f"workspace={self.workspace}"
            )
        except Exception as e:
            # 把失败原因写入任务日志，便于用户定位
            logger.exception(f"[{self.task_id}] SSH 任务启动失败: {e!r}")
            try:
                self._append_task_log(f"任务启动失败：{str(e)[:300]}")
            except Exception:
                pass
            raise
        finally:
            self._lock.release()

    def _build_start_command(self, config: SshTaskConfig) -> str:
        """构建远程启动命令（统一使用任务 venv 的 Python）"""
        entry_file = config.entry_file
        spider_name_to_run = config.spider_name_to_run
        python = self._use_python()

        # 优先使用指定的入口文件
        if entry_file:
            if self.ssh.file_exists(f"{self.workspace}/{entry_file}"):
                return f"{_q(python)} {_q(entry_file)}"

        # 尝试使用 crawlo（venv 内安装的 crawlo 不在 PATH，用 python -m crawlo）
        if spider_name_to_run:
            has_crawlo, _, _ = self.ssh.exec_command(
                f"{python} -m crawlo 2>/dev/null && echo ok || echo no"
            )
            if has_crawlo.strip() == 'ok':
                return (
                    f"cd {_q(self.workspace)} && {_q(python)} "
                    f"-m crawlo.crawler run {_q(spider_name_to_run)}"
                )

        # 尝试自动发现 run.py
        for candidate in ['run.py', 'main.py', 'crawl.py', 'start.py']:
            if self.ssh.file_exists(f"{self.workspace}/{candidate}"):
                return f"{_q(python)} {_q(candidate)}"

        # 最后尝试 crawlo (可能已通过 pip 安装但不在 PATH)
        return (
            f"cd {_q(self.workspace)} && {_q(python)} "
            f"-m crawlo.crawler run {_q(spider_name_to_run or config.spider_name)}"
        )

    def _ensure_crawlo(self):
        """确保执行环境可导入 crawlo（缺失则自动 pip 安装；优先在 venv 内安装）"""
        python = self._use_python()
        out, _, code = self.ssh.exec_command(
            f"{python} -c 'import crawlo' 2>/dev/null && echo ok || echo no"
        )
        if code == 0 and out.strip() == 'ok':
            return

        logger.info(f"[{self.task_id}] 缺少 crawlo，自动安装中...")
        self._append_task_log("检测到缺少 crawlo 框架，正在自动安装（可能耗时较长）...")
        # 使用 venv 内的 pip（venv 自带 pip）；仅在回退系统 python 时需 ensurepip 补
        if not getattr(self, '_venv_python', None):
            pip_out, pip_err, pip_code = self.ssh.exec_command(
                f"{python} -m pip --version"
            )
            if pip_code != 0:
                logger.info(f"[{self.task_id}] 缺少 pip，执行 ensurepip...")
                self.ssh.exec_command(
                    f"{_q(python)} -m ensurepip --upgrade", timeout=120
                )
                pip_out, _, pip_code2 = self.ssh.exec_command(
                    f"{python} -m pip --version"
                )
                if pip_code2 != 0:
                    # 精简系统（无 ensurepip）用系统包管理器补 pip
                    logger.info(f"[{self.task_id}] ensurepip 不可用，尝试 apt 安装 python3-pip...")
                    self.ssh.exec_command(
                        "apt-get update -qq && apt-get install -y -qq python3-pip",
                        timeout=600,
                    )

        out, err, code = self.ssh.exec_command(
            f"{python} -m pip install --quiet crawlo aiomysql "
            f"-i {os.environ.get('PIP_INDEX_URL', 'https://pypi.tuna.tsinghua.edu.cn/simple')}",
            timeout=600,
        )
        if code != 0:
            logger.warning(f"[{self.task_id}] crawlo 自动安装失败: {(err or out)[:200]}")
            self._append_task_log(f"crawlo 框架安装失败：{(err or out).strip()[:200]}")
        else:
            logger.info(f"[{self.task_id}] crawlo 安装完成")
            self._append_task_log("crawlo 框架安装完成")

    def stop(self, timeout: int = 10) -> bool:
        """停止远程爬虫进程"""
        with self._lock:
            if not self.remote_pid:
                return False

            try:
                # 先尝试优雅停止
                logger.info(f"[{self.task_id}] 停止远程进程 PID={self.remote_pid}")
                try:
                    self.ssh.exec_command(f"kill {_q(str(self.remote_pid))}", timeout=5)
                except Exception as e:
                    logger.warning(f"[{self.task_id}] kill 失败，将直接强制终止: {e}")

                # 等待进程结束
                import time
                for _ in range(timeout):
                    try:
                        alive, _, _ = self.ssh.exec_command(
                            f"kill -0 {_q(str(self.remote_pid))} 2>/dev/null && echo alive || echo dead"
                        )
                    except Exception:
                        alive = "alive"  # 连接异常按存活处理，进入强制终止
                    if 'dead' in alive:
                        break
                    time.sleep(1)
                else:
                    # 超时强制杀死
                    logger.warning(f"[{self.task_id}] 进程未响应，强制终止")
                    try:
                        self.ssh.exec_command(
                            f"kill -9 {_q(str(self.remote_pid))}", timeout=5
                        )
                    except Exception as e:
                        logger.error(f"[{self.task_id}] kill -9 失败: {e}")

                # kill -9 后最终确认：仍存活则记录告警（进程可能已无法访问，
                # 由外层 DB 兜底清理重试）
                try:
                    alive, _, _ = self.ssh.exec_command(
                        f"kill -0 {_q(str(self.remote_pid))} 2>/dev/null && echo alive || echo dead"
                    )
                    if 'alive' in alive:
                        logger.warning(f"[{self.task_id}] 强制终止后进程仍存活")
                except Exception as e:
                    logger.warning(f"[{self.task_id}] 停止后确认进程状态失败: {e}")

                # 按 workspace 清理同会话残留子进程（setsid bash 派生的
                # venv python 等），避免孤儿进程继续占用资源
                if self.workspace:
                    try:
                        self.ssh.exec_command(
                            f"pkill -9 -f {_q(self.workspace)} 2>/dev/null; echo done",
                            timeout=10,
                        )
                    except Exception as e:
                        logger.warning(f"[{self.task_id}] pkill 残留进程失败: {e}")

                self.status = TaskStatus.CANCELLED
                self.finished_at = cn_now()
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
                    self.finished_at = cn_now()

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
            # crawlo 1.7.x 统计 key 带 crawlo: 前缀（兼容旧格式）
            crawlo_items_pattern = re.compile(r"['\"]crawlo:item_successful_count['\"]\s*:\s*(\d+)")
            crawlo_items_legacy = re.compile(r"['\"]item_successful_count['\"]\s*:\s*(\d+)")
            crawlo_pages_pattern = re.compile(r"['\"]crawlo:response_received_count['\"]\s*:\s*(\d+)")
            crawlo_pages_legacy = re.compile(r"['\"]response_received_count['\"]\s*:\s*(\d+)")
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

            if not self.items_scraped:
                m = crawlo_items_pattern.search(log_content)
                if not m:
                    m = crawlo_items_legacy.search(log_content)
                if m:
                    self.items_scraped = int(m.group(1))
            if not self.pages_crawled:
                m = crawlo_pages_pattern.search(log_content)
                if not m:
                    m = crawlo_pages_legacy.search(log_content)
                if m:
                    self.pages_crawled = int(m.group(1))

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
            self.ssh.exec_command(f"rm -rf {_q(self.workspace)}")


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
        """执行远程 SSH 爬虫任务（阻塞操作放入线程池，避免阻塞事件循环）"""
        return await asyncio.to_thread(self._execute_sync, config)

    def _execute_sync(self, config: SshTaskConfig) -> str:
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
            logger.exception(f"SSH 远程任务启动失败: {e!r}")
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
                process.finished_at = cn_now()

            # 进程结束后的处理
            if process.status not in [TaskStatus.TIMEOUT, TaskStatus.CANCELLED]:
                process.finished_at = cn_now()
                # 优先读取退出码判断成功/失败
                exit_code_out, _, _ = process.ssh.exec_command(
                    f"cat {process.workspace}/exit.code 2>/dev/null || echo ''"
                )
                exit_code = exit_code_out.strip()
                if exit_code.isdigit():
                    process.status = (
                        TaskStatus.SUCCESS if int(exit_code) == 0 else TaskStatus.FAILED
                    )
                else:
                    # 兜底：按日志关键字判断
                    log_tail, _, _ = process.ssh.exec_command(
                        f"tail -10 {process.workspace}/task.log 2>/dev/null || echo ''"
                    )
                    process.status = (
                        TaskStatus.FAILED
                        if ('Traceback' in log_tail or 'Error' in log_tail)
                        else TaskStatus.SUCCESS
                    )

            # 解析指标
            process.parse_metrics_from_logs()

            # 更新数据库
            self._update_task_completion(
                task_id,
                process.status,
                process.finished_at or cn_now(),
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
            process.finished_at = cn_now()
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
        """停止 SSH 远程任务

        先尝试 active_tasks 中的进程句柄；若句柄丢失（如后端重启后
        active_tasks 为空），从 DB 读取节点凭据重建连接兜底清理，
        确保取消后远程进程必死、工作目录被清理，不留孤儿进程。
        """
        process = self.active_tasks.get(task_id)
        success = process.stop() if process else False
        if not success:
            logger.warning(f"active_tasks 未找到远程任务 {task_id}，尝试 DB 兜底清理")
            success = self._force_kill_remote(task_id)
        if success:
            if process:
                process.parse_metrics_from_logs()
            self._update_task_completion(
                task_id,
                TaskStatus.CANCELLED,
                cn_now(),
                process.pages_crawled if process else 0,
                process.items_scraped if process else 0,
                process.errors_count if process else 0,
            )
            if process:
                Thread(
                    target=self._delayed_cleanup,
                    args=(task_id,),
                    daemon=True
                ).start()

        return success

    def _force_kill_remote(self, task_id: str) -> bool:
        """DB 兜底：后端重启/句柄丢失时，从 DB 重建连接杀远程进程并清理目录"""
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == int(task_id)).first()
            if not task or task.deploy_mode != "ssh":
                logger.warning(f"[{task_id}] DB 兜底：任务不存在或非 SSH 模式")
                return False
            node = db.query(Node).filter(Node.id == task.node_id).first()
            if not node:
                logger.warning(f"[{task_id}] DB 兜底：节点不存在 node_id={task.node_id}")
                return False

            from app.services.node_service import decrypt_node_credential
            ssh = SshConnection(
                host=node.ssh_host or node.host,
                port=node.ssh_port or 22,
                user=node.ssh_user or "root",
                password=decrypt_node_credential(node.ssh_pwd),
                key=decrypt_node_credential(node.ssh_key),
            )
            pid = task.process_id
            workspace = task.workspace
            killed = False
            if pid:
                # 先优雅 kill，等待 2s，未死则 kill -9
                try:
                    ssh.exec_command(f"kill {_q(str(pid))}", timeout=5)
                except Exception:
                    pass
                import time as _time
                _time.sleep(2)
                try:
                    alive, _, _ = ssh.exec_command(
                        f"kill -0 {_q(str(pid))} 2>/dev/null && echo alive || echo dead",
                        timeout=5,
                    )
                except Exception:
                    alive = "alive"
                if "alive" in alive:
                    try:
                        ssh.exec_command(f"kill -9 {_q(str(pid))}", timeout=5)
                        logger.info(f"[{task_id}] DB 兜底 kill -9 远程进程 {pid}")
                    except Exception as e:
                        logger.error(f"[{task_id}] DB 兜底 kill -9 失败: {e}")
                killed = True
            # 兜底：按 workspace 匹配杀掉同会话残留子进程（setsid bash 派生的
            # venv python 等），确保取消后不留孤儿进程
            if workspace:
                try:
                    out, _, _ = ssh.exec_command(
                        f"pkill -9 -f {_q(workspace)} 2>/dev/null; echo done",
                        timeout=10,
                    )
                    logger.info(f"[{task_id}] DB 兜底 pkill workspace 残留进程")
                except Exception as e:
                    logger.warning(f"[{task_id}] DB 兜底 pkill 失败: {e}")
                killed = True
            # 清理远程工作目录
            if workspace:
                try:
                    ssh.exec_command(f"rm -rf {_q(workspace)}", timeout=10)
                    logger.info(f"[{task_id}] DB 兜底清理远程目录 {workspace}")
                except Exception as e:
                    logger.warning(f"[{task_id}] DB 兜底清理目录失败: {e}")
            return killed or bool(workspace)
        except Exception as e:
            logger.error(f"[{task_id}] DB 兜底清理失败: {e}")
            return False
        finally:
            db.close()

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
                task.deploy_mode = DeployMode.SSH
                if process_id is not None:
                    task.process_id = process_id
                if workspace:
                    task.workspace = workspace
                if error_message:
                    task.error_message = error_message
                if status == TaskStatus.RUNNING and not task.started_at:
                    task.started_at = cn_now()
                elif status in [TaskStatus.SUCCESS, TaskStatus.FAILED,
                                TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
                    if not task.finished_at:
                        task.finished_at = cn_now()
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
        updated = update_task_completion(
            task_id,
            status,
            finished_at,
            pages_crawled=pages_crawled,
            items_scraped=items_scraped,
            errors_count=errors_count,
            error_message=error_message,
            deploy_mode=DeployMode.SSH,
        )
        if updated:
            from app.core.database import SessionLocal as _SL
            db = _SL()
            try:
                task = db.query(TaskInstance).filter(
                    TaskInstance.id == int(task_id)
                ).first()
                if task:
                    self._update_spider_stats(db, task, status)
            finally:
                db.close()
        return updated

    def _update_spider_stats(self, db, task: TaskInstance, status: TaskStatus):
        """同步爬虫运行统计（与本地执行器保持一致）"""
        try:
            if not task.spider_id:
                return
            spider = db.query(Spider).filter(Spider.id == task.spider_id).first()
            if not spider:
                return
            spider.last_run_at = cn_now()
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
