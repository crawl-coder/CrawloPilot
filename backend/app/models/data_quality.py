# Phase 5 数据质量模型
from app.core.database import Base
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Enum, Boolean, ForeignKey, JSON, DECIMAL, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
import enum


class DataQualityStatus(str, enum.Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class DataQualityCheck(Base):
    """数据质量检测记录"""
    __tablename__ = "data_quality_check"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_instance_id = Column(BigInteger, ForeignKey("task_instance.id"), nullable=False)
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False)
    spider_name = Column(String(128), nullable=False, index=True)
    
    # 检测指标
    total_records = Column(BigInteger, default=0)
    expected_min_records = Column(BigInteger)
    expected_max_records = Column(BigInteger)
    records_in_range = Column(Boolean)
    
    null_fields = Column(JSON)
    null_rate_threshold = Column(DECIMAL(5, 2))
    null_rate_passed = Column(Boolean)
    
    duplicate_count = Column(BigInteger, default=0)
    duplicate_rate = Column(DECIMAL(5, 2))
    duplicate_rate_threshold = Column(DECIMAL(5, 2))
    duplicate_passed = Column(Boolean)
    
    format_errors = Column(JSON)
    format_passed = Column(Boolean)
    
    data_freshness = Column(Integer)
    freshness_threshold = Column(Integer)
    freshness_passed = Column(Boolean)
    
    # 检测结果
    overall_status = Column(Enum(DataQualityStatus), default=DataQualityStatus.PASSED)
    score = Column(DECIMAL(5, 2), default=100.00)
    details = Column(JSON)
    
    checked_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    task_instance = relationship("TaskInstance")
    project = relationship("Project")


class DataQualityRule(Base):
    """数据质量检测规则"""
    __tablename__ = "data_quality_rule"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False)
    spider_name = Column(String(128), nullable=False, index=True)
    rule_name = Column(String(128), nullable=False)
    
    # 规则配置
    rule_type = Column(String(32), nullable=False)
    conditions = Column(JSON, nullable=False)
    enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project")


class DataStatistics(Base):
    """数据统计指标"""
    __tablename__ = "data_statistics"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False, index=True)
    spider_name = Column(String(128), nullable=False, index=True)
    task_instance_id = Column(BigInteger, ForeignKey("task_instance.id"))
    
    # 统计数据
    total_records = Column(BigInteger, default=0)
    increment_records = Column(BigInteger, default=0)
    data_size_bytes = Column(BigInteger, default=0)
    avg_response_time = Column(DECIMAL(10, 2))
    success_rate = Column(DECIMAL(5, 2))
    
    # 统计维度
    stat_date = Column(DateTime, nullable=False, index=True)
    stat_type = Column(String(32), nullable=False)
    
    # 数据源信息
    data_source = Column(String(128))
    category = Column(String(64))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project = relationship("Project")
    task_instance = relationship("TaskInstance")
