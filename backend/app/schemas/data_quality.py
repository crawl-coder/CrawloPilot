"""
Phase 5: 数据质量 Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class DataQualityStatusEnum(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class DataQualityCheckCreate(BaseModel):
    task_instance_id: int
    project_id: int
    spider_name: str
    quality_data: Dict[str, Any]


class DataQualityCheckResponse(BaseModel):
    id: int
    task_instance_id: int
    project_id: int
    spider_name: str
    total_records: int
    records_in_range: Optional[bool]
    null_rate_passed: Optional[bool]
    duplicate_rate: Optional[float]
    duplicate_passed: Optional[bool]
    format_passed: Optional[bool]
    freshness_passed: Optional[bool]
    overall_status: DataQualityStatusEnum
    score: float
    checked_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class DataQualityRuleCreate(BaseModel):
    project_id: int
    spider_name: str
    rule_name: str
    rule_type: str
    conditions: Dict[str, Any]
    enabled: bool = True


class DataQualityRuleResponse(BaseModel):
    id: int
    project_id: int
    spider_name: str
    rule_name: str
    rule_type: str
    conditions: Dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DataStatisticsResponse(BaseModel):
    id: int
    project_id: int
    spider_name: str
    total_records: int
    increment_records: int
    data_size_bytes: int
    avg_response_time: Optional[float]
    success_rate: Optional[float]
    stat_date: datetime
    stat_type: str
    data_source: Optional[str]
    category: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class QualityStatsResponse(BaseModel):
    total_checks: int
    passed: int
    warning: int
    failed: int
    pass_rate: float
    average_score: float


class SummaryStatsResponse(BaseModel):
    total_records: int
    average_success_rate: float
    period_days: int
