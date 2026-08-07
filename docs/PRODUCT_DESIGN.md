# Crawlo 管理平台（CrawloPilot）- 产品设计与技术方案

> **阅读提示**：本文是项目初期的完整愿景设计稿（历史文档）。当前实际交付范围以
> [REMAINING_WORK.md](REMAINING_WORK.md) 为准；文中部分接口约定（统一响应格式、
> WebSocket 路径、组件选型、部署架构）与最终实现存在差异，具体行为以代码与
> 各模块文档（docs/modules/）为准。

## 一、产品概述

### 1.1 产品定位
CrawloPilot 是 Crawlo 爬虫框架的配套管理部署平台，提供爬虫项目全生命周期管理能力，包括项目部署、任务调度、运行监控、用户权限四大核心模块。

### 1.2 目标用户
- 爬虫开发工程师
- 运维工程师
- 技术管理者

### 1.3 核心价值
- 统一管理 50+ 爬虫项目的部署与运行
- 可视化监控爬虫运行状态
- 标准化调度策略，降低运维成本
- 权限隔离，保障数据安全

---

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────┐
│                  Web UI (Vue3)                    │
├─────────────────────────────────────────────────┤
│               API Gateway (Nginx)                │
├──────────┬──────────┬──────────┬────────────────┤
│ 项目管理  │ 任务调度  │ 运行监控  │   用户权限    │
│  Service │  Service │  Service │   Service      │
├──────────┴──────────┴──────────┴────────────────┤
│  MySQL (元数据)   │   uploads/ (项目代码/任务日志)  │
├──────────────────┴───────────────────────────────┤
│           Docker Engine / API                     │
├─────────────────────────────────────────────────┤
│   Worker Node 1  │  Worker Node 2  │  Node N    │
│  ┌────────────┐  │  ┌────────────┐  │            │
│  │ Container  │  │  │ Container  │  │            │
│  │ (Spider)   │  │  │ (Spider)   │  │            │
│  └────────────┘  │  └────────────┘  │            │
└─────────────────────────────────────────────────┘
```

### 2.2 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue3 + Element Plus + Pinia | 响应式管理后台 |
| API 网关 | Nginx | 反向代理、负载均衡 |
| 后端 | FastAPI + Uvicorn | 高性能异步 API |
| 任务调度 | APScheduler（进程内） | 定时任务（cron / interval / once） |
| 容器编排 | Docker Engine API | 容器生命周期管理 |
| 实时推送 | WebSocket | 任务状态与日志实时推送 |
| 元数据库 | MySQL 8.0 | 项目/任务/用户元数据 |
| 对象存储 | MinIO / 阿里云 OSS（可选） | 项目包、日志文件 |
| 监控 | Prometheus + Grafana | 指标采集与可视化 |
| 日志 | ELK (Elasticsearch + Logstash + Kibana) | 日志聚合检索 |

---

## 三、功能模块设计

### 3.1 项目部署管理

#### 3.1.1 项目管理

| 功能 | 说明 |
|------|------|
| 项目注册 | 上传项目包（zip/tar.gz）或关联 Git 仓库 |
| 版本管理 | 多版本共存，支持回滚 |
| 配置管理 | 可视化编辑 settings.py，环境变量覆盖 |
| 一键部署 | 选择版本 + 节点 + 配置，一键部署容器 |
| 灰度发布 | 按比例/按节点逐步切换新版本 |
| 项目克隆 | 基于已有项目快速创建新项目 |

#### 3.1.2 项目包结构规范

```
project_name/
├── crawlo.cfg              # 项目配置入口
├── settings.py             # 爬虫配置
├── spiders/                # 爬虫模块
│   ├── __init__.py
│   └── example_spider.py
├── pipelines/              # 自定义管道
├── middlewares/            # 自定义中间件
├── items/                  # 数据模型
├── requirements.txt        # 依赖
└── Dockerfile              # 容器构建（可选）
```

#### 3.1.3 部署流程

```
上传项目包 → 解析项目结构 → 校验配置 → 构建 Docker 镜像
→ 推送镜像仓库 → 分配节点 → 创建容器 → 健康检查 → 部署完成
```

#### 3.1.4 部署策略

| 策略 | 说明 |
|------|------|
| 全量部署 | 所有节点同时更新 |
| 滚动部署 | 逐个节点更新，零停机 |
| 灰度部署 | 先部署到部分节点，验证后全量 |
| 蓝绿部署 | 两套环境切换 |

### 3.2 任务调度管理

#### 3.2.1 调度类型

| 类型 | 说明 | 示例 |
|------|------|------|
| Cron 定时 | Cron 表达式调度 | `0 8 * * *` 每天8点 |
| 间隔调度 | 固定间隔执行 | 每30分钟一次 |
| 一次性任务 | 手动触发，执行一次 | 立即运行 |
| 依赖调度 | 上游任务完成后触发 | 数据采集完成后触发清洗 |
| 事件驱动 | 外部事件触发 | Kafka 消息到达后触发 |

#### 3.2.2 调度策略

| 策略 | 说明 |
|------|------|
| 并发控制 | 同一项目最大并发实例数 |
| 优先级队列 | 高/中/低优先级，抢占式调度 |
| 超时控制 | 单次执行最大时长，超时自动终止 |
| 重试策略 | 失败后自动重试，指数退避 |
| 依赖管理 | DAG 依赖图，上游失败下游不执行 |
| 资源限制 | CPU/内存配额，防止资源争抢 |

#### 3.2.3 DAG 依赖调度

```
[股票列表采集] → [财务数据采集] → [数据清洗] → [数据入库]
                        ↓
                  [公告文件下载] → [文件解析]
