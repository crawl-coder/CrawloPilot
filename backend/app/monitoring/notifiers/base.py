"""
通知器基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseNotifier(ABC):
    """通知器基类"""
    
    @abstractmethod
    def send(self, alert_event) -> bool:
        """
        发送告警通知
        
        Args:
            alert_event: 告警事件对象
        
        Returns:
            是否发送成功
        """
        pass
    
    def format_message(self, alert_event) -> str:
        """
        格式化告警消息
        
        Args:
            alert_event: 告警事件对象
        
        Returns:
            格式化后的消息
        """
        severity_emoji = {
            "warning": "⚠️",
            "critical": "🔴",
            "emergency": "🚨"
        }
        
        emoji = severity_emoji.get(alert_event.rule.severity, "ℹ️")
        
        message = f"""
{emoji} **告警通知**

**规则名称**: {alert_event.rule.name}
**严重程度**: {alert_event.rule.severity}
**当前值**: {alert_event.value}
**阈值**: {alert_event.rule.threshold}
**触发时间**: {alert_event.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}
**触发次数**: {alert_event.rule.trigger_count}

**消息**: {alert_event.message}
        """.strip()
        
        return message
