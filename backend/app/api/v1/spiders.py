"""
爬虫管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
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
    query = db.query(Spider)
    
    if project_id:
        query = query.filter(Spider.project_id == project_id)
    if status:
        query = query.filter(Spider.status == status)
    
    # 获取总数
    total = query.count()
    
    # 获取分页数据
    spiders = query.offset(skip).limit(limit).all()
    
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
    
    # 查询部署节点信息
    from app.models import Schedule, Node
    schedules = db.query(Schedule).filter(
        Schedule.project_id == spider.project_id,
        Schedule.spider_name == spider.name,
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
        "git_password": spider.git_password,
        "git_ssh_key": spider.git_ssh_key,
        "git_passphrase": spider.git_passphrase,
        "git_branch": spider.git_branch,
        "code_path": spider.code_path,
        "config": spider.config,
        "schedule_config": spider.schedule_config,
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
    
    # 创建爬虫
    new_spider = Spider(
        **spider_data.dict(),
        status="draft"
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
    for key, value in update_data.items():
        setattr(spider, key, value)
    
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
    """运行爬虫"""
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    
    if spider.status == "disabled":
        raise HTTPException(status_code=400, detail="爬虫已禁用，无法运行")
    
    # 检查代码目录
    upload_service = UploadService()
    code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    
    if not code_dir or not os.path.exists(code_dir):
        raise HTTPException(status_code=400, detail="爬虫代码目录不存在，请先上传代码或克隆Git仓库")
    
    # 创建任务实例
    from app.models import TaskInstance, TaskStatus
    task = TaskInstance(
        spider_id=spider.id,
        spider_name=spider.spider_name or spider.name,
        schedule_id=None,
        status=TaskStatus.PENDING,
    )
    
    # 如果有指定节点，设置节点信息
    if body.node_id:
        node = db.query(Node).get(body.node_id)
        if not node:
            raise HTTPException(status_code=404, detail="节点不存在")
        if node.status.value != "online":
            raise HTTPException(status_code=400, detail=f"节点 {node.name} 状态为 {node.status.value}，不可用")
        task.node_id = node.id
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # 根据节点类型选择执行方式
    if body.node_id:
        node = db.query(Node).get(body.node_id)
        if node.connect_type == "ssh":
            return _run_via_ssh(spider, task, node, code_dir, background_tasks)
        elif node.connect_type == "docker":
            return _run_via_remote_docker(spider, task, node, code_dir, background_tasks)
        elif node.connect_type == "agent":
            return _run_via_agent(spider, task, node, db)
        else:
            return _run_via_ssh(spider, task, node, code_dir, background_tasks)
    else:
        # 无节点指定，使用本地执行
        return _run_locally(spider, task, code_dir, db, background_tasks)


def _run_locally(spider, task, code_dir, db, background_tasks):
    """本地模式运行爬虫（v1 默认执行方式，不依赖 Docker / Celery）"""
    from app.services.local_executor import get_local_executor, LocalTaskConfig
    local_executor = get_local_executor()

    config = LocalTaskConfig(
        task_id=str(task.id),
        spider_id=str(spider.id),
        spider_name=spider.spider_name or spider.name,
        code_dir=code_dir,
        entry_file=spider.entry_file,
        spider_name_to_run=spider.spider_name or spider.name,
    )

    # 在后台运行
    background_tasks.add_task(local_executor.execute_task, config)

    # 更新爬虫统计
    spider.run_count = (spider.run_count or 0) + 1
    spider.last_run_at = datetime.utcnow()
    spider.last_run_status = "running"
    db.commit()

    return {
        "message": "爬虫已启动(本地模式)",
        "task_id": task.id,
        "spider_id": spider.id,
        "mode": "local",
        "code_dir": code_dir,
        "entry_file": spider.entry_file
    }


def _run_via_ssh(spider, task, node, code_dir, background_tasks):
    """通过 SSH 在远程服务器上运行爬虫"""
    from app.services.ssh_executor import get_ssh_executor, SshTaskConfig

    ssh_executor = get_ssh_executor()

    config = SshTaskConfig(
        task_id=str(task.id),
        spider_id=str(spider.id),
        spider_name=spider.spider_name or spider.name,
        ssh_host=node.ssh_host or node.host,
        ssh_port=node.ssh_port or 22,
        ssh_user=node.ssh_user or "root",
        ssh_pwd=node.ssh_pwd,
        ssh_key=node.ssh_key,
        code_dir=code_dir,
        entry_file=spider.entry_file,
        spider_name_to_run=spider.spider_name or spider.name,
    )

    # 在后台执行
    background_tasks.add_task(ssh_executor.execute_task, config)

    # 更新爬虫统计
    from app.core.database import SessionLocal
    db_local = SessionLocal()
    try:
        spider_obj = db_local.query(Spider).get(spider.id)
        if spider_obj:
            spider_obj.run_count = (spider_obj.run_count or 0) + 1
            spider_obj.last_run_at = datetime.utcnow()
            spider_obj.last_run_status = "running"
            db_local.commit()
    finally:
        db_local.close()

    return {
        "message": "爬虫运行指令已发送(SSH模式)",
        "task_id": task.id,
        "spider_id": spider.id,
        "mode": "ssh",
        "node_id": node.id,
        "node_name": node.name,
        "host": node.ssh_host or node.host,
        "workspace": f"/opt/crawlopilot/workspace/{task.id}/"
    }


def _run_via_remote_docker(spider, task, node, code_dir, background_tasks):
    """在远程 Docker 节点上运行爬虫（直连节点 Docker API，不依赖 Celery）"""
    from app.services.docker_executor import get_docker_executor, DockerTaskConfig

    docker_executor = get_docker_executor()
    config = DockerTaskConfig(
        task_id=str(task.id),
        spider_id=str(spider.id),
        spider_name=spider.spider_name or spider.name,
        project_id=spider.project_id,
        code_dir=code_dir,
        entry_file=spider.entry_file,
        spider_name_to_run=spider.spider_name or spider.name,
        node_host=node.host,
        node_port=node.port or 2375,
        docker_host=node.docker_host,
    )
    background_tasks.add_task(docker_executor.execute_task, config)

    # 更新爬虫统计
    from app.core.database import SessionLocal
    db_local = SessionLocal()
    try:
        spider_obj = db_local.query(Spider).get(spider.id)
        if spider_obj:
            spider_obj.run_count = (spider_obj.run_count or 0) + 1
            spider_obj.last_run_at = datetime.utcnow()
            spider_obj.last_run_status = "running"
            db_local.commit()
    finally:
        db_local.close()

    return {
        "message": "爬虫运行指令已发送(Docker直连模式)",
        "task_id": task.id,
        "spider_id": spider.id,
        "mode": "docker",
        "node_id": node.id,
        "node_name": node.name,
        "docker_host": f"{node.host}:{node.port or 2375}",
    }


def _run_via_agent(spider, task, node, db):
    """通过 Agent 运行爬虫：任务保持 PENDING，由节点上的 agent 领取执行"""
    from app.models import TaskStatus

    task.deploy_mode = "agent"
    task.node_id = node.id
    task.status = TaskStatus.PENDING
    db.commit()

    # 更新爬虫统计
    spider.run_count = (spider.run_count or 0) + 1
    spider.last_run_at = datetime.utcnow()
    spider.last_run_status = "running"
    db.commit()

    return {
        "message": "任务已派发给节点 Agent",
        "task_id": task.id,
        "spider_id": spider.id,
        "mode": "agent",
        "node_id": node.id,
        "node_name": node.name,
    }


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
            # 尝试本地执行器停止
            from app.services.local_executor import get_local_executor
            local_executor = get_local_executor()
            success = await local_executor.stop_task(str(task.id))
            
            if not success:
                # 尝试 Docker 执行器停止
                try:
                    from app.workers.celery_app import celery_app
                    celery_app.send_task(
                        'app.workers.task_tasks.stop_spider_task',
                        args=[str(task.id)]
                    )
                except Exception:
                    pass
            
            # LocalExecutor.stop_task 已更新数据库状态，这里作为兜底
            if task.status not in [TaskStatus.CANCELLED, TaskStatus.SUCCESS, TaskStatus.FAILED]:
                task.status = TaskStatus.CANCELLED
                task.finished_at = datetime.utcnow()
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
    path: str,
    content: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """保存爬虫文件内容"""
    from app.services.file_service import FileService
    
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

    # 组装克隆 URL / SSH 环境
    clone_url = git_url
    env = dict(os.environ)
    key_path = None
    if spider.git_auth_type == "password" and (spider.git_username or spider.git_password):
        if parsed.scheme in ("http", "https"):
            username = quote(spider.git_username or "x-access-token", safe="")
            password = quote(spider.git_password or "", safe="")
            netloc = f"{username}:{password}@{parsed.netloc}"
            clone_url = urlunparse(
                (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
            )
    elif spider.git_auth_type == "ssh" and spider.git_ssh_key:
        try:
            key_fd, key_path = tempfile.mkstemp(prefix="crawlo_git_key_")
            os.close(key_fd)
            with open(key_path, "w", encoding="utf-8") as f:
                f.write(spider.git_ssh_key)
            os.chmod(key_path, 0o600)
            env["GIT_SSH_COMMAND"] = (
                f"ssh -i {key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
            )
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
        cmds = [
            ["git", "clone", "--depth", "1", "--branch", branch, clone_url, tmp_dir],
            ["git", "clone", "--depth", "1", clone_url, tmp_dir],
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

        # 只保留代码，去掉仓库元数据
        git_meta = os.path.join(spider_code_dir, ".git")
        if os.path.exists(git_meta):
            shutil.rmtree(git_meta, ignore_errors=True)

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
        if key_path:
            try:
                os.unlink(key_path)
            except OSError:
                pass