```

### 3.3 运行监控告警

#### 3.3.1 实时监控

| 指标 | 说明 |
|------|------|
| 运行状态 | 运行中/已停止/异常/等待中 |
| 下载速率 | 请求/秒 |
| 成功率 | 成功请求/总请求 |
| 队列深度 | 待处理请求数 |
| 资源占用 | CPU/内存/网络 IO |
| 数据吞吐 | 条/秒 |

#### 3.3.2 日志管理

| 功能 | 说明 |
|------|------|
| 实时日志 | WebSocket 推送容器日志流 |
| 日志检索 | ELK 全文检索，支持关键词/时间/级别过滤 |
| 日志下载 | 按任务实例下载日志文件 |
| 日志归档 | 超期日志自动归档/清理 |

#### 3.3.3 告警规则

| 规则类型 | 示例 |
|----------|------|
| 状态告警 | 爬虫异常退出 |
| 阈值告警 | 成功率 < 80% |
| 超时告警 | 执行时间超过阈值 |
| 资源告警 | 内存使用 > 90% |
| 数据告警 | 数据量同比/环比异常 |

#### 3.3.4 告警通道

| 通道 | 说明 |
|------|------|
| 钉钉/飞书 | Webhook 推送（框架已内置） |
| 邮件 | SMTP 发送 |
| 短信 | 阿里云 SMS |
| Webhook | 自定义 HTTP 回调 |

### ~~3.4 数据质量管理~~（2026-08-07 取消）

> 经评估对爬虫部署管理平台价值不大，不做。数据质量检测与统计报表相关规划取消，
> `data_quality_rule` 等表继续保留，将来若有需求可低成本恢复。

#### ~~3.4.1 数据质量检测~~

| 检测项 | 说明 |
|--------|------|
| 数据量检测 | 采集条数是否在预期范围 |
| 空值率检测 | 关键字段空值比例 |
| 重复率检测 | 数据去重率 |
| 格式校验 | 字段格式合规性 |
| 时效性检测 | 数据更新时间是否延迟 |

#### ~~3.4.2 数据统计~~

| 统计维度 | 说明 |
|----------|------|
| 项目维度 | 每个项目的数据总量/增量 |
| 爬虫维度 | 每个爬虫的采集效率 |
| 时间维度 | 小时/天/周/月趋势 |
| 数据源维度 | 各数据源的数据量对比 |

### 3.5 用户与权限管理

#### 3.5.1 用户管理

| 功能 | 说明 |
|------|------|
| 用户注册/登录 | 账号密码 + LDAP/SSO |
| 角色管理 | 预设角色 + 自定义角色 |
| 团队管理 | 按团队划分项目权限 |

#### 3.5.2 RBAC 权限模型

| 角色 | 权限范围 |
|------|----------|
| 超级管理员 | 全部权限 |
| 项目管理员 | 管理本团队项目 |
| 开发工程师 | 部署/调试/查看日志 |
| 运维工程师 | 调度/监控/告警配置 |
| ~~数据分析师~~ | ~~查看数据统计/质量报告~~（数据质量模块已取消） |
| 只读用户 | 查看状态/日志 |

#### 3.5.3 资源隔离

| 维度 | 说明 |
|------|------|
| 项目隔离 | 项目间配置/数据/日志隔离 |
| 团队隔离 | 团队间项目不可见 |
| 节点隔离 | 不同团队使用不同 Worker 节点池 |

### 3.6 代理池管理

#### 3.6.1 代理管理

| 功能 | 说明 |
|------|------|
| 代理录入 | 批量导入/单条添加代理 IP |
| 健康检查 | 定时检测代理可用性 |
| 自动切换 | 代理失效自动切换 |
| 代理评分 | 根据响应时间/成功率评分 |
| 代理分组 | 按地域/类型分组管理 |

#### 3.6.2 代理策略

| 策略 | 说明 |
|------|------|
| 轮询 | 按顺序使用代理 |
| 随机 | 随机选择可用代理 |
| 权重 | 根据评分权重选择 |
| 粘性 | 同一会话使用同一代理 |

### 3.7 API 接口管理

#### 3.7.1 API 管理

| 功能 | 说明 |
|------|------|
| API 注册 | 注册爬虫依赖的外部 API |
| 限流控制 | 按 API 设置请求频率限制 |
| 熔断机制 | 异常时自动熔断保护 |
| 调用统计 | API 调用次数/成功率/延迟 |
| 密钥管理 | API Key 加密存储与轮换 |

### 3.8 数据导出管理

| 功能 | 说明 |
|------|------|
| 导出格式 | CSV/Excel/JSON/Parquet |
| 定时导出 | 按调度任务定时导出数据 |
| 数据过滤 | 按条件筛选导出字段/数据 |
| 自动清理 | 导出文件定期清理 |

### 3.9 操作审计

| 功能 | 说明 |
|------|------|
| 操作日志 | 记录用户所有操作行为 |
| 变更追溯 | 配置变更历史可追溯 |
| 审计报表 | 生成审计报告 |
| 合规检查 | 满足安全合规要求 |

---

## 四、数据模型设计

### 4.1 核心实体关系

```
User ──1:N──> Team
Team ──1:N──> Project
Project ──1:N──> ProjectVersion
Project ──1:N──> Spider
Spider ──1:N──> Schedule
Schedule ──1:N──> TaskInstance
TaskInstance ──1:1──> Container
Project ──1:N──> AlertRule
Spider ──1:N──> DataQualityReport
```

### 4.2 核心表结构

**project（项目表）**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| name | VARCHAR(128) | 项目名称 |
| team_id | BIGINT | 所属团队 |
| description | TEXT | 项目描述 |
| git_url | VARCHAR(512) | Git 仓库地址 |
| status | ENUM | active/archived/deleted |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**project_version（项目版本表）**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| project_id | BIGINT | 所属项目 |
| version | VARCHAR(32) | 版本号 |
| package_url | VARCHAR(512) | 项目包存储路径 |
| config_snapshot | JSON | 配置快照 |
| image_tag | VARCHAR(128) | Docker 镜像标签 |
| status | ENUM | building/ready/deployed |
| created_at | DATETIME | 创建时间 |

**schedule（调度表）**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| spider_id | BIGINT | 关联爬虫 |
| schedule_type | ENUM | cron/interval/once/dependency |
| cron_expr | VARCHAR(64) | Cron 表达式 |
| interval_seconds | INT | 间隔秒数 |
| priority | INT | 优先级 |
| max_concurrency | INT | 最大并发实例数 |
| timeout_seconds | INT | 超时秒数 |
| retry_strategy | JSON | 重试策略 |
| enabled | BOOLEAN | 是否启用 |
| next_run_time | DATETIME | 下次执行时间 |

**task_instance（任务实例表）**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| schedule_id | BIGINT | 关联调度 |
| spider_name | VARCHAR(128) | 爬虫名称 |
| status | ENUM | pending/running/success/failed/timeout |
| worker_node | VARCHAR(64) | 执行节点 |
| container_id | VARCHAR(64) | 容器 ID |
| started_at | DATETIME | 开始时间 |
| finished_at | DATETIME | 结束时间 |
| stats | JSON | 运行统计 |
| log_url | VARCHAR(512) | 日志路径 |

**alert_rule（告警规则表）**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| project_id | BIGINT | 所属项目 |
| rule_type | ENUM | status/threshold/timeout/resource/data |
| condition | JSON | 触发条件 |
| channel | JSON | 通知通道 |
| enabled | BOOLEAN | 是否启用 |

**proxy_pool（代理池表）**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| ip | VARCHAR(64) | 代理 IP |
| port | INT | 端口 |
| protocol | ENUM | HTTP/HTTPS/SOCKS5 |
| region | VARCHAR(64) | 地域 |
| group_name | VARCHAR(64) | 分组名称 |
| health_score | DECIMAL(5,2) | 健康评分(0-100) |
| status | ENUM | active/inactive/blocked |
| last_checked_at | DATETIME | 最后检查时间 |
| created_at | DATETIME | 创建时间 |

**api_config（API 配置表）**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| project_id | BIGINT | 所属项目 |
| name | VARCHAR(128) | API 名称 |
| base_url | VARCHAR(512) | 基础 URL |
| auth_type | ENUM | none/api_key/oauth2 |
| api_key | VARCHAR(256) | 加密后的密钥 |
| rate_limit | INT | 每分钟请求限制 |
| circuit_breaker_threshold | INT | 熔断阈值 |
| enabled | BOOLEAN | 是否启用 |

**audit_log（审计日志表）**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| user_id | BIGINT | 操作用户 |
| action | VARCHAR(64) | 操作类型 |
| resource_type | VARCHAR(64) | 资源类型 |
| resource_id | BIGINT | 资源 ID |
| old_value | JSON | 旧值 |
| new_value | JSON | 新值 |
| ip_address | VARCHAR(64) | 操作 IP |
| created_at | DATETIME | 操作时间 |

**environment_config（环境配置表）**
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| project_id | BIGINT | 所属项目 |
| env_name | VARCHAR(32) | 环境名称(dev/test/prod) |
| config | JSON | 环境配置 |
| is_active | BOOLEAN | 是否激活 |

---

## 五、API 设计

### 5.1 API 规范

- RESTful 风格
- 统一响应格式：`{"code": 0, "message": "ok", "data": {}}`
- 分页参数：`page`, `page_size`
- 认证方式：JWT Token

### 5.2 核心 API 列表

**项目管理**
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/projects | 项目列表 |
| POST | /api/v1/projects | 创建项目 |
| GET | /api/v1/projects/{id} | 项目详情 |
| PUT | /api/v1/projects/{id} | 更新项目 |
| DELETE | /api/v1/projects/{id} | 删除项目 |
| POST | /api/v1/projects/{id}/versions | 上传新版本 |
| POST | /api/v1/projects/{id}/deploy | 部署项目 |

**任务调度**
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/schedules | 调度列表 |
| POST | /api/v1/schedules | 创建调度 |
| PUT | /api/v1/schedules/{id} | 更新调度 |
| POST | /api/v1/schedules/{id}/trigger | 手动触发 |
| POST | /api/v1/schedules/{id}/pause | 暂停调度 |
| POST | /api/v1/schedules/{id}/resume | 恢复调度 |
| GET | /api/v1/tasks | 任务实例列表 |
| GET | /api/v1/tasks/{id}/logs | 任务日志 |

**运行监控**
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/monitor/overview | 全局概览 |
| GET | /api/v1/monitor/projects/{id}/status | 项目状态 |
| GET | /api/v1/monitor/nodes | 节点列表 |
| GET | /api/v1/monitor/metrics | Prometheus 指标 |
| WS | /ws/tasks/{task_id}（实际实现，无 API 前缀） | 实时日志推送 |

**~~数据质量~~（2026-08-07 取消）**
| 方法 | 路径 | 说明 |
|------|------|------|
| ~~GET~~ | ~~/api/v1/data-quality/reports~~ | ~~质量报告列表~~ |
| ~~GET~~ | ~~/api/v1/data-quality/stats~~ | ~~数据统计~~ |
| ~~POST~~ | ~~/api/v1/data-quality/check~~ | ~~触发检测~~ |

**用户权限**
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/auth/login | 登录 |
| GET | /api/v1/users | 用户列表 |
| POST | /api/v1/users | 创建用户 |
| GET | /api/v1/roles | 角色列表 |
| PUT | /api/v1/roles/{id}/permissions | 更新权限 |

**代理池**
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/proxies | 代理列表 |
| POST | /api/v1/proxies | 添加代理 |
| PUT | /api/v1/proxies/{id} | 更新代理 |
| DELETE | /api/v1/proxies/{id} | 删除代理 |
| POST | /api/v1/proxies/check | 批量健康检查 |

**API 配置**
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/api-configs | API 列表 |
| POST | /api/v1/api-configs | 创建 API 配置 |
| PUT | /api/v1/api-configs/{id} | 更新配置 |
| GET | /api/v1/api-configs/{id}/stats | 调用统计 |

**数据导出**
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/exports | 创建导出任务 |
| GET | /api/v1/exports/{id}/status | 导出状态 |
| GET | /api/v1/exports/{id}/download | 下载导出文件 |

**审计日志**
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/audit-logs | 审计日志列表 |

---

## 六、Docker 容器化方案

### 6.1 容器架构

```
┌─────────────────────────────────────────────┐
│               CrawloPilot                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │  API      │  │ Scheduler│  │  Worker   │ │
│  │  Server   │  │  Server  │  │  (N 个)   │ │
│  └──────────┘  └──────────┘  └───────────┘ │
├─────────────────────────────────────────────┤
│               Spider Containers              │
│  ┌────────┐  ┌────────┐  ┌────────┐        │
│  │Spider A│  │Spider B│  │Spider C│  ...    │
│  └────────┘  └────────┘  └────────┘        │
└─────────────────────────────────────────────┘
```

### 6.2 Spider 容器生命周期

```
创建容器 → 启动 → 健康检查 → 运行 → 采集指标
→ 完成/超时/异常 → 停止 → 保存日志/统计 → 清理
```

### 6.3 Spider 基础镜像

```dockerfile
FROM python:3.10-slim
RUN pip install crawlo
WORKDIR /app
COPY . .
ENTRYPOINT ["crawlo", "run"]
```

### 6.4 资源限制

| 资源 | 默认限制 | 说明 |
|------|----------|------|
| CPU | 1 core | 可按项目调整 |
| 内存 | 512MB | 可按项目调整 |
| 磁盘 | 1GB | 日志 + 临时文件 |
| 网络 | 不限 | 可按需限制带宽 |

---

## 七、实时通信方案

### 7.1 状态推送

| 场景 | 技术 | 说明 |
|------|------|------|
| 实时日志 | WebSocket | 容器日志流式推送 |
| 状态变更 | SSE | 爬虫状态变化推送 |
| 告警通知 | WebSocket + Webhook | 实时告警 + 外部回调 |

### 7.2 指标采集

```
Spider 容器 → StatsD Exporter → Prometheus → Grafana
                                        → 告警引擎
