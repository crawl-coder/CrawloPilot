"""
钉钉通知器
"""
import requests
import hashlib
import base64
import hmac
import time
import urllib.parse
from app.monitoring.notifiers.base import BaseNotifier
import logging

logger = logging.getLogger(__name__)


class DingTalkNotifier(BaseNotifier):
    """钉钉机器人通知器"""
    
    def __init__(self, webhook: str, secret: str = ""):
        self.webhook = webhook
        self.secret = secret
    
    def _generate_sign(self) -> str:
        """生成钉钉签名"""
        if not self.secret:
            return ""
        
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f'{timestamp}\n{self.secret}'
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f"&timestamp={timestamp}&sign={sign}"
    
    def send(self, alert_event) -> bool:
        """发送钉钉通知"""
        try:
            url = self.webhook
            if self.secret:
                url += self._generate_sign()
            
            message = self.format_message(alert_event)
            
            # 钉钉 Markdown 消息
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"告警: {alert_event.rule.name}",
                    "text": message.replace('**', '**').replace('\n', '\n\n')
                }
            }
            
            response = requests.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            result = response.json()
            if result.get('errcode') == 0:
                logger.info("DingTalk notification sent")
                return True
            else:
                logger.error(f"DingTalk API error: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send DingTalk notification: {e}", exc_info=True)
            return False
