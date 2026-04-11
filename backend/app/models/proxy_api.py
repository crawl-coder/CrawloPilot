"""
Phase 6: 代理池和 API 管理扩展模型
"""
from app.core.database import Base
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Enum, Boolean, ForeignKey, JSON, DECIMAL, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
import enum


class ProxyCheckLog(Base):
    """代理健康检查日志"""
    __tablename__ = "proxy_check_log"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    proxy_id = Column(BigInteger, ForeignKey("proxy_pool.id"), nullable=False)
    
    # 检查结果
    is_available = Column(Boolean, nullable=False)
    response_time = Column(Integer)  # 响应时间（毫秒）
    status_code = Column(Integer)  # HTTP 状态码
    error_message = Column(Text)  # 错误信息
    
    # 检查时的指标
    health_score_before = Column(DECIMAL(5, 2))  # 检查前评分
    health_score_after = Column(DECIMAL(5, 2))  # 检查后评分
    
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    proxy = relationship("ProxyPool")


class ProxyUsageLog(Base):
    """代理使用日志"""
    __tablename__ = "proxy_usage_log"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    proxy_id = Column(BigInteger, ForeignKey("proxy_pool.id"), nullable=False)
    project_id = Column(BigInteger, ForeignKey("project.id"))
    task_instance_id = Column(BigInteger, ForeignKey("task_instance.id"))
    
    # 使用统计
    request_count = Column(Integer, default=0)  # 请求次数
    success_count = Column(Integer, default=0)  # 成功次数
    failed_count = Column(Integer, default=0)  # 失败次数
    total_response_time = Column(Integer, default=0)  # 总响应时间（毫秒）
    
    # 使用时间窗口
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    proxy = relationship("ProxyPool")
    project = relationship("Project")
    task_instance = relationship("TaskInstance")


class ApiCallLog(Base):
    """API 调用日志"""
    __tablename__ = "api_call_log"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_config_id = Column(BigInteger, ForeignKey("api_config.id"), nullable=False)
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False)
    task_instance_id = Column(BigInteger, ForeignKey("task_instance.id"))
    
    # 调用信息
    endpoint = Column(String(256))  # API 端点
    method = Column(String(16), default="GET")  # HTTP 方法
    status_code = Column(Integer)  # HTTP 状态码
    response_time = Column(Integer)  # 响应时间（毫秒）
    request_size = Column(BigInteger)  # 请求大小（字节）
    response_size = Column(BigInteger)  # 响应大小（字节）
    
    # 调用结果
    is_success = Column(Boolean)
    error_message = Column(Text)
    
    # 熔断器状态
    circuit_breaker_open = Column(Boolean, default=False)  # 熔断器是否打开
    consecutive_failures = Column(Integer, default=0)  # 连续失败次数
    
    called_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    api_config = relationship("ApiConfig")
    project = relationship("Project")
    task_instance = relationship("TaskInstance")


class ApiRateLimit(Base):
    """API 限流记录"""
    __tablename__ = "api_rate_limit"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_config_id = Column(BigInteger, ForeignKey("api_config.id"), nullable=False)
    
    # 限流窗口
    window_start = Column(DateTime, nullable=False, index=True)
    window_end = Column(DateTime, nullable=False)
    
    # 计数
    request_count = Column(Integer, default=0)
    limit_count = Column(Integer, nullable=False)  # 限制次数
    is_limited = Column(Boolean, default=False)  # 是否被限流
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    api_config = relationship("ApiConfig")
