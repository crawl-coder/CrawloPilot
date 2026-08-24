"""
告警规则引擎（Wave C）

事件驱动：task_updater / node_service / task_reconciler 在关键状态变更时调用
`evaluate_rules(event_type, payload)`，引擎遍历匹配规则并触发告警。

规则冷却：同一规则在 cooldown_minutes 内不重复触发（按 rule_id + target_id 去重）。
"""
import logging
import threading
from datetime import timedelta
from typing import Optional, Dict, Any

from sqlalchemy import and_, func

from app.core.database import SessionLocal
from app.core.time_utils import cn_now
from app.models import (
    AlertRule, AlertRecord, AlertRuleType, AlertSeverity,
    TaskInstance, TaskStatus, Node, NodeStatus,
)

logger = logging.getLogger(__name__)

# ==================== 事件发布（简单进程内 pub-sub） ====================

_handlers = []


def subscribe(handler):
    """注册事件处理器（引擎初始化时调用）"""
    _handlers.append(handler)


def publish(event_type: str, payload: Dict[str, Any]):
    """发布事件（fire-and-forget，不阻塞调用方）"""
    for h in _handlers:
        try:
            h(event_type, payload)
        except Exception as e:
            logger.warning(f"告警事件处理异常: {e}")


# ==================== 规则评估 ====================

def evaluate_rules(event_type: str, payload: Dict[str, Any]):
    """遍历匹配规则并触发告警（后台线程执行，不阻塞主流程）"""
    db = SessionLocal()
    try:
        rules = (
            db.query(AlertRule)
            .filter(AlertRule.enabled == True, AlertRule.rule_type == event_type)
            .all()
        )
        now = cn_now()
        for rule in rules:
            try:
                # 范围过滤
                if rule.spider_id and payload.get("spider_id") != rule.spider_id:
                    continue
                if rule.project_id and payload.get("project_id") != rule.project_id:
                    continue

                # 冷却期检查
                if _in_cooldown(db, rule.id, payload.get("target_id"), now, rule.cooldown_minutes):
                    continue

                # 规则评估
                triggered, message, severity = _evaluate_single(db, rule, event_type, payload, now)
                if not triggered:
                    continue

                # 写入告警记录
                record = AlertRecord(
                    rule_id=rule.id,
                    event_type=event_type,
                    target_id=payload.get("target_id"),
                    target_name=payload.get("target_name"),
                    message=message,
                    severity=severity or rule.severity,
                )
                db.add(record)
                db.commit()
                logger.warning(f"告警触发: rule={rule.name} type={event_type} target={payload.get('target_name')} msg={message[:100]}")

                # 发送通知（C2 通道通知）
                _send_notifications(record, rule)

            except Exception as e:
                logger.error(f"规则 {rule.id} 评估异常: {e}", exc_info=True)
                db.rollback()
    finally:
        db.close()


def _evaluate_single(db, rule: AlertRule, event_type: str, payload: Dict, now) -> tuple:
    """评估单条规则，返回 (triggered, message, severity)"""
    rt = rule.rule_type

    if rt == AlertRuleType.TASK_FAILED:
        return True, _msg_task_failed(payload), AlertSeverity.WARNING

    elif rt == AlertRuleType.TASK_TIMEOUT:
        return True, _msg_task_timeout(payload), AlertSeverity.WARNING

    elif rt == AlertRuleType.NODE_OFFLINE:
        return True, _msg_node_offline(payload), AlertSeverity.CRITICAL

    elif rt == AlertRuleType.ZOMBIE_CONVERGED:
        return True, _msg_zombie_converged(payload), AlertSeverity.WARNING

    elif rt == AlertRuleType.CONSECUTIVE_FAILURES:
        count = _count_recent_failures(db, rule.spider_id or payload.get("spider_id"),
                                       rule.window_minutes, now)
        if count >= rule.threshold:
            return True, f"连续失败 {count} 次（阈值 {rule.threshold}，窗口 {rule.window_minutes} 分钟）", AlertSeverity.CRITICAL
        return False, "", None

    elif rt == AlertRuleType.SUCCESS_RATE:
        rate = _calc_success_rate(db, rule.spider_id or payload.get("spider_id"),
                                  rule.window_minutes, now)
        if rate is not None and rate < rule.threshold:
            return True, f"近 {rule.window_minutes} 分钟成功率 {rate:.1f}% < 阈值 {rule.threshold}%", AlertSeverity.WARNING
        return False, "", None

    return False, "", None


