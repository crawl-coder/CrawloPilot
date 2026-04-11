"""
邮件通知器
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
from app.monitoring.notifiers.base import BaseNotifier
import logging

logger = logging.getLogger(__name__)


class EmailNotifier(BaseNotifier):
    """邮件通知器"""
    
    def __init__(self, smtp_host: str, smtp_port: int, username: str, 
                 password: str, from_email: str, to_emails: List[str]):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails
    
    def send(self, alert_event) -> bool:
        """发送邮件通知"""
        if not self.to_emails:
            logger.warning("No email recipients configured")
            return False
        
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert_event.rule.severity.upper()}] {alert_event.rule.name}"
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            
            # 邮件内容
            message = self.format_message(alert_event)
            html_content = f"""
            <html>
            <body>
                <h2>{message.split(chr(10))[0]}</h2>
                <pre>{message}</pre>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # 发送邮件
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"Email notification sent to {self.to_emails}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}", exc_info=True)
            return False
