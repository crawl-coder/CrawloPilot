"""
Git 操作服务

在爬虫代码目录（保留 .git 的完整仓库）上执行版本控制操作：
status / branches / commit / push / pull / checkout

安全约束:
- 凭据不持久化: 密码/Token 仅在单次 push/pull 时拼入 URL，SSH 私钥写临时文件用完即删
- 所有命令有超时控制，超时杀整个进程组
"""
import os
import shutil
import signal
import subprocess
import tempfile
import logging
from typing import Optional, Tuple, Dict, Any, List
from urllib.parse import urlparse, urlunparse, quote

logger = logging.getLogger(__name__)


class GitOperationError(Exception):
    """Git 操作失败（message 可直接返回给前端）"""
    pass


def _run_git(cmd: List[str], cwd: str, env: dict = None, timeout: int = 120) -> Tuple[int, str, str]:
    """运行 git 命令，返回 (returncode, stdout, stderr)；超时杀进程组"""
    proc = subprocess.Popen(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env, start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except OSError:
            pass
        proc.communicate()
        raise GitOperationError(f"Git 操作超时（{timeout} 秒）")
    return proc.returncode, (stdout or "").strip(), (stderr or "").strip()


class GitService:
    """单个爬虫代码仓库的 Git 操作封装"""

    def __init__(self, spider, code_dir: str):
        self.spider = spider
        self.code_dir = code_dir

    # ==================== 基础 ====================

    def is_repo(self) -> bool:
        return os.path.isdir(os.path.join(self.code_dir, ".git"))

    def _git(self, args: List[str], timeout: int = 120, env_extra: dict = None) -> Tuple[int, str, str]:
        env = dict(os.environ)
        if env_extra:
            env.update(env_extra)
        return _run_git(["git"] + args, cwd=self.code_dir, env=env, timeout=timeout)

    def _require_repo(self):
        if not self.is_repo():
            raise GitOperationError("该爬虫代码目录不是 Git 仓库（早期克隆未保留 .git），请在详情页重新克隆")

    def _current_branch(self) -> str:
        rc, branch, err = self._git(["rev-parse", "--abbrev-ref", "HEAD"])
        if rc != 0 or not branch:
            raise GitOperationError(f"无法读取当前分支: {err}")
        return branch

    def _ensure_identity(self):
        """确保仓库有提交身份（merge/pull 产生提交时需要）"""
        rc, name, _ = self._git(["config", "user.name"])
        if rc != 0 or not name:
            self._git(["config", "user.name", "CrawloPilot"])
        rc, email, _ = self._git(["config", "user.email"])
        if rc != 0 or not email:
            self._git(["config", "user.email", "bot@crawlo.local"])

    # ==================== 认证 ====================

    def _auth_context(self) -> Tuple[str, dict, Optional[Any]]:
        """
        生成带认证信息的上下文: (remote_url, env_extra, cleanup_fn)
        - 密码/Token: 拼入 URL（仅用于单次命令，不写回 config）
        - SSH: 私钥写临时文件 + GIT_SSH_COMMAND，返回清理函数
        """
        spider = self.spider
        clean_url = spider.git_url or ""

        if spider.git_auth_type == "password" and (spider.git_username or spider.git_password):
            parsed = urlparse(clean_url)
            if parsed.scheme in ("http", "https"):
                username = quote(spider.git_username or "x-access-token", safe="")
                password = quote(spider.git_password or "", safe="")
                netloc = f"{username}:{password}@{parsed.netloc}"
                cred_url = urlunparse(
                    (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
                )
                return cred_url, {}, None

        if spider.git_auth_type == "ssh" and spider.git_ssh_key:
            fd, key_path = tempfile.mkstemp(prefix="crawlo_git_key_")
            os.close(fd)
            try:
                with open(key_path, "w", encoding="utf-8") as f:
                    f.write(spider.git_ssh_key)
                os.chmod(key_path, 0o600)
            except OSError as e:
                try:
                    os.unlink(key_path)
                except OSError:
                    pass
                raise GitOperationError(f"SSH 私钥写入失败: {e}")

            env_extra = {
                "GIT_SSH_COMMAND": (
                    f"ssh -i {key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
                )
            }

            def cleanup():
                try:
                    os.unlink(key_path)
                except OSError:
                    pass

            return clean_url, env_extra, cleanup

        return clean_url, {}, None

    # ==================== 查询 ====================

    def status(self) -> Dict[str, Any]:
        """仓库状态: 当前分支/改动文件/领先落后"""
        self._require_repo()
        branch = self._current_branch()

        rc, porcelain, err = self._git(["status", "--porcelain"])
        if rc != 0:
            raise GitOperationError(f"读取状态失败: {err}")
        changed = [line for line in porcelain.splitlines() if line.strip()]

        ahead = behind = 0
        rc, track, _ = self._git(["rev-list", "--left-right", "--count", "HEAD...@{upstream}"])
        if rc == 0 and track:
            parts = track.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                ahead, behind = int(parts[0]), int(parts[1])

        return {
            "branch": branch,
            "clean": len(changed) == 0,
            "changed_count": len(changed),
            "changed_files": changed[:100],
            "ahead": ahead,
            "behind": behind,
        }

    def branches(self) -> Dict[str, Any]:
        """分支列表: 当前/本地/远程"""
        self._require_repo()
        current = self._current_branch()

        rc, local_out, err = self._git(["branch", "--format=%(refname:short)"])
        if rc != 0:
            raise GitOperationError(f"读取分支失败: {err}")
        local = [b.strip() for b in local_out.splitlines() if b.strip()]

        rc, remote_out, _ = self._git(["branch", "-r", "--format=%(refname:short)"])
        remote = []
        if rc == 0:
            for line in remote_out.splitlines():
                name = line.strip()
                # 跳过符号引用（origin/HEAD 短名为裸 "origin"，不含 /）
                if name and "->" not in name and "/" in name:
                    remote.append(name)

        return {"current": current, "local": local, "remote": remote}

    # ==================== 写操作 ====================

    def commit(self, message: str, author_name: str = None, author_email: str = None) -> Dict[str, Any]:
        """暂存全部改动并提交"""
        self._require_repo()
        if not message or not message.strip():
            raise GitOperationError("提交信息不能为空")

        rc, _, err = self._git(["add", "-A"])
        if rc != 0:
            raise GitOperationError(f"暂存失败: {err}")

        rc, staged, _ = self._git(["diff", "--cached", "--name-only"])
        if rc != 0:
            raise GitOperationError("读取暂存区失败")
        if not staged.strip():
            raise GitOperationError("没有需要提交的改动")

        args = []
        if author_name:
            args += ["-c", f"user.name={author_name}"]
        if author_email:
            args += ["-c", f"user.email={author_email}"]
        args += ["commit", "-m", message.strip()]

        rc, out, err = self._git(args)
        if rc != 0:
            raise GitOperationError(err or "提交失败")

        files_count = len([l for l in staged.splitlines() if l.strip()])
        return {"message": "提交成功", "files_count": files_count, "output": out}

    def push(self) -> Dict[str, Any]:
        """推送当前分支到远程"""
        self._require_repo()
        branch = self._current_branch()
        url, env_extra, cleanup = self._auth_context()
        try:
            rc, out, err = self._git(
                ["push", "-u", url, f"HEAD:{branch}"],
                timeout=180, env_extra=env_extra,
            )
        finally:
            if cleanup:
                cleanup()

        if rc != 0:
            raise GitOperationError(err or "推送失败")
        return {"message": f"已推送到远程分支 {branch}", "branch": branch, "output": out or err}

    def pull(self) -> Dict[str, Any]:
        """从远程拉取当前分支"""
        self._require_repo()
        branch = self._current_branch()

        # 有未提交改动时禁止 pull，避免合并冲突覆盖本地修改
        status = self.status()
        if not status["clean"]:
            raise GitOperationError(f"有 {status['changed_count']} 个未提交的改动，请先提交或放弃后再拉取")

        self._ensure_identity()
        url, env_extra, cleanup = self._auth_context()
        try:
            rc, out, err = self._git(
                ["pull", "--no-rebase", url, branch],
                timeout=180, env_extra=env_extra,
            )
        finally:
            if cleanup:
                cleanup()

        if rc != 0:
            detail = err or out or "拉取失败"
            if "CONFLICT" in detail or "conflict" in detail.lower():
                raise GitOperationError("拉取产生冲突，请在服务器上手动处理后再试")
            raise GitOperationError(detail)
        return {"message": "拉取完成", "branch": branch, "output": out}

    def checkout(self, branch: str, create: bool = False) -> Dict[str, Any]:
        """切换分支; create=True 时基于当前分支新建"""
        self._require_repo()
        branch = (branch or "").strip()
        if not branch:
            raise GitOperationError("分支名不能为空")

        # 有未提交改动时禁止切换，避免工作区被覆盖
        status = self.status()
        if not status["clean"]:
            raise GitOperationError(f"有 {status['changed_count']} 个未提交的改动，请先提交或放弃后再切换分支")

        info = self.branches()
        if create:
            if branch in info["local"]:
                raise GitOperationError(f"分支 {branch} 已存在")
            rc, out, err = self._git(["checkout", "-b", branch])
        else:
            if branch in info["local"]:
                rc, out, err = self._git(["checkout", branch])
            elif f"origin/{branch}" in info["remote"]:
                # 远程分支: 建立本地跟踪分支
                rc, out, err = self._git(["checkout", "-b", branch, "--track", f"origin/{branch}"])
            else:
                raise GitOperationError(f"分支 {branch} 不存在（本地和远程都没有）")

        if rc != 0:
            raise GitOperationError(err or "切换分支失败")
        return {"message": f"已切换到分支 {branch}", "branch": branch, "output": out}


# ==================== 克隆辅助（供 spiders.py 复用） ====================

def sanitize_remote_url(code_dir: str, clean_url: str):
    """克隆后重置 remote URL 为无凭据版本，避免凭据落盘到 .git/config"""
    if not clean_url:
        return
    _run_git(["git", "remote", "set-url", "origin", clean_url], cwd=code_dir, timeout=30)


def set_repo_identity(code_dir: str, name: str, email: str):
    """克隆后写入仓库级提交身份"""
    _run_git(["git", "config", "user.name", name or "CrawloPilot"], cwd=code_dir, timeout=30)
    _run_git(["git", "config", "user.email", email or "bot@crawlo.local"], cwd=code_dir, timeout=30)
