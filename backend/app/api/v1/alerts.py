"""
告警管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from typing import Any

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.monitoring.alert_engine import get_alert_engine, AlertSeverity
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["告警管理"])


# Pydantic Schemas
class AlertRuleCreate(BaseModel):
    name: str
    metric: str
    operator: str  # >, <, >=, <=, ==
    threshold: float
    severity: str = "warning"
    duration: int = 0
    enabled: bool = True
    notification_channels: List[str] = []

class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    metric: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[float] = None
    severity: Optional[str] = None
    duration: Optional[int] = None
    enabled: Optional[bool] = None
    notification_channels: Optional[List[str]] = None

class AlertRuleResponse(BaseModel):
    id: int
    name: str
    metric: str
    operator: str
    threshold: float
    severity: str
    duration: int
    enabled: bool
    notification_channels: List[str]
    created_at: Any
    updated_at: Optional[Any]
    
    class Config:
        from_attributes = True


@router.get("/rules")
async def list_alert_rules(
    enabled: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取告警规则列表"""
    # TODO: 从数据库查询实际规则
    # 目前返回示例数据
    return [
        {
            "id": 1,
            "name": "CPU 使用率过高",
            "metric": "node_cpu_usage_percent",
            "operator": ">",
            "threshold": 80.0,
            "severity": "warning",
            "duration": 300,
            "enabled": True,
            "notification_channels": ["email", "dingtalk"]
        },
        {
            "id": 2,
            "name": "爬虫成功率过低",
            "metric": "spider_success_rate",
            "operator": "<",
            "threshold": 90.0,
            "severity": "critical",
            "duration": 600,
            "enabled": True,
            "notification_channels": ["email", "dingtalk", "wechat"]
        }
    ]


@router.post("/rules")
async def create_alert_rule(
    rule_data: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建告警规则"""
    # TODO: 保存到数据库
    # 目前返回模拟数据
    return {
        "id": 999,
        **rule_data.dict(),
        "created_at": "2026-04-11T10:00:00",
        "updated_at": None
    }


@router.put("/rules/{rule_id}")
async def update_alert_rule(
    rule_id: int,
    rule_data: AlertRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新告警规则"""
    # TODO: 更新数据库
    return {
        "id": rule_id,
        **rule_data.dict(exclude_unset=True)
    }


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除告警规则"""
    # TODO: 从数据库删除
    return {"message": "告警规则已删除"}


@router.get("/active")
async def get_active_alerts(
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取活跃告警"""
    alert_engine = get_alert_engine(db)
    alerts = alert_engine.get_active_alerts()
    
    # 按严重程度过滤
    if severity:
        alerts = [a for a in alerts if a.rule.severity == severity]
    
    return [
        {
            "rule_id": alert.rule.rule_id,
            "rule_name": alert.rule.name,
            "severity": alert.rule.severity,
            "value": alert.value,
            "threshold": alert.rule.threshold,
            "triggered_at": alert.triggered_at.isoformat(),
            "trigger_count": alert.rule.trigger_count,
            "message": alert.message
        }
        for alert in alerts
    ]


@router.get("/history")
async def get_alert_history(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取告警历史"""
    # TODO: 从数据库查询历史记录
    return []


@router.get("/stats")
async def get_alert_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取告警统计"""
    alert_engine = get_alert_engine(db)
    stats = alert_engine.get_alert_stats()
    
    return stats


@router.post("/test-notification")
async def test_notification(
    channel: str = "email",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """测试通知渠道"""
    alert_engine = get_alert_engine(db)
    
    if channel not in alert_engine.notifiers:
        raise HTTPException(status_code=400, detail=f"通知渠道不存在: {channel}")
    
    # 创建测试告警
    from app.monitoring.alert_engine import AlertRule, AlertEvent
    
    test_rule = AlertRule(
        rule_id=0,
        name="测试告警",
        metric="test",
        operator=">",
        threshold=0,
        severity="warning",
        notification_channels=[channel]
    )
    
    test_alert = AlertEvent(test_rule, 100, "这是一条测试告警")
    
    # 发送测试通知
    try:
        notifier = alert_engine.notifiers[channel]
        success = notifier.send(test_alert)
        
        if success:
            return {"message": f"测试通知已发送到 {channel}"}
        else:
            raise HTTPException(status_code=500, detail="通知发送失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"通知发送失败: {str(e)}")


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动解决告警"""
    # TODO: 实现告警解决逻辑
    return {"message": "告警已解决"}
