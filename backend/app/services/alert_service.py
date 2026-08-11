"""
失败告警通知（Webhook，异步 fire-and-forget）

配置 ALERT_WEBHOOK_URL 后，任务 failed / timeout 时推送一条 JSON，
兼容钉钉/企业微信/飞书/Slack 等自定义机器人（消息格式见 payload）。
"""
import json
import logging
import threading
import urllib.request

from app.core.config import settings

logger = logging.getLogger(__name__)


def notify_task_failed(
    task_id,
    spider_name: str,
    project_name: str,
    node_name: str,
    status: str,
    error_message: str,
    duration,
    started_at,
    finished_at,
):
    """任务失败/超时告警（有配置才发送，后台线程不阻塞主流程）"""
    url = settings.ALERT_WEBHOOK_URL
    if not url:
        return

    payload = {
        "event": "task_failed",
        "task_id": str(task_id),
        "spider_name": spider_name,
        "project_name": project_name,
        "node_name": node_name,
        "status": status,
        "error_message": (error_message or "")[:500],
        "duration_seconds": float(duration) if duration is not None else None,
        "started_at": started_at.isoformat() if started_at else None,
        "finished_at": finished_at.isoformat() if finished_at else None,
    }

    def _send():
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                logger.info(f"任务告警已发送 task={task_id} http={r.status}")
        except Exception as e:
            logger.warning(f"任务告警发送失败 task={task_id}: {e}")

    threading.Thread(target=_send, daemon=True, name=f"alert-{task_id}").start()
