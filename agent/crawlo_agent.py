#!/usr/bin/env python3
"""
CrawloPilot Agent - 节点执行代理

运行在目标服务器上，主动连接 CrawloPilot 控制端：
- 注册（token）→ 获得 node_id
- 每 30 秒心跳
- 每 5 秒轮询领取待执行任务
- 下载爬虫代码 → 本地执行 → 实时回报日志 → 回报终态/指标

用法:
    python crawlo_agent.py --server http://控制端:8000 --token <注册令牌>

仅依赖 Python 标准库，可在任意 Linux/macOS/Windows 服务器直接运行。
"""

import argparse
import json
import os
import platform
import re
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

AGENT_VERSION = "0.1.0"
DEFAULT_SERVER = "http://127.0.0.1:8000"
PIP_INDEX = os.environ.get("PIP_INDEX_URL", "https://pypi.tuna.tsinghua.edu.cn/simple")


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
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
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
        req = urllib.request.Request(url)
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
                f"/api/v1/nodes/agent/tasks?node_id={self.node_id}&token={self.token}",
                timeout=30,
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
                f"?node_id={self.node_id}&token={self.token}",
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
                {"node_id": self.node_id, "token": self.token, "logs": text},
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
                    "token": self.token,
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
                f"?node_id={self.node_id}&token={self.token}",
                code_archive,
            )
            with tarfile.open(code_archive, "r:gz") as tar:
                try:
                    tar.extractall(workspace, filter="data")
                except TypeError:
                    # Python < 3.12 无 filter 参数
                    tar.extractall(workspace)
            code_dir = workspace / "code"
            log(f"代码已下载: {code_dir}")

            # 2. 确保 crawlo 可用
            self._ensure_crawlo()
            self._install_requirements(code_dir)

            # 3. 启动进程
            env = os.environ.copy()
            env.update({
                "TASK_ID": str(task_id),
                "SPIDER_NAME": spider_name,
                "PYTHONUNBUFFERED": "1",
                "PYTHONIOENCODING": "utf-8",
            })
            proc = subprocess.Popen(
                [sys.executable, entry_file],
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

    def _ensure_crawlo(self):
        """确保本机可导入 crawlo（缺失则自动 pip 安装）"""
        check = subprocess.run(
            [sys.executable, "-c", "import crawlo"],
            capture_output=True,
        )
        if check.returncode == 0:
            return

        log("检测到 crawlo 未安装，自动安装中...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", "crawlo", "aiomysql", "-i", PIP_INDEX],
                timeout=600,
            )
            log("crawlo 安装完成")
        except Exception as e:
            log(f"crawlo 自动安装失败: {e}")

    def _install_requirements(self, code_dir):
        """安装项目 requirements.txt（如存在）"""
        req_file = os.path.join(str(code_dir), "requirements.txt")
        if not os.path.exists(req_file):
            return
        log(f"检测到 requirements.txt，安装依赖...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", req_file, "-i", PIP_INDEX],
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
            else:
                time.sleep(self.poll_interval)


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
    parser.add_argument("--server", default=DEFAULT_SERVER, help="控制端地址，如 http://127.0.0.1:8000")
    parser.add_argument("--token", required=True, help="节点注册令牌")
    parser.add_argument("--poll-interval", type=int, default=5, help="任务轮询间隔（秒）")
    args = parser.parse_args()

    client = AgentClient(args.server, args.token, args.poll_interval)
    client.run()


if __name__ == "__main__":
    main()
