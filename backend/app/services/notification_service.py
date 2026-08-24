"""
通知通道服务（Wave C）

从 alert_channel 表读取启用的通道，根据 channel_type 构造消息并发送。
支持去重/静默期（cooldown 由 alert_engine 层处理，此层只负责发送）。
"""
import json
import logging
import threading
import urllib.request
from typing import List

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import AlertRecord, AlertRule, AlertChannel, AlertChannelType

logger = logging.getLogger(__name__)


def send_alert_notification(record: AlertRecord, rule: AlertRule):
    """发送告警通知到所有启用的通道（后台线程，fire-and-forget）"""
    db = SessionLocal()
    try:
        channels = db.query(AlertChannel).filter(AlertChannel.enabled == True).all()
        if not channels:
            return
        for ch in channels:
            threading.Thread(
                target=_send_to_channel,
                args=(ch, record, rule),
                daemon=True,
                name=f"notify-{ch.id}-{record.id}",
            ).start()
    finally:
        db.close()


def _send_to_channel(ch: AlertChannel, record: AlertRecord, rule: AlertRule):
    """发送单条通知到指定通道"""
    try:
        if ch.channel_type == AlertChannelType.DINGTALK:
            payload = _format_dingtalk(record, rule)
        elif ch.channel_type == AlertChannelType.WECHAT:
            payload = _format_wechat(record, rule)
        elif ch.channel_type == AlertChannelType.FEISHU:
            payload = _format_feishu(record, rule)
        else:
            payload = _format_custom(record, rule)

        req = urllib.request.Request(
            ch.webhook_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info(f"通知已发送: channel={ch.name} record={record.id} http={resp.status}")
    except Exception as e:
        logger.warning(f"通知发送失败: channel={ch.name} record={record.id} error={e}")


def _format_dingtalk(record: AlertRecord, rule: AlertRule) -> dict:
    severity_emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(
        record.severity.value if record.severity else "warning", "🟡")
    return {
        "msgtype": "markdown",
        "markdown": {
            "title": f"{severity_emoji} CrawloPilot 告警",
            "text": (f"## {severity_emoji} {rule.name}\n\n"
                     f"- **规则**：{rule.name} ({rule.rule_type.value})\n"
                     f"- **目标**：{record.target_name or '-'}\n"
                     f"- **消息**：{record.message}\n"
                     f"- **时间**：{record.created_at}"),
        },
    }


def _format_wechat(record: AlertRecord, rule: AlertRule) -> dict:
    return {
        "msgtype": "markdown",
        "markdown": {
            "content": (f"## CrawloPilot 告警\n"
                        f"> 规则：{rule.name}\n"
                        f"> 目标：{record.target_name or '-'}\n"
                        f"> 消息：{record.message}\n"
                        f"> 时间：{record.created_at}"),
        },
    }


def _format_feishu(record: AlertRecord, rule: AlertRule) -> dict:
    return {
        "msg_type": "text",
        "content": {
            "text": (f"[CrawloPilot 告警] {rule.name}\n"
                     f"目标：{record.target_name or '-'}\n"
                     f"消息：{record.message}\n"
                     f"时间：{record.created_at}"),
        },
    }


def _format_custom(record: AlertRecord, rule: AlertRule) -> dict:
    return {
        "event": "alert",
        "rule_name": rule.name,
        "rule_type": rule.rule_type.value,
        "target_id": record.target_id,
        "target_name": record.target_name,
        "message": record.message,
        "severity": record.severity.value if record.severity else "warning",
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
