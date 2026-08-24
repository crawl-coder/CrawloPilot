#!/usr/bin/env python3
"""
CrawloPilot Agent - 节点执行代理

运行在目标服务器上，主动连接 CrawloPilot 管理服务器：
- 注册（token）→ 获得 node_id
- 每 30 秒心跳
- 每 5 秒轮询领取待执行任务
- 下载爬虫代码 → 本地执行 → 实时回报日志 → 回报终态/指标

用法:
    python crawlo_agent.py --server http://管理服务器:18000 --token <注册令牌>

仅依赖 Python 标准库，可在任意 Linux/macOS/Windows 服务器直接运行。
"""

import argparse
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AGENT_VERSION = "0.2.0"
DEFAULT_SERVER = os.environ.get("CRAWLOPILOT_AGENT_SERVER", "http://127.0.0.1:18000")
PIP_INDEX = os.environ.get("PIP_INDEX_URL", "https://pypi.tuna.tsinghua.edu.cn/simple")

# venv 模板缓存目录（按 crawlo 版本，一次安装多任务复用）
_TEMPLATE_VENV_DIR = Path(os.environ.get(
    "CRAWLO_AGENT_TEMPLATE_VENV", str(Path.home() / ".crawlo-agent" / "template_venv")))


def log(msg: str):
    print(f"[crawlo-agent {time.strftime('%H:%M:%S')}] {msg}", flush=True)


