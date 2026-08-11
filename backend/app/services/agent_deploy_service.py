"""
Agent 一键部署服务

通过服务器已有的 SSH 通道，把 crawlo_agent.py 部署到目标服务器，
并以 systemd 托管（开机自启 + 崩溃自动重启），随后等待 agent 注册上线。
批量部署：逐台执行，单台失败不中断其他服务器。
"""
import base64
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from app.core.crypto import decrypt_or_plain
from app.models import Node, NodeStatus
from app.services.ssh_executor import SshConnection

logger = logging.getLogger(__name__)

# 仓库根目录：backend/app/services/agent_deploy_service.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
AGENT_SCRIPT = _REPO_ROOT / "agent" / "crawlo_agent.py"
REMOTE_AGENT_PATH = "/usr/local/bin/crawlo_agent.py"
REMOTE_SERVICE_NAME = "crawlo-agent"


def _get_ssh_node(db, server) -> Node | None:
    """取服务器下的 SSH 通道（优先在线节点）"""
    nodes = db.query(Node).filter(
        Node.server_id == server.id,
        Node.connect_type == "ssh",
    ).all()
    if not nodes:
        return None
    for n in nodes:
        if n.status == NodeStatus.ONLINE:
            return n
    return nodes[0]


def _get_or_create_agent_node(db, server, node_service) -> Node:
    """复用服务器已有的 Agent 节点，否则新建并绑定"""
    node = db.query(Node).filter(
        Node.server_id == server.id,
        Node.connect_type == "agent",
    ).first()
    if node:
        return node

    try:
        name = f"agent-{server.host}"
        node = node_service.create_node(
            name=name,
            host=server.host,
            port=22,
            connect_type="agent",
            ssh_host=server.host,
            ssh_port=22,
            ssh_user="root",
        )
    except ValueError:
        name = f"agent-{server.host}-{uuid.uuid4().hex[:6]}"
        node = node_service.create_node(
            name=name,
            host=server.host,
            port=22,
            connect_type="agent",
            ssh_host=server.host,
            ssh_port=22,
            ssh_user="root",
        )
    node.server_id = server.id
    db.commit()
    db.refresh(node)
    return node


def _build_systemd_unit(server_url: str, token: str, python_path: str, host: str) -> str:
    return f"""[Unit]
Description=CrawloPilot Agent ({host})
After=network-online.target

[Service]
Type=simple
ExecStart={python_path} {REMOTE_AGENT_PATH} --server {server_url} --token {token}
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""


def deploy_agent_to_server(db, server, server_url: str) -> Dict[str, Any]:
    """单台服务器一键部署 Agent"""
    result: Dict[str, Any] = {
        "server_id": server.id,
        "server_name": server.name,
        "host": server.host,
        "success": False,
        "message": "",
        "agent_node_id": None,
    }

    ssh_node = _get_ssh_node(db, server)
    if not ssh_node:
        result["message"] = "该服务器没有 SSH 通道，请先创建并激活 SSH 通道"
        return result

    try:
        from app.services.node_service import NodeService
        node_service = NodeService(db)
        agent_node = _get_or_create_agent_node(db, server, node_service)
        token = agent_node.agent_token
        result["agent_node_id"] = agent_node.id

        conn = SshConnection(
            host=ssh_node.ssh_host or ssh_node.host,
            port=ssh_node.ssh_port or ssh_node.port or 22,
            user=ssh_node.ssh_user or "root",
            password=decrypt_or_plain(ssh_node.ssh_pwd),
            key=decrypt_or_plain(ssh_node.ssh_key),
        )
        try:
            client = conn.connect()

            # 1. 探测 python3 路径
            out, _, _ = conn.exec_command("command -v python3 || echo /usr/bin/python3")
            python_path = (out or "/usr/bin/python3").strip().splitlines()[-1]

            # 2. 上传 agent 脚本
            if not AGENT_SCRIPT.exists():
                result["message"] = f"控制面缺少 agent 脚本: {AGENT_SCRIPT}"
                return result
            sftp = client.open_sftp()
            try:
                sftp.put(str(AGENT_SCRIPT), REMOTE_AGENT_PATH)
                sftp.chmod(REMOTE_AGENT_PATH, 0o755)
            finally:
                sftp.close()

            # 3. 写入 systemd 单元并启动（base64 传输避免转义问题）
            unit = _build_systemd_unit(server_url, token, python_path, server.host)
            unit_b64 = base64.b64encode(unit.encode("utf-8")).decode("ascii")
            cmd = (
                f"echo {unit_b64} | base64 -d > /etc/systemd/system/{REMOTE_SERVICE_NAME}.service && "
                f"systemctl daemon-reload && systemctl enable --now {REMOTE_SERVICE_NAME}"
            )
            _, err, code = conn.exec_command(cmd, timeout=60)
            if code != 0:
                result["message"] = f"systemd 配置失败: {(err or '').strip()[:200]}"
                return result
        finally:
            conn.close()

        # 4. 等待注册上线（agent 启动后注册，首次可能因网络/重试耗时，最长等 90s）
        deadline = time.time() + 90
        online = False
        while time.time() < deadline:
            db.expire_all()
            node = db.query(Node).get(agent_node.id)
            if node and node.status == NodeStatus.ONLINE:
                online = True
                break
            time.sleep(3)

        # 兜底：窗口结束前再确认一次（避免刚好卡在边界）
        if not online:
            db.expire_all()
            node = db.query(Node).get(agent_node.id)
            online = bool(node and node.status == NodeStatus.ONLINE)

        result["success"] = online
        result["message"] = (
            f"Agent 已上线（节点 ID: {agent_node.id}）"
            if online
            else "Agent 已启动但 90 秒内未上线，请登录服务器检查 systemd 日志"
        )
        return result

    except Exception as e:
        logger.exception(f"部署 Agent 到 {server.host} 失败")
        result["message"] = f"部署失败: {str(e)[:200]}"
        return result


def batch_deploy_agents(db, server_ids: List[int], server_url: str) -> List[Dict[str, Any]]:
    """批量部署：逐台执行，单台失败不中断"""
    from app.models import Server

    results: List[Dict[str, Any]] = []
    for server_id in server_ids:
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            results.append({
                "server_id": server_id,
                "server_name": f"#{server_id}",
                "host": "-",
                "success": False,
                "message": "服务器不存在",
                "agent_node_id": None,
            })
            continue
        results.append(deploy_agent_to_server(db, server, server_url))
    return results