# ==================== 辅助函数 ====================

def _in_cooldown(db, rule_id, target_id, now, cooldown_minutes) -> bool:
    """检查冷却期内是否已触发过同规则"""
    cutoff = now - timedelta(minutes=cooldown_minutes)
    q = db.query(AlertRecord).filter(
        AlertRecord.rule_id == rule_id,
        AlertRecord.created_at >= cutoff,
    )
    if target_id:
        q = q.filter(AlertRecord.target_id == target_id)
    return db.query(q.exists()).scalar()


def _count_recent_failures(db, spider_id, window_minutes, now) -> int:
    """统计近 N 分钟内某爬虫的连续失败次数（从最近一次成功算起）"""
    if not spider_id:
        return 0
    cutoff = now - timedelta(minutes=window_minutes)
    recent = (
        db.query(TaskInstance.status)
        .filter(TaskInstance.spider_id == spider_id, TaskInstance.created_at >= cutoff)
        .order_by(TaskInstance.id.desc())
        .limit(50)
        .all()
    )
    count = 0
    for (status,) in recent:
        if status in (TaskStatus.FAILED, TaskStatus.TIMEOUT):
            count += 1
        else:
            break  # 遇到非失败状态就停止（连续失败）
    return count


def _calc_success_rate(db, spider_id, window_minutes, now) -> Optional[float]:
    """计算近 N 分钟内某爬虫的成功率"""
    if not spider_id:
        return None
    cutoff = now - timedelta(minutes=window_minutes)
    total = db.query(func.count()).filter(
        TaskInstance.spider_id == spider_id,
        TaskInstance.created_at >= cutoff,
    ).scalar()
    if total == 0:
        return None
    success = db.query(func.count()).filter(
        TaskInstance.spider_id == spider_id,
        TaskInstance.created_at >= cutoff,
        TaskInstance.status == TaskStatus.SUCCESS,
    ).scalar()
    return (success / total) * 100


def _msg_task_failed(payload) -> str:
    return (f"任务失败：{payload.get('target_name', '')} "
            f"(task_id={payload.get('target_id')}) "
            f"{payload.get('error_message', '')[:200]}")


def _msg_task_timeout(payload) -> str:
    return (f"任务超时：{payload.get('target_name', '')} "
            f"(task_id={payload.get('target_id')}) "
            f"duration={payload.get('duration')}s")


def _msg_node_offline(payload) -> str:
    return (f"节点离线：{payload.get('target_name', '')} "
            f"(node_id={payload.get('target_id')})")


def _msg_zombie_converged(payload) -> str:
    return (f"僵尸任务清理：{payload.get('target_name', '')} "
            f"(task_id={payload.get('target_id')}) "
            f"{payload.get('error_message', '')[:200]}")


def _send_notifications(record: AlertRecord, rule: AlertRule):
    """发送通知到所有启用的通道（C2 实现后接入）"""
    try:
        from app.services.notification_service import send_alert_notification
        send_alert_notification(record, rule)
    except ImportError:
        pass  # notification_service 尚未实现时静默跳过
    except Exception as e:
        logger.warning(f"通知发送异常: {e}")


# ==================== 初始化 ====================

def init_alert_engine():
    """启动时调用：注册事件处理器"""
    subscribe(evaluate_rules)
    logger.info("告警引擎已启动")