class AgentClient:
    def __init__(self, server: str, token: str, poll_interval: int = 5):
        self.server = server.rstrip("/")
        self.token = token
        self.node_id = None
        self.poll_interval = poll_interval
        self._running_tasks = {}

    # ============ HTTP 工具 ============

    def _request(self, method: str, path: str, body: dict = None, timeout: int = 30):
        url = f"{self.server}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode("utf-8")).get("detail", str(e))
            except Exception:
                detail = str(e)
            raise RuntimeError(f"HTTP {e.code}: {detail}")

    def _download(self, path: str, dest: Path):
        url = f"{self.server}{path}"
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(dest, "wb") as f:
                shutil.copyfileobj(resp, f)

    # ============ 注册与心跳 ============

    def register(self) -> bool:
        info = {
            "token": self.token,
            "hostname": platform.node(),
            "os_type": platform.system(),
            "os_version": platform.release(),
            "cpu_cores": os.cpu_count() or 0,
            "agent_version": AGENT_VERSION,
        }
        try:
            res = self._request("POST", "/api/v1/nodes/agent/register", info, timeout=30)
            self.node_id = res.get("node_id")
            self.poll_interval = res.get("task_poll_interval") or self.poll_interval
            log(f"注册成功 node_id={self.node_id}")
            return True
        except Exception as e:
            log(f"注册失败: {e}")
            return False

    def heartbeat_once(self):
        if not self.node_id:
            return
        try:
            self._request(
                "POST",
                "/api/v1/nodes/agent/heartbeat",
                {"node_id": self.node_id, "token": self.token},
                timeout=15,
            )
        except Exception as e:
            log(f"心跳失败: {e}")

    def _heartbeat_loop(self):
        while True:
            self.heartbeat_once()
            time.sleep(30)

    # ============ 任务执行 ============

    def poll_task(self):
        try:
            res = self._request(
                "GET",
                f"/api/v1/nodes/agent/tasks?node_id={self.node_id}&long_poll=1",
                timeout=35,
            )
            return res.get("task")
        except Exception as e:
            log(f"领取任务失败: {e}")
            return None

    def _task_status(self, task_id):
        try:
            res = self._request(
                "GET",
                f"/api/v1/nodes/agent/tasks/{task_id}/status"
                f"?node_id={self.node_id}",
                timeout=15,
            )
            return res.get("stop_requested", False)
        except Exception:
            return False

    def _upload_logs(self, task_id, text: str):
        if not text:
            return
        try:
            self._request(
                "POST",
                f"/api/v1/nodes/agent/tasks/{task_id}/logs",
                {"node_id": self.node_id, "logs": text},
                timeout=15,
            )
        except Exception as e:
            log(f"日志上报失败: {e}")

    def _report(self, task_id, status, pages, items, errors, logs_text, error_message=None):
        try:
            self._request(
                "POST",
                f"/api/v1/nodes/agent/tasks/{task_id}/report",
                {
                    "node_id": self.node_id,
                    "status": status,
                    "pages_crawled": pages,
                    "items_scraped": items,
                    "errors_count": errors,
                    "error_message": error_message,
                    "logs": logs_text,
                },
                timeout=30,
            )
            log(f"任务 {task_id} 回报: {status}")
        except Exception as e:
            log(f"任务回报失败: {e}")

    def execute_task(self, task):
        task_id = task["task_id"]
        spider_name = task.get("spider_name") or ""
        entry_file = task.get("entry_file") or "run.py"
        log(f"开始执行任务 {task_id}: {spider_name}")

        workspace = Path(tempfile.mkdtemp(prefix=f"crawlo-agent-{task_id}-"))
        code_archive = workspace / "code.tar.gz"

        try:
            # 1. 下载代码
            self._download(
                f"/api/v1/nodes/agent/tasks/{task_id}/code"
                f"?node_id={self.node_id}",
                code_archive,
            )
            with tarfile.open(code_archive, "r:gz") as tar:
                # 安全校验：拒绝路径穿越（.. / 绝对路径 / 符号链接逃逸），
                # 所有 Python 版本统一手工校验，避免 3.10/3.11 fallback 漏洞
                for member in tar.getmembers():
                    name = member.name.replace("\\", "/")
                    if name.startswith("/") or ".." in name.split("/"):
                        raise ValueError(f"代码包包含非法路径: {member.name}")
                    if member.issym() or member.islnk():
                        raise ValueError(f"代码包包含链接文件: {member.name}")
                try:
                    tar.extractall(workspace, filter="data")
                except TypeError:
                    # Python < 3.12 无 filter 参数：已手工校验成员，安全调用
                    tar.extractall(workspace)
            code_dir = workspace / "code"
            log(f"代码已下载: {code_dir}")

            # 2. 隔离环境：venv 内装 crawlo 与项目依赖，避免多爬虫互相污染
            #    安装阶段也响应停止指令（每步前检查 stop_requested）
            if self._task_status(task_id):
                log(f"任务 {task_id} 在准备阶段收到停止指令")
                self._report(task_id, "cancelled", 0, 0, 0, "")
                return
            venv_python = self._create_venv(workspace)
            if self._task_status(task_id):
                log(f"任务 {task_id} 在准备阶段收到停止指令")
                self._report(task_id, "cancelled", 0, 0, 0, "")
                return
            self._ensure_crawlo(venv_python)
            if self._task_status(task_id):
                log(f"任务 {task_id} 在准备阶段收到停止指令")
                self._report(task_id, "cancelled", 0, 0, 0, "")
                return
            self._install_requirements(code_dir, venv_python)

            # 3. 构建启动命令（支持任务参数 args）
            run_args = [venv_python, entry_file]
            task_args = task.get("args") or ""
            if task_args:
                run_args.extend(shlex.split(task_args))

            env = os.environ.copy()
            env.update({
                "TASK_ID": str(task_id),
                "SPIDER_NAME": spider_name,
                "PYTHONUNBUFFERED": "1",
                "PYTHONIOENCODING": "utf-8",
            })
            task_env = task.get("env") or {}
            if isinstance(task_env, dict):
                env.update({str(k): str(v) for k, v in task_env.items() if k and v is not None})
            proc = subprocess.Popen(
                run_args,
                cwd=str(code_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            log_lines = []
            stopped = False
            last_upload = time.time()
            last_stop_check = time.time()

            while True:
                line = proc.stdout.readline()
                if line:
                    log_lines.append(line)
                    if time.time() - last_upload > 2:
                        self._upload_logs(task_id, "".join(log_lines[-200:]))
                        last_upload = time.time()
                    # 有持续输出时也定期检查停止指令
                    if time.time() - last_stop_check > 1:
                        if self._task_status(task_id):
                            log(f"任务 {task_id} 收到停止指令")
                            proc.terminate()
                            try:
                                proc.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                            stopped = True
                            break
                        last_stop_check = time.time()
                elif proc.poll() is not None:
                    break
                else:
                    # 没有新输出且进程仍在运行：检查停止标记
                    if self._task_status(task_id):
                        log(f"任务 {task_id} 收到停止指令")
                        proc.terminate()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        stopped = True
                        break
                    time.sleep(0.5)

            # 收集剩余输出
            try:
                rest = proc.stdout.read()
                if rest:
                    log_lines.append(rest)
            except Exception:
                pass

            logs_text = "".join(log_lines)
            if stopped:
                self._report(task_id, "cancelled", 0, 0, 0, logs_text)
                return

            exit_code = proc.returncode
            pages, items, errors = parse_metrics(logs_text)
            status = "success" if exit_code == 0 else "failed"
            error_message = None if exit_code == 0 else f"进程退出码: {exit_code}"
            self._report(task_id, status, pages, items, errors, logs_text, error_message)

        except Exception as e:
            log(f"任务 {task_id} 执行异常: {e}")
            self._report(task_id, "failed", 0, 0, 0, "", str(e))
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def _ensure_template_venv(self) -> Path:
        """确保模板 venv 存在且含 crawlo（一次性创建，后续任务复制即可）。

        缓存目录：~/.crawlo-agent/template_venv/（可由 CRAWLO_AGENT_TEMPLATE_VENV 覆盖）
        重建触发：目录不存在、或模板内 import crawlo 失败（版本升级场景）。
        """
        if os.environ.get("CRAWLO_AGENT_SKIP_CRAWLO_INSTALL", "").lower() in ("1", "true", "yes"):
            return None  # 跳过模式不走缓存

        t_venv = _TEMPLATE_VENV_DIR
        t_python = t_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        t_marker = t_venv / ".installed"

        # 快速路径：模板 venv 存在且标记文件存在 → 视为就绪
        if t_python.exists() and t_marker.exists():
            return t_venv

        # 需要创建/重建模板
        log(f"创建 venv 模板: {t_venv}")
        t_venv.parent.mkdir(parents=True, exist_ok=True)
        if t_venv.exists():
            shutil.rmtree(t_venv)
        try:
            r = subprocess.run([sys.executable, "-m", "venv", str(t_venv)],
                               capture_output=True, text=True, timeout=180)
            if r.returncode != 0:
                raise RuntimeError(r.stderr)
        except Exception as e:
            log(f"模板 venv 创建失败（回退每任务独立创建）: {e}")
            return None

        # 安装 crawlo + aiomysql
        log("模板 venv 安装 crawlo（仅首次，后续任务直接复制）...")
        try:
            subprocess.run([str(t_python), "-m", "pip", "install", "--quiet",
                            "crawlo", "aiomysql", "-i", PIP_INDEX], timeout=600)
            t_marker.write_text(AGENT_VERSION)
            log("venv 模板就绪")
        except Exception as e:
            log(f"模板安装失败（回退每任务独立创建）: {e}")
            shutil.rmtree(t_venv, ignore_errors=True)
            return None

        return t_venv

    def _create_venv(self, base_dir: Path) -> str:
        """创建任务级虚拟环境：优先从模板复制（秒级），否则新建 + 安装。"""
        venv_dir = base_dir / ".venv"
        t_venv = self._ensure_template_venv()

        if t_venv is not None:
            # 模板命中：直接复制（~0.5s vs 30s+新建+pip install）
            try:
                shutil.copytree(str(t_venv), str(venv_dir), symlinks=True)
                python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                log(f"venv 从模板复制（秒级）: {python}")
                return str(python)
            except Exception as e:
                log(f"模板复制失败，回退新建: {e}")

        # 模板不可用：新建（原有逻辑）
        created = False
        try:
            r = subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                capture_output=True, text=True, timeout=180,
            )
            created = r.returncode == 0
        except Exception as e:
            log(f"python -m venv 失败: {e}")
        if not created:
            log("python -m venv 不可用，尝试 virtualenv")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--quiet", "virtualenv", "-i", PIP_INDEX],
                    timeout=300,
                )
                subprocess.run(
                    [sys.executable, "-m", "virtualenv", str(venv_dir)],
                    capture_output=True, text=True, timeout=180,
                )
            except Exception as e:
                raise RuntimeError(f"虚拟环境创建失败: {e}")

        python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python.exists():
            raise RuntimeError(f"虚拟环境 python 不存在: {python}")
        log(f"虚拟环境已创建: {python}")
        return str(python)

    def _ensure_crawlo(self, python: str):
        """确保 venv 内可导入 crawlo（缺失则自动 pip 安装）"""
        # 测试/开发逃生阀：跳过 crawlo 安装（e2e 回归用纯标准库爬虫，无需框架）
        if os.environ.get("CRAWLO_AGENT_SKIP_CRAWLO_INSTALL", "").lower() in ("1", "true", "yes"):
            log("跳过 crawlo 安装（CRAWLO_AGENT_SKIP_CRAWLO_INSTALL 已设置）")
            return
        check = subprocess.run(
            [python, "-c", "import crawlo"],
            capture_output=True,
        )
        if check.returncode == 0:
            return

        log("检测到 crawlo 未安装，自动安装中...")
        try:
            subprocess.run(
                [python, "-m", "pip", "install", "--quiet", "crawlo", "aiomysql", "-i", PIP_INDEX],
                timeout=600,
            )
            log("crawlo 安装完成")
        except Exception as e:
            log(f"crawlo 自动安装失败: {e}")

    def _install_requirements(self, code_dir, python: str):
        """安装项目 requirements.txt（如存在，装进 venv）"""
        req_file = os.path.join(str(code_dir), "requirements.txt")
        if not os.path.exists(req_file):
            return
        log(f"检测到 requirements.txt，安装依赖...")
        try:
            subprocess.run(
                [python, "-m", "pip", "install", "-r", req_file, "-i", PIP_INDEX],
                timeout=600,
            )
            log("项目依赖安装完成")
        except Exception as e:
            log(f"项目依赖安装失败: {e}")

    # ============ 主循环 ============

    def run(self):
        log(f"CrawloPilot Agent v{AGENT_VERSION} 启动, server={self.server}")
        while not self.register():
            time.sleep(5)

        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

        while True:
            task = self.poll_task()
            if task:
                self.execute_task(task)
            # 长轮询：空载由服务端挂起最多 25s，无需本地 sleep 兜底