```

---

## 八、部署架构

### 8.1 单机部署（开发/测试）

```
Docker Compose
├── api-server
├── mysql
└── frontend (nginx)
```

### 8.2 集群部署（生产）

```
┌────────────── Master Node ──────────────┐
│  Nginx → API Server (x2)                │
│  Scheduler（进程内 APScheduler，主备）    │
│  MySQL (主从)                            │
│  MinIO                                  │
│  Prometheus + Grafana                   │
│  ELK                                    │
└─────────────────────────────────────────┘
┌────────────── Worker Node 1 ────────────┐
│  Docker Engine                          │
│  Spider Container A                     │
│  Spider Container B                     │
└─────────────────────────────────────────┘
┌────────────── Worker Node N ────────────┐
│  Docker Engine                          │
│  Spider Container C                     │
└─────────────────────────────────────────┘
```

---

## 九、高可用与灾备

### 9.1 高可用设计

| 组件 | 高可用方案 |
|------|------------|
| API Server | 多实例 + Nginx 负载均衡 |
| Scheduler | 主备切换（数据库行锁，按需选型） |
| MySQL | 主从复制 + 自动故障转移 |
| MinIO | 分布式对象存储 |

### 9.2 备份恢复

| 类型 | 策略 | 保留周期 |
|------|------|----------|
| MySQL | 每日全量 + 每小时增量 | 30 天 |
| MinIO | 跨区域复制 | 永久 |
| 配置备份 | 版本化管理（Git） | 永久 |

### 9.3 故障转移

```
故障检测 → 健康检查失败 → 触发告警
→ 自动切换备用节点 → 恢复服务 → 记录故障日志
```

---

## 十、安全加固

### 10.1 网络安全

| 措施 | 说明 |
|------|------|
| 防火墙 | 限制端口访问，仅开放必要端口 |
| WAF | Web 应用防火墙，防 SQL 注入/XSS |
| HTTPS | 全站 HTTPS，TLS 1.2+ |
| IP 白名单 | 管理后台限制访问 IP |

### 10.2 数据安全

| 措施 | 说明 |
|------|------|
| 密钥加密 | API Key/数据库密码 AES-256 加密 |
| 密钥轮换 | 定期自动轮换密钥 |
| 敏感字段脱敏 | 日志/导出时自动脱敏 |
| 访问审计 | 所有数据访问记录日志 |

### 10.3 容器安全

| 措施 | 说明 |
|------|------|
| 最小权限 | 容器以非 root 用户运行 |
| 镜像扫描 | 部署前扫描镜像漏洞 |
| 资源隔离 | cgroups 隔离 CPU/内存 |
| 只读文件系统 | 非必要目录只读挂载 |

---

## 十一、运维管理

### 11.1 自动扩缩容

| 策略 | 说明 |
|------|------|
| 触发条件 | CPU > 80% 或队列深度 > 阈值 |
| 扩容动作 | 自动创建 Worker 节点 |
| 缩容动作 | 空闲节点自动回收 |
| 冷却时间 | 扩容/缩容间隔 5 分钟 |

### 11.2 成本控制

| 功能 | 说明 |
|------|------|
| 资源用量统计 | CPU/内存/存储/网络用量 |
| 费用预估 | 根据用量预估月度成本 |
| 预算告警 | 超出预算阈值时告警 |
| 优化建议 | 识别闲置资源并建议回收 |

### 11.3 文档中心

| 功能 | 说明 |
|------|------|
| 使用文档 | 平台功能使用说明 |
| FAQ | 常见问题解答 |
| 最佳实践 | 爬虫开发/部署最佳实践 |
| API 文档 | Swagger 自动生成 |

---

## 十二、与 Crawlo 框架集成点

### 12.1 框架侧适配

| 集成点 | 说明 | 当前状态 |
|--------|------|----------|
| Stats 采集 | 平台解析任务日志，回写 pages/items/errors | 已实现（V1） |
| 日志输出 | 结构化日志 + 远程采集 | 框架已有 logging 模块 |
| 健康检查 | HTTP 健康端点 | 需新增 |
| 优雅关闭 | 信号处理 + 检查点保存 | 框架已有 checkpoint |
| 配置注入 | 环境变量覆盖 settings | 框架已有 EnvConfigManager |

### 12.2 需新增的框架能力

| 能力 | 说明 |
|------|------|
| /health 端点 | HTTP 健康检查接口，供 Docker HEALTHCHECK 使用 |
| StatsD 上报 | 运行指标推送到 StatsD |
| 结构化日志 | JSON 格式日志，便于 ELK 解析 |
| 远程配置拉取 | 启动时从管理平台拉取配置 |

---

## 十三、开发阶段规划

### Phase 1：核心基座（4 周）
- 用户/权限/团队管理
- 项目注册与版本管理
- 基础 API 框架

### Phase 2：部署引擎（4 周）
- Docker 容器生命周期管理
- 项目构建与镜像管理
- 部署策略实现

### Phase 3：调度系统（3 周）
- Cron/间隔/一次性调度
- 依赖调度（DAG）
- 任务实例管理

### Phase 4：监控告警（3 周）
- 实时状态监控
- 日志流式推送
- 告警规则引擎

### ~~Phase 5：数据质量（2 周）~~（2026-08-07 取消）
- ~~数据质量检测~~
- ~~统计报表~~

### Phase 6：代理池与 API 管理（2 周）
- 代理池管理
- API 接口管理
- 限流与熔断

### Phase 7：生产加固（2 周）
- 高可用设计
- 安全加固
- 操作审计
- 灾备方案

### Phase 8：运维增强（2 周）
- 自动扩缩容
- 成本控制
- 数据导出
- 文档中心
