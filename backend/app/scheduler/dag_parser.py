"""
DAG (Directed Acyclic Graph) 依赖解析器
用于解析任务之间的依赖关系，确保按正确顺序执行
"""
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


class DAGNode:
    """DAG 节点"""
    
    def __init__(self, task_id: str, schedule_id: int, dependencies: List[int] = None):
        self.task_id = task_id
        self.schedule_id = schedule_id
        self.dependencies = dependencies or []
        self.status = "pending"  # pending, running, success, failed
        self.result = None


class DAGParser:
    """DAG 解析器"""
    
    def __init__(self):
        self.graph: Dict[int, DAGNode] = {}
        self.adjacency_list: Dict[int, List[int]] = defaultdict(list)
        self.reverse_adjacency: Dict[int, List[int]] = defaultdict(list)
    
    def add_task(self, schedule_id: int, task_id: str, dependencies: List[int] = None):
        """
        添加任务节点
        
        Args:
            schedule_id: 调度配置 ID
            task_id: 任务 ID (Celery task ID)
            dependencies: 依赖的调度 ID 列表
        """
        node = DAGNode(task_id, schedule_id, dependencies)
        self.graph[schedule_id] = node
        
        # 构建邻接表
        if dependencies:
            for dep_id in dependencies:
                self.adjacency_list[dep_id].append(schedule_id)
                self.reverse_adjacency[schedule_id].append(dep_id)
        
        logger.debug(f"Added task node: schedule_id={schedule_id}, task_id={task_id}")
    
    def validate_dag(self) -> bool:
        """
        验证是否是有向无环图 (检测环)
        
        Returns:
            True 如果是 DAG，False 如果存在环
        """
        # 使用 Kahn 算法检测环
        in_degree = defaultdict(int)
        
        # 计算入度
        for node_id in self.graph:
            if node_id not in in_degree:
                in_degree[node_id] = 0
            
            for neighbor in self.adjacency_list[node_id]:
                in_degree[neighbor] += 1
        
        # 初始化队列（入度为 0 的节点）
        queue = deque([node_id for node_id in self.graph if in_degree[node_id] == 0])
        
        visited_count = 0
        
        while queue:
            node_id = queue.popleft()
            visited_count += 1
            
            for neighbor in self.adjacency_list[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 如果访问的节点数等于总节点数，说明是 DAG
        is_dag = visited_count == len(self.graph)
        
        if not is_dag:
            logger.error("Cycle detected in dependency graph!")
        
        return is_dag
    
    def get_execution_order(self) -> Optional[List[int]]:
        """
        获取任务执行顺序（拓扑排序）
        
        Returns:
            执行顺序列表，如果存在环则返回 None
        """
        if not self.validate_dag():
            return None
        
        # Kahn 算法进行拓扑排序
        in_degree = defaultdict(int)
        
        for node_id in self.graph:
            if node_id not in in_degree:
                in_degree[node_id] = 0
            
            for neighbor in self.adjacency_list[node_id]:
                in_degree[neighbor] += 1
        
        queue = deque([node_id for node_id in self.graph if in_degree[node_id] == 0])
        execution_order = []
        
        while queue:
            # 可以选择优先级高的任务先执行
            queue = deque(sorted(queue, key=lambda x: self.graph[x].schedule_id))
            
            node_id = queue.popleft()
            execution_order.append(node_id)
            
            for neighbor in self.adjacency_list[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return execution_order
    
    def get_ready_tasks(self) -> List[int]:
        """
        获取可以立即执行的任务（所有依赖已完成）
        
        Returns:
            可以执行的任务 ID 列表
        """
        ready_tasks = []
        
        for node_id, node in self.graph.items():
            if node.status != "pending":
                continue
            
            # 检查所有依赖是否完成
            dependencies_met = all(
                self.graph[dep_id].status == "success"
                for dep_id in node.dependencies
                if dep_id in self.graph
            )
            
            if dependencies_met:
                ready_tasks.append(node_id)
        
        return ready_tasks
    
    def update_task_status(self, schedule_id: int, status: str, result: Any = None):
        """
        更新任务状态
        
        Args:
            schedule_id: 调度 ID
            status: 新状态
            result: 任务结果
        """
        if schedule_id in self.graph:
            self.graph[schedule_id].status = status
            self.graph[schedule_id].result = result
            logger.debug(f"Updated task status: schedule_id={schedule_id}, status={status}")
    
    def get_dependencies(self, schedule_id: int) -> List[int]:
        """获取任务的依赖列表"""
        if schedule_id in self.graph:
            return self.graph[schedule_id].dependencies
        return []
    
    def get_dependents(self, schedule_id: int) -> List[int]:
        """获取依赖该任务的任务列表"""
        return self.adjacency_list.get(schedule_id, [])
    
    def is_blocked(self, schedule_id: int) -> bool:
        """
        检查任务是否被阻塞（依赖失败）
        
        Returns:
            True 如果被阻塞
        """
        if schedule_id not in self.graph:
            return False
        
        for dep_id in self.graph[schedule_id].dependencies:
            if dep_id in self.graph:
                if self.graph[dep_id].status == "failed":
                    return True
                # 递归检查依赖
                if self.is_blocked(dep_id):
                    return True
        
        return False
    
    def reset(self):
        """重置 DAG"""
        self.graph.clear()
        self.adjacency_list.clear()
        self.reverse_adjacency.clear()
        logger.debug("DAG reset")
    
    def get_dag_info(self) -> Dict[str, Any]:
        """获取 DAG 信息"""
        return {
            "total_tasks": len(self.graph),
            "tasks": {
                str(node_id): {
                    "task_id": node.task_id,
                    "schedule_id": node.schedule_id,
                    "status": node.status,
                    "dependencies": node.dependencies,
                    "dependents": self.adjacency_list.get(node_id, [])
                }
                for node_id, node in self.graph.items()
            },
            "is_valid_dag": self.validate_dag()
        }


def parse_schedule_dependencies(schedules: List[Dict]) -> DAGParser:
    """
    解析调度配置的依赖关系
    
    Args:
        schedules: 调度配置列表，每个包含 id 和 dependencies
    
    Returns:
        DAGParser 实例
    """
    parser = DAGParser()
    
    for schedule in schedules:
        parser.add_task(
            schedule_id=schedule['id'],
            task_id=schedule.get('task_id', ''),
            dependencies=schedule.get('dependencies', [])
        )
    
    return parser