def parse_metrics(log_text: str):
    """解析日志中的 pages/items/errors（兼容 crawlo 1.6/1.7 统计格式）"""
    pages = items = errors = 0
    if not log_text:
        return pages, items, errors

    crawled = re.compile(
        r"(?:Crawled|crawled|已爬取)\s+(\d+)\s+(?:pages?|页).*?(\d+)\s+(?:items?|条)",
        re.IGNORECASE,
    )
    alt = re.compile(r"(\d+)\s+pages?.*?(\d+)\s+items?", re.IGNORECASE)
    items_new = re.compile(r"['\"]crawlo:item_successful_count['\"]\s*:\s*(\d+)")
    items_old = re.compile(r"['\"]item_successful_count['\"]\s*:\s*(\d+)")
    pages_new = re.compile(r"['\"]crawlo:response_received_count['\"]\s*:\s*(\d+)")
    pages_old = re.compile(r"['\"]response_received_count['\"]\s*:\s*(\d+)")

    m = list(crawled.finditer(log_text))
    if m:
        pages = int(m[-1].group(1))
        items = int(m[-1].group(2))
    else:
        am = list(alt.finditer(log_text))
        if am:
            pages = int(am[-1].group(1))
            items = int(am[-1].group(2))

    if not items:
        mi = items_new.search(log_text) or items_old.search(log_text)
        if mi:
            items = int(mi.group(1))
    if not pages:
        mp = pages_new.search(log_text) or pages_old.search(log_text)
        if mp:
            pages = int(mp.group(1))

    errors = len(re.findall(r"\[(?:ERROR|WARNING)\]", log_text, re.IGNORECASE))
    return pages, items, errors


def main():
    parser = argparse.ArgumentParser(description="CrawloPilot Agent")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="管理服务器地址，如 http://127.0.0.1:18000")
    parser.add_argument("--token", required=True, help="节点注册令牌")
    parser.add_argument("--poll-interval", type=int, default=5, help="任务轮询间隔（秒）")
    args = parser.parse_args()

    client = AgentClient(args.server, args.token, args.poll_interval)
    client.run()


if __name__ == "__main__":
    main()
