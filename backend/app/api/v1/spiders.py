"""
爬虫管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.core.time_utils import cn_now
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Spider, Project, Node
from app.schemas.spider import SpiderCreate, SpiderUpdate, SpiderInDB
from app.services.upload_service import UploadService
import os
import re

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/spiders", tags=["爬虫管理"])


# ==================== Pydantic Schemas ====================

from pydantic import BaseModel


class RunSpiderRequest(BaseModel):
    """运行爬虫请求"""
    node_id: Optional[int] = None  # 指定目标节点，None=本地运行
    memory_limit: Optional[str] = None  # Docker 内存限制，如 "512m" / "1g"
    cpu_limit: Optional[float] = None   # Docker CPU 配额（核数）



# ==================== 爬虫管理 ====================

@router.get("")
async def list_spiders(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取爬虫列表(带分页)"""
    from app.core.pagination import clamp_pagination
    skip, limit = clamp_pagination(skip, limit, default_limit=50)
    query = db.query(Spider)
    
    if project_id:
        query = query.filter(Spider.project_id == project_id)
    if status:
        query = query.filter(Spider.status == status)
    
    # 获取总数
    total = query.count()
    
    # 获取分页数据（按创建时间倒序，最新在前）
    spiders = (
        query.order_by(Spider.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return {
        "total": total,
        "items": spiders,
        "skip": skip,
        "limit": limit
    }


@router.get("/{spider_id}", response_model=SpiderInDB)
async def get_spider(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取爬虫详情"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    # 查询部署节点信息（按 spider_id 关联，爬虫改名不受影响）
    from app.models import Schedule, Node
    schedules = db.query(Schedule).filter(
        Schedule.spider_id == spider.id,
        Schedule.node_id.isnot(None)
    ).all()
    
    deploy_nodes = []
    for s in schedules:
        node = db.query(Node).get(s.node_id)
        if node:
            deploy_nodes.append({
                "id": node.id,
                "name": node.name,
                "host": node.ssh_host or node.host,
                "port": node.ssh_port or node.port,
                "status": node.status
            })
    
    result = {
        "id": spider.id,
        "name": spider.name,
        "project_id": spider.project_id,
        "description": spider.description,
        "spider_type": spider.spider_type,
        "status": spider.status,
        "entry_file": spider.entry_file,
        "spider_name": spider.spider_name,
        "git_url": spider.git_url,
        "git_auth_type": spider.git_auth_type,
        "git_username": spider.git_username,
        # 秘密字段不回传（前端编辑表单不消费这些值）
        "git_password": None,
        "git_ssh_key": None,
        "git_passphrase": None,
        "git_branch": spider.git_branch,
        "git_credential_id": spider.git_credential_id,
        "code_path": spider.code_path,
        "config": spider.config,

        "last_run_at": spider.last_run_at,
        "last_run_status": spider.last_run_status,
        "run_count": spider.run_count,
        "success_count": spider.success_count,
        "error_count": spider.error_count,
        "created_at": spider.created_at,
        "updated_at": spider.updated_at,
        "deploy_nodes": deploy_nodes
    }
    return result


@router.post("", response_model=SpiderInDB, status_code=status.HTTP_201_CREATED)
async def create_spider(
    spider_data: SpiderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建爬虫"""
    # 验证项目是否存在
    project = db.query(Project).filter(Project.id == spider_data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 检查爬虫名称是否重复
    existing = db.query(Spider).filter(
        Spider.project_id == spider_data.project_id,
        Spider.name == spider_data.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该项目下已存在同名爬虫")
    
    # 解析 Git 凭据来源：共享凭据池 > 个人凭据 > 手动填写
    data = spider_data.dict(exclude={"use_my_git_credential"})
    if data.get("git_credential_id"):
        from app.models import GitCredential
        cred = db.query(GitCredential).filter(
            GitCredential.id == data["git_credential_id"],
            GitCredential.is_active == True,  # noqa: E712
        ).first()
        if not cred:
            raise HTTPException(status_code=400, detail="所选共享 Git 凭据不存在或已停用")
        # 使用共享凭据时清空内联凭据，避免双份凭据歧义
        data["git_username"] = None
        data["git_password"] = None
        data["git_ssh_key"] = None
        data["git_passphrase"] = None
    elif spider_data.use_my_git_credential and data.get("git_url"):
        from app.services.credential_service import unpack_user_credentials
        my_cred = unpack_user_credentials(current_user)
        if not my_cred:
            raise HTTPException(status_code=400, detail="您还未配置个人 Git 凭据，请先在个人中心配置")
        data["git_auth_type"] = my_cred.get("auth_type") or "password"
        data["git_username"] = my_cred.get("username") or None
        data["git_password"] = my_cred.get("password") or None
        data["git_ssh_key"] = my_cred.get("ssh_key") or None
        data["git_passphrase"] = my_cred.get("passphrase") or None
        if not data.get("git_branch") and my_cred.get("default_branch"):
            data["git_branch"] = my_cred["default_branch"]

    # 内联 Git 凭据加密落库（幂等：已是密文不重复加密）
    from app.core.crypto import encrypt_if_plain
    for field in ("git_password", "git_ssh_key", "git_passphrase"):
        data[field] = encrypt_if_plain(data.get(field))

    # 创建爬虫
    new_spider = Spider(
        **data,
        status="active"
    )

    db.add(new_spider)
    db.commit()
    db.refresh(new_spider)
    
    return new_spider


@router.put("/{spider_id}", response_model=SpiderInDB)
async def update_spider(
    spider_id: int,
    spider_data: SpiderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新爬虫"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    # 更新字段
    update_data = spider_data.dict(exclude_unset=True)

    # 校验共享凭据引用（显式传 null 表示清除引用）
    if "git_credential_id" in update_data and update_data["git_credential_id"]:
        from app.models import GitCredential
        cred = db.query(GitCredential).filter(
            GitCredential.id == update_data["git_credential_id"],
            GitCredential.is_active == True,  # noqa: E712
        ).first()
        if not cred:
            raise HTTPException(status_code=400, detail="所选共享 Git 凭据不存在或已停用")

    for key, value in update_data.items():
        setattr(spider, key, value)

    # 生命周期同步：爬虫改名 → 同步冗余展示列 schedule.spider_name
    if "name" in update_data:
        from app.models import Schedule
        db.query(Schedule).filter(Schedule.spider_id == spider.id).update(
            {"spider_name": spider.spider_name or spider.name}
        )
    
    db.commit()
    db.refresh(spider)
    
    return spider


@router.delete("/{spider_id}")
async def delete_spider(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除爬虫"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")

    # 生命周期同步：删除爬虫 → 级联删除其调度并移除 job（任务历史保留）
    from app.models import Schedule, TaskInstance
    from app.services.scheduler_service import get_scheduler_service
    scheduler = get_scheduler_service()
    for sched in db.query(Schedule).filter(Schedule.spider_id == spider.id).all():
        scheduler.remove_schedule(sched.id)
        # 解除任务历史对调度的外键引用（历史保留，仅断开关联）
        db.query(TaskInstance).filter(TaskInstance.schedule_id == sched.id).update(
            {"schedule_id": None}, synchronize_session=False
        )
        db.delete(sched)
    db.flush()

    # 解除任务历史对爬虫的外键引用（历史保留，仅断开关联）
    db.query(TaskInstance).filter(TaskInstance.spider_id == spider.id).update(
        {"spider_id": None}, synchronize_session=False
    )

    db.delete(spider)
    db.commit()
    
    return {"message": "删除成功"}


# ==================== 爬虫运行控制 ====================

@router.post("/{spider_id}/run")
async def run_spider(
    spider_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    body: RunSpiderRequest = RunSpiderRequest(),
):
    """运行爬虫（复用统一任务创建/分发服务）"""
    from app.services.task_service import create_and_run_task

    try:
        return create_and_run_task(
            db,
            spider_id=spider_id,
            node_id=body.node_id,
            background_tasks=background_tasks,
            memory_limit=body.memory_limit,
            cpu_limit=body.cpu_limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{spider_id}/stop")
async def stop_spider(
    spider_id: int,
    task_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """停止爬虫"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    from app.models import TaskInstance, TaskStatus
    
    if task_id:
        # 停止指定任务
        task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        target_tasks = [task]
    else:
        # 停止该爬虫所有运行中的任务
        target_tasks = db.query(TaskInstance).filter(
            TaskInstance.spider_id == spider_id,
            TaskInstance.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
        ).all()
    
    stopped = []
    errors = []
    
    for task in target_tasks:
        try:
            # 按部署模式分发对应执行器（docker/ssh/agent/local），
            # 避免 docker 任务只调 local executor 导致容器/远程进程无法真正停止
            from app.services.executor_registry import get_executor_for_task
            executor = get_executor_for_task(task)
            await executor.stop_task(str(task.id))

            # executor 已更新数据库状态，这里作为兜底
            if task.status not in [TaskStatus.CANCELLED, TaskStatus.SUCCESS, TaskStatus.FAILED]:
                task.status = TaskStatus.CANCELLED
                task.finished_at = cn_now()
                if task.started_at:
                    task.duration = (task.finished_at - task.started_at).total_seconds()
            stopped.append(str(task.id))
            
        except Exception as e:
            errors.append(f"Task {task.id}: {str(e)}")
    
    db.commit()
    
    return {
        "message": f"已停止 {len(stopped)} 个任务",
        "spider_id": spider_id,
        "stopped_tasks": stopped,
        "errors": errors if errors else None
    }


# ==================== 爬虫代码管理 ====================

@router.get("/{spider_id}/files/tree")
async def get_spider_file_tree(
    spider_id: int,
    path: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取爬虫文件树"""
    from app.services.file_service import FileService
    
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    # 获取爬虫代码目录
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    if not spider_code_dir or not os.path.exists(spider_code_dir):
        return {"error": "爬虫代码目录不存在，请先上传代码"}
    
    try:
        file_service = FileService(spider_code_dir)
        tree = file_service.get_file_tree(path, max_depth=3)
        return tree
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{spider_id}/files/content")
async def get_spider_file_content(
    spider_id: int,
    path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取爬虫文件内容"""
    from app.services.file_service import FileService
    
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    if not spider_code_dir:
        raise HTTPException(status_code=400, detail="爬虫代码目录不存在")
    
    file_service = FileService(spider_code_dir)
    result = file_service.read_file(path)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/{spider_id}/files/content")
async def save_spider_file_content(
    spider_id: int,
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保存爬虫文件内容"""
    from app.services.file_service import FileService
    path = request.get("path")
    content = request.get("content")
    if not path:
        raise HTTPException(status_code=422, detail="缺少 path 参数")
    if content is None:
        raise HTTPException(status_code=422, detail="缺少 content 参数")
    
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    if not spider_code_dir:
        raise HTTPException(status_code=400, detail="爬虫代码目录不存在")
    
    file_service = FileService(spider_code_dir)
    result = file_service.write_file(path, content)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/{spider_id}/files/create")
async def create_spider_file(
    spider_id: int,
    path: str,
    is_directory: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建爬虫文件或目录"""
    from app.services.file_service import FileService
    
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    if not spider_code_dir:
        raise HTTPException(status_code=400, detail="爬虫代码目录不存在")
    
    file_service = FileService(spider_code_dir)
    result = file_service.create_file(path, is_directory)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.delete("/{spider_id}/files")
async def delete_spider_file(
    spider_id: int,
    path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除爬虫文件或目录"""
    from app.services.file_service import FileService
    
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    upload_service = UploadService()
    spider_code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    if not spider_code_dir:
        raise HTTPException(status_code=400, detail="爬虫代码目录不存在")
    
    file_service = FileService(spider_code_dir)
    result = file_service.delete_file(path)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.post("/{spider_id}/git/clone")
async def clone_spider_git_repo(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    从 Git 仓库克隆代码到爬虫代码目录

    - 支持公开仓库（http/https）与凭据仓库（密码/Token 或 SSH 私钥）
    - 克隆到 uploads/project_{id}/spider_{id}/，移除 .git 只保留代码
    """
    from urllib.parse import urlparse, urlunparse, quote
    import subprocess, tempfile, shutil, signal
    from app.services.file_service import FileService

    def _run_git_clone(cmd, timeout=180):
        """运行 git clone，超时/失败时清理整个进程组"""
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                pass
            proc.communicate()
            return "Git 克隆超时（180 秒）"
        if proc.returncode != 0:
            return (stderr or stdout).strip()
        return None

    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    if not spider.git_url:
        raise HTTPException(status_code=400, detail="该爬虫未配置 Git 仓库地址")

    git_url = spider.git_url.strip()
    parsed = urlparse(git_url)
    # 只允许 http/https/ssh/git 协议，或 scp 风格 git@host:path；拒绝 file:// 与本地路径
    scp_like = bool(re.match(r"^[^/@\s]+@[^:\s]+:.+", git_url))
    if not scp_like and parsed.scheme not in ("http", "https", "ssh", "git"):
        raise HTTPException(status_code=400, detail="不支持的 Git 地址协议，仅支持 http/https/ssh")

    # 解析实际使用的凭据（共享凭据池 > 爬虫内联凭据）
    from app.services.credential_service import resolve_spider_git_credentials
    git_cred = resolve_spider_git_credentials(db, spider)

    # 组装克隆 URL / SSH 环境
    clone_url = git_url
    env = dict(os.environ)
    key_path = None
    askpass_path = None
    if git_cred.git_auth_type == "password" and (git_cred.git_username or git_cred.git_password):
        if parsed.scheme in ("http", "https"):
            username = quote(git_cred.git_username or "x-access-token", safe="")
            password = quote(git_cred.git_password or "", safe="")
            netloc = f"{username}:{password}@{parsed.netloc}"
            clone_url = urlunparse(
                (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
            )
    elif git_cred.git_auth_type == "ssh" and git_cred.git_ssh_key:
        try:
            key_fd, key_path = tempfile.mkstemp(prefix="crawlo_git_key_")
            os.close(key_fd)
            with open(key_path, "w", encoding="utf-8") as f:
                f.write(git_cred.git_ssh_key)
            os.chmod(key_path, 0o600)
            env["GIT_SSH_COMMAND"] = (
                f"ssh -i {key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
            )
            # 私钥密码：SSH_ASKPASS 方式提供（密码走环境变量，不落明文脚本）
            if git_cred.git_passphrase:
                ask_fd, askpass_path = tempfile.mkstemp(prefix="crawlo_git_askpass_", text=True)
                with os.fdopen(ask_fd, "w", encoding="utf-8") as f:
                    f.write('#!/bin/sh\nprintf "%s" "$CRAWLO_GIT_PASS"\n')
                os.chmod(askpass_path, 0o700)
                env["SSH_ASKPASS"] = askpass_path
                env["SSH_ASKPASS_REQUIRE"] = "force"  # OpenSSH 8.4+
                env["CRAWLO_GIT_PASS"] = git_cred.git_passphrase
        except OSError as e:
            if key_path:
                os.unlink(key_path)
            raise HTTPException(status_code=500, detail=f"SSH 私钥写入失败: {e}")

    upload_service = UploadService()
    spider_code_dir = os.path.join(
        upload_service.upload_base_dir,
        f"project_{spider.project_id}",
        f"spider_{spider.id}",
    )
    # 目录非空时不覆盖，避免误删已有代码
    if os.path.isdir(spider_code_dir) and any(os.scandir(spider_code_dir)):
        raise HTTPException(status_code=400, detail="爬虫代码目录非空，请先清空代码目录或删除爬虫后重试")

    tmp_dir = tempfile.mkdtemp(prefix="crawlo_git_clone_")
    try:
        branch = (spider.git_branch or "main").strip()
        # 完整克隆（不用 --depth），保留分支历史以支持切换分支/提交/推送
        cmds = [
            ["git", "clone", "--branch", branch, clone_url, tmp_dir],
            ["git", "clone", clone_url, tmp_dir],
        ]
        last_err = ""
        for i, cmd in enumerate(cmds):
            # 上一次尝试失败可能留下半成品，先清空
            if i > 0:
                for item in os.listdir(tmp_dir):
                    p = os.path.join(tmp_dir, item)
                    shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.unlink(p)
            last_err = _run_git_clone(cmd) or ""
            if not last_err:
                break

        if last_err:
            raise HTTPException(status_code=500, detail=f"Git 克隆失败: {last_err[-500:]}")

        os.makedirs(spider_code_dir, exist_ok=True)
        for item in os.listdir(tmp_dir):
            src = os.path.join(tmp_dir, item)
            dst = os.path.join(spider_code_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

        # 保留 .git 元数据（代码目录即完整仓库，支持提交/推送/切分支）
        # 但需清理 remote URL 中的凭据，避免密码/Token 落盘到 .git/config
        from app.services.git_service import sanitize_remote_url, set_repo_identity
        sanitize_remote_url(spider_code_dir, git_url)
        set_repo_identity(
            spider_code_dir,
            name=current_user.username or "CrawloPilot",
            email=current_user.email or "bot@crawlo.local",
        )

        file_service = FileService(spider_code_dir)
        tree = file_service.get_file_tree("", max_depth=3)
        return {
            "message": "Git 仓库克隆成功",
            "code_dir": spider_code_dir,
            "files": tree,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Git 克隆失败: {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        for p in (key_path, askpass_path):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass


@router.post("/{spider_id}/upload")
async def upload_spider_code(
    spider_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传爬虫代码包（ZIP/TAR），解压到 uploads/project_{id}/spider_{id}/

    - 兼容 ZIP / TAR / TAR.GZ / TAR.BZ2
    - 解压后若根目录只有一个文件夹（常见 ZIP 外层目录），自动拍平一层
    """
    import tempfile, shutil, zipfile, tarfile
    from app.services.file_service import FileService

    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")

    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    allowed_ext = {".zip", ".tar", ".gz", ".bz2"}
    if ext not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}，支持: {sorted(allowed_ext)}",
        )

    upload_service = UploadService()
    spider_code_dir = os.path.join(
        upload_service.upload_base_dir,
        f"project_{spider.project_id}",
        f"spider_{spider.id}",
    )
    # 目录非空时不覆盖，避免误删已有代码
    if os.path.isdir(spider_code_dir) and any(os.scandir(spider_code_dir)):
        raise HTTPException(status_code=400, detail="爬虫代码目录非空，请先清空代码目录或删除爬虫后重试")

    tmp_dir = tempfile.mkdtemp(prefix="crawlo_upload_")
    try:
        content = await file.read()
        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="文件大小不能超过 100MB")
        if not content:
            raise HTTPException(status_code=400, detail="上传文件为空")

        archive_path = os.path.join(tmp_dir, "code" + ext)
        with open(archive_path, "wb") as f:
            f.write(content)

        extract_dir = os.path.join(tmp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        if ext == ".zip":
            with zipfile.ZipFile(archive_path) as zf:
                for member in zf.infolist():
                    # 防 zip-slip：拒绝解压到目标目录之外的路径
                    target = os.path.normpath(os.path.join(extract_dir, member.filename))
                    if not target.startswith(os.path.normpath(extract_dir) + os.sep):
                        raise ValueError(f"非法的压缩包路径: {member.filename}")
                zf.extractall(extract_dir)
        else:
            with tarfile.open(archive_path, "r:*") as tf:
                for member in tf.getmembers():
                    target = os.path.normpath(os.path.join(extract_dir, member.name))
                    if not target.startswith(os.path.normpath(extract_dir) + os.sep):
                        raise ValueError(f"非法的压缩包路径: {member.name}")
                tf.extractall(extract_dir)

        # 去掉 macOS 元数据
        macosx_dir = os.path.join(extract_dir, "__MACOSX")
        if os.path.isdir(macosx_dir):
            shutil.rmtree(macosx_dir, ignore_errors=True)

        # 解压后只有一个顶层文件夹时拍平一层（ZIP 常见结构）
        entries = [e for e in os.listdir(extract_dir) if e != ".DS_Store"]
        if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
            inner = os.path.join(extract_dir, entries[0])
            extract_dir = inner

        os.makedirs(spider_code_dir, exist_ok=True)
        for item in os.listdir(extract_dir):
            src = os.path.join(extract_dir, item)
            dst = os.path.join(spider_code_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

        file_service = FileService(spider_code_dir)
        tree = file_service.get_file_tree("", max_depth=3)
        return {
            "message": "代码上传成功",
            "code_dir": spider_code_dir,
            "files": tree,
        }
    except HTTPException:
        raise
    except ValueError as e:
        # 压缩包内容非法（如 zip-slip 路径穿越）
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"代码上传失败: {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ==================== Git 工作流（提交/推送/拉取/分支） ====================

class GitCommitRequest(BaseModel):
    """提交改动请求"""
    message: str


class GitCheckoutRequest(BaseModel):
    """切换分支请求"""
    branch: str
    create: bool = False


def _get_git_service(spider_id: int, db: Session):
    """获取爬虫对应的 GitService，校验存在性与仓库状态（凭据走统一解析）"""
    from app.services.git_service import GitService
    from app.services.credential_service import resolve_spider_git_credentials

    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")

    upload_service = UploadService()
    code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    if not code_dir or not os.path.exists(code_dir):
        raise HTTPException(status_code=400, detail="爬虫代码目录不存在")

    return spider, GitService(resolve_spider_git_credentials(db, spider), code_dir)


@router.get("/{spider_id}/git/status")
async def get_git_status(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取仓库状态：当前分支/改动文件数/领先落后远程"""
    from app.services.git_service import GitOperationError

    spider, git = _get_git_service(spider_id, db)
    if not git.is_repo():
        return {"is_repo": False, "detail": "代码目录不是 Git 仓库"}
    try:
        return {"is_repo": True, **git.status()}
    except GitOperationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{spider_id}/git/branches")
async def get_git_branches(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取分支列表：当前/本地/远程"""
    from app.services.git_service import GitOperationError

    _, git = _get_git_service(spider_id, db)
    try:
        return git.branches()
    except GitOperationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{spider_id}/git/commit")
async def git_commit(
    spider_id: int,
    body: GitCommitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """提交全部改动（提交人为当前登录用户）"""
    from app.services.git_service import GitOperationError

    _, git = _get_git_service(spider_id, db)
    try:
        return git.commit(
            body.message,
            author_name=current_user.username or "CrawloPilot",
            author_email=current_user.email or "bot@crawlo.local",
        )
    except GitOperationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{spider_id}/git/push")
async def git_push(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """推送当前分支到远程（自动使用爬虫配置的凭据）"""
    from app.services.git_service import GitOperationError

    spider, git = _get_git_service(spider_id, db)
    if not spider.git_url:
        raise HTTPException(status_code=400, detail="该爬虫未配置 Git 仓库地址")
    try:
        return git.push()
    except GitOperationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{spider_id}/git/pull")
async def git_pull(
    spider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """从远程拉取当前分支（有未提交改动时拒绝，冲突时提示手动处理）"""
    from app.services.git_service import GitOperationError

    spider, git = _get_git_service(spider_id, db)
    if not spider.git_url:
        raise HTTPException(status_code=400, detail="该爬虫未配置 Git 仓库地址")
    try:
        return git.pull()
    except GitOperationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{spider_id}/git/checkout")
async def git_checkout(
    spider_id: int,
    body: GitCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """切换分支（create=true 时基于当前分支新建）"""
    from app.services.git_service import GitOperationError

    _, git = _get_git_service(spider_id, db)
    try:
        return git.checkout(body.branch, create=body.create)
    except GitOperationError as e:
        raise HTTPException(status_code=400, detail=str(e))
