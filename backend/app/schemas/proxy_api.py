"""
Phase 6: 代理池和 API 管理 Schemas
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ProxyProtocolEnum(str, Enum):
    HTTP = "HTTP"
    HTTPS = "HTTPS"
    SOCKS5 = "SOCKS5"


class ProxyStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class ProxyCreate(BaseModel):
    ip: str
    port: int
    protocol: ProxyProtocolEnum
    region: Optional[str] = None
    group_name: Optional[str] = None


class ProxyResponse(BaseModel):
    id: int
    ip: str
    port: int
    protocol: ProxyProtocolEnum
    region: Optional[str]
    group_name: Optional[str]
    health_score: float
    status: ProxyStatusEnum
    last_checked_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ProxyCheckResponse(BaseModel):
    total: int
    checked: int
    available: int
    unavailable: int


class ProxyStatsResponse(BaseModel):
    total: int
    active: int
    inactive: int
    blocked: int
    average_score: float


class ApiAuthTypeEnum(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"


class ApiConfigCreate(BaseModel):
    project_id: int
    name: str
    base_url: str
    auth_type: ApiAuthTypeEnum = ApiAuthTypeEnum.NONE
    api_key: Optional[str] = None
    rate_limit: int = 60
    circuit_breaker_threshold: int = 10
    enabled: bool = True


class ApiConfigResponse(BaseModel):
    id: int
    project_id: int
    name: str
    base_url: str
    auth_type: ApiAuthTypeEnum
    rate_limit: int
    circuit_breaker_threshold: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApiStatsResponse(BaseModel):
    total_calls: int
    success_calls: int
    failed_calls: int
    success_rate: float
    average_response_time: float
    circuit_breaker_trips: int
    period_days: int


class ApiTrendResponse(BaseModel):
    date: str
    total_calls: int
    success_calls: int
    avg_response_time: float
