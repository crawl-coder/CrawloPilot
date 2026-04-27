"""
实时日志广播器

提供线程安全的日志行发布/订阅机制：
- `broadcast(task_id, line)` — 来自子进程读取线程的同步调用
- `subscribe(task_id)` — 返回 queue.Queue，从异步 WebSocket 处理协程读取
- 用于将 LocalExecutor/SSH 等爬虫进程的实时 stdout 推送到 WebSocket 客户端
"""

import queue
import logging
from typing import Dict, Set, Optional

logger = logging.getLogger(__name__)


class LogBroadcaster:
    """线程安全的日志行广播器"""

    def __init__(self):
        self._subscribers: Dict[str, Set[queue.Queue]] = {}

    def subscribe(self, task_id: str, maxsize: int = 500) -> queue.Queue:
        """订阅某任务的实时日志，返回一个 queue.Queue"""
        if task_id not in self._subscribers:
            self._subscribers[task_id] = set()
        q = queue.Queue(maxsize=maxsize)
        self._subscribers[task_id].add(q)
        return q

    def unsubscribe(self, task_id: str, q: queue.Queue):
        """取消订阅"""
        if task_id in self._subscribers:
            self._subscribers[task_id].discard(q)
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]

    def broadcast(self, task_id: str, line: str):
        """广播一行日志到所有订阅者（线程安全，可从子进程读取线程调用）"""
        if task_id in self._subscribers:
            for q in list(self._subscribers[task_id]):
                try:
                    q.put_nowait(line)
                except queue.Full:
                    # 队列满则丢弃最旧的行
                    try:
                        q.get_nowait()
                        q.put_nowait(line)
                    except queue.Empty:
                        pass
                except Exception:
                    pass


# 全局实例
_broadcaster: Optional[LogBroadcaster] = None


def get_log_broadcaster() -> LogBroadcaster:
    """获取全局日志广播器实例"""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = LogBroadcaster()
    return _broadcaster
