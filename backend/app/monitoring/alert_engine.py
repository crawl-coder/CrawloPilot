"""
告警引擎
负责评估告警规则、触发告警和发送通知
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.monitoring.notifiers.base import BaseNotifier
from app.monitoring.notifiers.email import EmailNotifier
from app.monitoring.notifiers.dingtalk import DingTalkNotifier
from app.monitoring.notifiers.wechat import WeChatNotifier
import logging

logger = logging.getLogger(__name__)


class AlertSeverity:
    """告警严重程度"""
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertRule:
    """告警规则"""
    
    def __init__(self, rule_id: int, name: str, metric: str, 
                 operator: str, threshold: float, severity: str,
                 duration: int = 0, enabled: bool = True,
                 notification_channels: List[str] = None):
        self.rule_id = rule_id
        self.name = name
        self.metric = metric
        self.operator = operator  # >, <, >=, <=, ==
        self.threshold = threshold
        self.severity = severity
        self.duration = duration  # 持续时长（秒）
        self.enabled = enabled
        self.notification_channels = notification_channels or []
        self.triggered_at = None
        self.trigger_count = 0
    
    def evaluate(self, current_value: float) -> bool:
        """
        评估是否触发告警
        
        Args:
            current_value: 当前指标值
        
        Returns:
            是否触发告警
        """
        if self.operator == '>':
            return current_value > self.threshold
        elif self.operator == '<':
            return current_value < self.threshold
        elif self.operator == '>=':
            return current_value >= self.threshold
        elif self.operator == '<=':
            return current_value <= self.threshold
        elif self.operator == '==':
            return abs(current_value - self.threshold) < 0.001
        else:
            return False


class AlertEvent:
    """告警事件"""
    
    def __init__(self, rule: AlertRule, value: float, message: str = ""):
        self.rule = rule
        self.value = value
        self.message = message or f"告警触发: {rule.name} (当前值: {value}, 阈值: {rule.threshold})"
        self.triggered_at = datetime.utcnow()
        self.resolved_at = None
        self.notified = False
    
    def resolve(self):
        """解决告警"""
        self.resolved_at = datetime.utcnow()
        logger.info(f"Alert resolved: {self.rule.name}")


class AlertEngine:
    """告警引擎"""
    
    def __init__(self, db: Session):
        self.db = db
        self.rules: Dict[int, AlertRule] = {}
        self.active_alerts: Dict[int, AlertEvent] = {}
        self.notifiers: Dict[str, BaseNotifier] = {}
        self._init_notifiers()
    
    def _init_notifiers(self):
        """初始化通知器"""
        from app.core.config import settings
        
        # 邮件通知器
        if hasattr(settings, 'SMTP_HOST') and settings.SMTP_HOST:
            self.notifiers['email'] = EmailNotifier(
                smtp_host=settings.SMTP_HOST,
                smtp_port=getattr(settings, 'SMTP_PORT', 587),
                username=getattr(settings, 'SMTP_USER', ''),
                password=getattr(settings, 'SMTP_PASSWORD', ''),
                from_email=getattr(settings, 'SMTP_FROM', ''),
                to_emails=getattr(settings, 'ALERT_EMAILS', [])
            )
        
        # 钉钉通知器
        if hasattr(settings, 'DINGTALK_WEBHOOK') and settings.DINGTALK_WEBHOOK:
            self.notifiers['dingtalk'] = DingTalkNotifier(
                webhook=settings.DINGTALK_WEBHOOK,
                secret=getattr(settings, 'DINGTALK_SECRET', '')
            )
        
        # 企业微信通知器
        if hasattr(settings, 'WECHAT_WEBHOOK') and settings.WECHAT_WEBHOOK:
            self.notifiers['wechat'] = WeChatNotifier(
                webhook=settings.WECHAT_WEBHOOK
            )
        
        logger.info(f"Initialized {len(self.notifiers)} notifiers")
    
    def load_rules(self, rules: List[Dict[str, Any]]):
        """
        加载告警规则
        
        Args:
            rules: 规则配置列表
        """
        for rule_config in rules:
            rule = AlertRule(
                rule_id=rule_config['id'],
                name=rule_config['name'],
                metric=rule_config['metric'],
                operator=rule_config['operator'],
                threshold=rule_config['threshold'],
                severity=rule_config.get('severity', AlertSeverity.WARNING),
                duration=rule_config.get('duration', 0),
                enabled=rule_config.get('enabled', True),
                notification_channels=rule_config.get('notification_channels', [])
            )
            self.rules[rule.rule_id] = rule
        
        logger.info(f"Loaded {len(self.rules)} alert rules")
    
    def evaluate_metric(self, metric_name: str, current_value: float):
        """
        评估指标是否触发告警
        
        Args:
            metric_name: 指标名称
            current_value: 当前值
        """
        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue
            
            if rule.metric != metric_name:
                continue
            
            # 评估规则
            if rule.evaluate(current_value):
                self._handle_alert_triggered(rule, current_value)
            else:
                self._handle_alert_resolved(rule)
    
    def _handle_alert_triggered(self, rule: AlertRule, value: float):
        """处理告警触发"""
        # 检查是否已经在活跃告警中
        if rule.rule_id in self.active_alerts:
            alert = self.active_alerts[rule.rule_id]
            alert.rule.trigger_count += 1
            
            # 检查持续时间
            if rule.duration > 0:
                elapsed = (datetime.utcnow() - alert.triggered_at).total_seconds()
                if elapsed < rule.duration:
                    return  # 还未达到持续时间
            
            # 已经触发过，跳过重复通知
            if alert.notified:
                return
        
        # 创建告警事件
        alert = AlertEvent(rule, value)
        self.active_alerts[rule.rule_id] = alert
        
        logger.warning(f"Alert triggered: {rule.name} (value={value}, threshold={rule.threshold})")
        
        # 发送通知
        self._send_notifications(alert)
        
        # 更新指标
        from app.monitoring.metrics import metrics_collector
        metrics_collector.record_alert(rule.name, rule.severity)
    
    def _handle_alert_resolved(self, rule: AlertRule):
        """处理告警解决"""
        if rule.rule_id in self.active_alerts:
            alert = self.active_alerts[rule.rule_id]
            alert.resolve()
            del self.active_alerts[rule.rule_id]
            
            logger.info(f"Alert resolved: {rule.name}")
            
            # 减少活跃告警计数
            from app.monitoring.metrics import active_alerts_count
            active_alerts_count.labels(severity=rule.severity).dec()
    
    def _send_notifications(self, alert: AlertEvent):
        """发送告警通知"""
        if not alert.rule.notification_channels:
            logger.info("No notification channels configured, skipping")
            return
        
        for channel in alert.rule.notification_channels:
            if channel in self.notifiers:
                try:
                    notifier = self.notifiers[channel]
                    notifier.send(alert)
                    alert.notified = True
                    logger.info(f"Notification sent via {channel}")
                except Exception as e:
                    logger.error(f"Failed to send notification via {channel}: {e}")
            else:
                logger.warning(f"Notifier not found: {channel}")
    
    def get_active_alerts(self) -> List[AlertEvent]:
        """获取活跃告警列表"""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """获取告警历史"""
        # TODO: 从数据库查询告警历史
        return []
    
    def get_alert_stats(self) -> Dict[str, int]:
        """获取告警统计"""
        total = len(self.active_alerts)
        by_severity = {
            AlertSeverity.WARNING: 0,
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.EMERGENCY: 0
        }
        
        for alert in self.active_alerts.values():
            if alert.rule.severity in by_severity:
                by_severity[alert.rule.severity] += 1
        
        return {
            "total": total,
            "by_severity": by_severity
        }


# 全局告警引擎实例（延迟初始化）
alert_engine = None


def get_alert_engine(db: Session) -> AlertEngine:
    """获取告警引擎实例"""
    global alert_engine
    if alert_engine is None:
        alert_engine = AlertEngine(db)
    return alert_engine
