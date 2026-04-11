"""
企业微信通知器
"""
import requests
from app.monitoring.notifiers.base import BaseNotifier
import logging

logger = logging.getLogger(__name__)


class WeChatNotifier(BaseNotifier):
    """企业微信机器人通知器"""
    
    def __init__(self, webhook: str):
        self.webhook = webhook
    
    def send(self, alert_event) -> bool:
        """发送企业微信通知"""
        try:
            message = self.format_message(alert_event)
            
            # 企业微信 Markdown 消息
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": message
                }
            }
            
            response = requests.post(
                self.webhook,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            result = response.json()
            if result.get('errcode') == 0:
                logger.info("WeChat notification sent")
                return True
            else:
                logger.error(f"WeChat API error: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send WeChat notification: {e}", exc_info=True)
            return False
