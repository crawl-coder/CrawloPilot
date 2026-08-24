"""
告警 API（Wave C）

- 告警规则 CRUD（启用/禁用/编辑）
- 告警记录列表 + 确认（acknowledge）
- 通知通道管理
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.core.time_utils import cn_now
from app.models import (
    User, AlertRule, AlertRecord, AlertChannel,
    AlertRuleType, AlertSeverity, AlertChannelType,
)

router = APIRouter(prefix="/alerts", tags=["告警"])


# ==================== Schemas ====================

class AlertRuleCreate(BaseModel):
    name: str
    rule_type: str
    spider_id: Optional[int] = None
    project_id: Optional[int] = None
    threshold: int = 1
    window_minutes: int = 60
    cooldown_minutes: int = 30
    severity: str = "warning"
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    threshold: Optional[int] = None
    window_minutes: Optional[int] = None
    cooldown_minutes: Optional[int] = None
    severity: Optional[str] = None
    enabled: Optional[bool] = None


class AlertChannelCreate(BaseModel):
    name: str
    channel_type: str
    webhook_url: str
    enabled: bool = True


class AlertChannelUpdate(BaseModel):
    name: Optional[str] = None
    webhook_url: Optional[str] = None
    enabled: Optional[bool] = None


# ==================== Rules ====================

@router.get("/rules", response_model=List[dict])
async def list_rules(
    enabled: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(AlertRule)
    if enabled is not None:
        q = q.filter(AlertRule.enabled == enabled)
    return [_serialize_rule(r) for r in q.order_by(AlertRule.created_at.desc()).all()]


@router.post("/rules", status_code=201)
async def create_rule(
    data: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        rule_type = AlertRuleType(data.rule_type)
    except ValueError:
        raise HTTPException(400, f"不支持的规则类型: {data.rule_type}，可选: {[t.value for t in AlertRuleType]}")
    try:
        severity = AlertSeverity(data.severity)
    except ValueError:
        raise HTTPException(400, f"不支持的严重级别: {data.severity}")

    rule = AlertRule(
        name=data.name, rule_type=rule_type,
        spider_id=data.spider_id, project_id=data.project_id,
        threshold=data.threshold, window_minutes=data.window_minutes,
        cooldown_minutes=data.cooldown_minutes, severity=severity,
        enabled=data.enabled, created_by=current_user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _serialize_rule(rule)


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: int,
    data: AlertRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    rule = db.query(AlertRule).get(rule_id)
    if not rule:
        raise HTTPException(404, "规则不存在")
    for k, v in data.dict(exclude_unset=True).items():
        if k == "severity":
            setattr(rule, k, AlertSeverity(v))
        else:
            setattr(rule, k, v)
    db.commit()
    return _serialize_rule(rule)


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    rule = db.query(AlertRule).get(rule_id)
    if not rule:
        raise HTTPException(404, "规则不存在")
    db.delete(rule)
    db.commit()
    return {"message": "规则已删除"}


# ==================== Records ====================

@router.get("/records")
async def list_records(
    rule_id: Optional[int] = None,
    severity: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.core.pagination import clamp_pagination
    skip, limit = clamp_pagination(skip, limit, default_limit=50)
    q = db.query(AlertRecord)
    if rule_id:
        q = q.filter(AlertRecord.rule_id == rule_id)
    if severity:
        q = q.filter(AlertRecord.severity == severity)
    if acknowledged is not None:
        q = q.filter(AlertRecord.acknowledged == acknowledged)
    return [_serialize_record(r) for r in q.order_by(AlertRecord.created_at.desc()).offset(skip).limit(limit).all()]


@router.post("/records/{record_id}/acknowledge")
async def acknowledge_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.query(AlertRecord).get(record_id)
    if not record:
        raise HTTPException(404, "告警记录不存在")
    record.acknowledged = True
    record.acknowledged_by = current_user.id
    record.acknowledged_at = cn_now()
    db.commit()
    return _serialize_record(record)


# ==================== Channels ====================

@router.get("/channels")
async def list_channels(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return [_serialize_channel(ch) for ch in db.query(AlertChannel).order_by(AlertChannel.created_at.desc()).all()]


@router.post("/channels", status_code=201)
async def create_channel(
    data: AlertChannelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        ch_type = AlertChannelType(data.channel_type)
    except ValueError:
        raise HTTPException(400, f"不支持的通道类型: {data.channel_type}，可选: {[t.value for t in AlertChannelType]}")
    ch = AlertChannel(name=data.name, channel_type=ch_type, webhook_url=data.webhook_url, enabled=data.enabled)
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return _serialize_channel(ch)


@router.put("/channels/{channel_id}")
async def update_channel(
    channel_id: int,
    data: AlertChannelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    ch = db.query(AlertChannel).get(channel_id)
    if not ch:
        raise HTTPException(404, "通道不存在")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(ch, k, v)
    db.commit()
    return _serialize_channel(ch)


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    ch = db.query(AlertChannel).get(channel_id)
    if not ch:
        raise HTTPException(404, "通道不存在")
    db.delete(ch)
    db.commit()
    return {"message": "通道已删除"}


# ==================== 序列化 ====================

def _serialize_rule(rule: AlertRule) -> dict:
    return {
        "id": rule.id, "name": rule.name,
        "rule_type": rule.rule_type.value if rule.rule_type else None,
        "spider_id": rule.spider_id, "project_id": rule.project_id,
        "threshold": rule.threshold, "window_minutes": rule.window_minutes,
        "cooldown_minutes": rule.cooldown_minutes,
        "severity": rule.severity.value if rule.severity else "warning",
        "enabled": rule.enabled,
        "created_by": rule.created_by,
        "created_at": rule.created_at, "updated_at": rule.updated_at,
    }


def _serialize_record(rec: AlertRecord) -> dict:
    return {
        "id": rec.id, "rule_id": rec.rule_id,
        "event_type": rec.event_type,
        "target_id": rec.target_id, "target_name": rec.target_name,
        "message": rec.message,
        "severity": rec.severity.value if rec.severity else "warning",
        "acknowledged": rec.acknowledged,
        "acknowledged_by": rec.acknowledged_by,
        "acknowledged_at": rec.acknowledged_at,
        "created_at": rec.created_at,
    }


def _serialize_channel(ch: AlertChannel) -> dict:
    return {
        "id": ch.id, "name": ch.name,
        "channel_type": ch.channel_type.value if ch.channel_type else None,
        "webhook_url": ch.webhook_url,
        "enabled": ch.enabled,
        "created_at": ch.created_at,
    }
