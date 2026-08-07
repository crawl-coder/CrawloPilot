"""
Prometheus 监控指标定义
"""
from prometheus_client import Counter, Histogram, Gauge, Enum


# ==================== HTTP 指标（由 middleware/metrics.py 采集）====================
# 此处不再重复定义 http_requests_total / http_request_duration_seconds
# 它们已在 middleware/metrics.py 中定义，避免 Prometheus 注册冲突


# ==================== 爬虫指标 ====================

# 爬虫执行总数
spider_runs_total = Counter(
    'spider_runs_total',
    'Total spider runs',
    ['spider_name', 'status']  # status: success, failed, timeout
)

# 爬虫抓取项目数
spider_items_scraped = Counter(
    'spider_items_scraped_total',
    'Total items scraped by spiders',
    ['spider_name']
)

# 爬虫运行时长
spider_duration_seconds = Histogram(
    'spider_duration_seconds',
    'Spider run duration in seconds',
    ['spider_name'],
    buckets=[60, 300, 600, 1800, 3600, 7200]
)

# 当前运行的爬虫数
spider_running_count = Gauge(
    'spider_running_count',
    'Number of currently running spiders'
)


# ==================== 调度指标 ====================

# 调度任务执行总数
schedule_executions_total = Counter(
    'schedule_executions_total',
    'Total schedule executions',
    ['schedule_id', 'spider_name', 'status']
)

# 活跃的调度数
active_schedules_count = Gauge(
    'active_schedules_count',
    'Number of active schedules'
)

# 下次执行时间
schedule_next_run_timestamp = Gauge(
    'schedule_next_run_timestamp',
    'Next schedule run timestamp',
    ['schedule_id', 'spider_name']
)


# ==================== 部署指标 ====================

# 部署总数
deployments_total = Counter(
    'deployments_total',
    'Total deployments',
    ['project_id', 'strategy', 'status']
)

# 当前运行的容器数
running_containers_count = Gauge(
    'running_containers_count',
    'Number of running containers',
    ['node_id']
)


# ==================== 节点指标 ====================

# 节点状态
node_status = Enum(
    'node_status',
    'Node status',
    ['node_id', 'node_name'],
    states=['online', 'offline', 'draining', 'error']
)

# 节点 CPU 使用率
node_cpu_usage_percent = Gauge(
    'node_cpu_usage_percent',
    'Node CPU usage percentage',
    ['node_id', 'node_name']
)

# 节点内存使用率
node_memory_usage_percent = Gauge(
    'node_memory_usage_percent',
    'Node memory usage percentage',
    ['node_id', 'node_name']
)

# 节点磁盘使用率
node_disk_usage_percent = Gauge(
    'node_disk_usage_percent',
    'Node disk usage percentage',
    ['node_id', 'node_name']
)


# ==================== 告警指标 ====================

# 告警触发总数
alerts_triggered_total = Counter(
    'alerts_triggered_total',
    'Total alerts triggered',
    ['alert_type', 'severity']
)

# 当前活跃告警数
active_alerts_count = Gauge(
    'active_alerts_count',
    'Number of active alerts',
    ['severity']
)


# ==================== 系统指标 ====================

# 数据库连接数
db_connections_active = Gauge(
    'db_connections_active',
    'Number of active database connections'
)


class MetricsCollector:
    """指标收集器（HTTP 指标由 middleware/metrics.py 自动采集）"""
    
    @staticmethod
    def record_spider_run(spider_name: str, status: str, items: int = 0, duration: float = 0):
        """记录爬虫运行指标"""
        spider_runs_total.labels(
            spider_name=spider_name,
            status=status
        ).inc()
        
        if items > 0:
            spider_items_scraped.labels(spider_name=spider_name).inc(items)
        
        if duration > 0:
            spider_duration_seconds.labels(spider_name=spider_name).observe(duration)
    
    @staticmethod
    def record_schedule_execution(schedule_id: str, spider_name: str, status: str):
        """记录调度执行指标"""
        schedule_executions_total.labels(
            schedule_id=schedule_id,
            spider_name=spider_name,
            status=status
        ).inc()
    
    @staticmethod
    def record_deployment(project_id: str, strategy: str, status: str):
        """记录部署指标"""
        deployments_total.labels(
            project_id=project_id,
            strategy=strategy,
            status=status
        ).inc()
    
    @staticmethod
    def update_node_metrics(node_id: str, node_name: str, cpu: float, memory: float, disk: float):
        """更新节点指标"""
        node_cpu_usage_percent.labels(node_id=node_id, node_name=node_name).set(cpu)
        node_memory_usage_percent.labels(node_id=node_id, node_name=node_name).set(memory)
        node_disk_usage_percent.labels(node_id=node_id, node_name=node_name).set(disk)
    
    @staticmethod
    def record_alert(alert_type: str, severity: str):
        """记录告警指标"""
        alerts_triggered_total.labels(
            alert_type=alert_type,
            severity=severity
        ).inc()
        
        active_alerts_count.labels(severity=severity).inc()


# 全局指标收集器实例
metrics_collector = MetricsCollector()
