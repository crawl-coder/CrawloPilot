"""
执行器抽象契约（Protocol）

四个执行器（Local / SSH / Docker / Agent）实现同一套任务生命周期接口，
新增执行方式时实现本 Protocol 即可被 executor_registry 复用。

契约方法：
- execute_task(config) -> task_id     启动任务
- stop_task(task_id) -> bool           停止任务
- get_task_status(task_id) -> dict     查询状态
- get_task_logs(task_id, tail) -> str  读取日志

可选能力（仅 LocalExecutor 支持，路由层需判断）：
- pause_task / resume_task             暂停 / 恢复
"""

from typing import Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class Executor(Protocol):
    """执行器核心契约"""

    async def execute_task(self, config) -> str:  # noqa: E704
        """启动任务，返回 task_id"""
        ...

    async def stop_task(self, task_id: str) -> bool:  # noqa: E704
        """停止任务"""
        ...

    def get_task_status(self, task_id: str) -> Optional[Dict]:  # noqa: E704
        """查询任务状态"""
        ...

    def get_task_logs(self, task_id: str, tail: int = 100) -> str:  # noqa: E704
        """读取任务日志"""
        ...


@runtime_checkable
class PausableExecutor(Protocol):
    """支持暂停/恢复的执行器（目前仅 LocalExecutor）"""

    async def pause_task(self, task_id: str) -> bool:  # noqa: E704
        """暂停任务"""
        ...

    async def resume_task(self, task_id: str) -> bool:  # noqa: E704
        """恢复任务"""
        ...


def supports_pause(executor) -> bool:
    """判断执行器是否支持暂停/恢复"""
    return isinstance(executor, PausableExecutor)
