"""
统一时间工具

项目所有数据库时间统一使用中国时区（Asia/Shanghai, UTC+8）。
禁止再使用 datetime.utcnow()（UTC 时间，会导致与本地时区 8 小时偏差）。
"""

from datetime import datetime
from zoneinfo import ZoneInfo


CN_TZ = ZoneInfo("Asia/Shanghai")


def cn_now() -> datetime:
    """返回当前中国时区时间（naive，落库即北京时间）"""
    return datetime.now(CN_TZ).replace(tzinfo=None)


def cn_now_aware() -> datetime:
    """返回带时区的当前中国时间（用于 APScheduler 等需要 aware datetime 的场景）"""
    return datetime.now(CN_TZ)
