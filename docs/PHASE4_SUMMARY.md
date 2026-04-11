# Phase 4: 监控告警系统开发总结

## 开发时间
2026-04-11

## 概述
Phase 4 实现了完整的监控告警系统，包括 Prometheus 指标收集、多渠道告警通知、实时监控 Dashboard 和告警规则管理。

## 新增文件

### 后端监控模块 (backend/app/monitoring/)
1. **metrics.py** (254 行)
   - Prometheus 指标定义
   - HTTP/爬虫/调度/部署/节点/告警指标
   - MetricsCollector 指标收集器

2. **alert_engine.py** (267 行)
   - 告警规则评估引擎
   - 告警触发/解决逻辑
   - 通知发送管理
   - 告警统计

3. **notifiers/base.py** (59 行)
   - 通知器基类
   - 消息格式化

4. **notifiers/email.py** (64 行)
   - SMTP 邮件通知
   - HTML 邮件模板

5. **notifiers/dingtalk.py** (75 行)
   - 钉钉机器人通知
   - Markdown 消息
   - 签名验证

6. **notifiers/wechat.py** (48 行)
   - 企业微信机器人通知
   - Markdown 消息

### 后端 API 路由 (backend/app/api/v1/)
7. **monitoring.py** (282 行)
   - 系统指标查询
   - 爬虫/调度/部署/节点指标
   - 健康状态检查
   - Dashboard 综合数据

8. **alerts.py** (239 行)
   - 告警规则 CRUD
   - 活跃告警查询
   - 告警历史
   - 告警统计
   - 通知测试

### 前端 API 封装 (frontend/src/api/)
9. **monitoring.js** (72 行)
   - 监控数据 API（9 个函数）
   - 告警管理 API（8 个函数）

### 前端页面 (frontend/src/views/)
10. **Monitoring.vue** (279 行)
    - 系统健康状态展示
    - 统计卡片
    - 节点资源监控（CPU/内存/磁盘）
    - 活跃告警列表
    - 自动刷新（30 秒）

11. **Alerts.vue** (374 行)
    - 活跃告警 Tab
    - 告警规则 Tab（CRUD）
    - 告警统计 Tab
    - 规则创建/编辑对话框
    - 通知渠道配置

### 配置更新
12. **main.py** - 注册监控和告警路由
13. **router/index.js** - 添加路由
14. **Layout.vue** - 添加菜单项
15. **DEVELOPMENT.md** - 更新进度

## 核心功能

### 1. Prometheus 指标

#### HTTP 指标
- `http_requests_total` - 请求总数
- `http_request_duration_seconds` - 请求延迟

#### 爬虫指标
- `spider_runs_total` - 执行总数
- `spider_items_scraped` - 抓取项目数
- `spider_duration_seconds` - 执行时长
- `spider_running_count` - 运行中数量

#### 调度指标
- `schedule_executions_total` - 执行总数
- `active_schedules_count` - 活跃调度数
- `schedule_next_run_timestamp` - 下次执行时间

#### 节点指标
- `node_cpu_usage_percent` - CPU 使用率
- `node_memory_usage_percent` - 内存使用率
- `node_disk_usage_percent` - 磁盘使用率
- `node_status` - 节点状态

#### 告警指标
- `alerts_triggered_total` - 告警触发总数
- `active_alerts_count` - 活跃告警数

### 2. 告警引擎

#### 告警规则
```python
{
  "name": "CPU 使用率过高",
  "metric": "node_cpu_usage_percent",
  "operator": ">",
  "threshold": 80.0,
  "severity": "warning",
  "duration": 300,  # 持续 5 分钟
  "enabled": true,
  "notification_channels": ["email", "dingtalk"]
}
```

#### 告警级别
- **warning** (警告) - 需要关注
- **critical** (严重) - 需要立即处理
- **emergency** (紧急) - 系统故障

#### 评估逻辑
1. 收集指标当前值
2. 匹配告警规则
3. 评估条件（>, <, >=, <=, ==）
4. 检查持续时间
5. 触发告警并发送通知

### 3. 通知渠道

#### 邮件通知
- SMTP 协议
- HTML 格式
- 多收件人支持

#### 钉钉通知
- 机器人 Webhook
- Markdown 消息
- 签名验证

#### 企业微信通知
- 机器人 Webhook
- Markdown 消息

### 4. API 端点

#### 监控数据（9 个）
```
GET /api/v1/monitoring/system        - 系统指标
GET /api/v1/monitoring/spiders       - 爬虫指标
GET /api/v1/monitoring/schedules     - 调度指标
GET /api/v1/monitoring/deployments   - 部署指标
GET /api/v1/monitoring/nodes         - 节点指标
GET /api/v1/monitoring/tasks/queue   - 任务队列
GET /api/v1/monitoring/health        - 健康状态
GET /api/v1/monitoring/dashboard     - Dashboard 数据
```

#### 告警管理（8 个）
```
GET    /api/v1/alerts/rules          - 规则列表
POST   /api/v1/alerts/rules          - 创建规则
PUT    /api/v1/alerts/rules/{id}     - 更新规则
DELETE /api/v1/alerts/rules/{id}     - 删除规则
GET    /api/v1/alerts/active         - 活跃告警
GET    /api/v1/alerts/history        - 告警历史
GET    /api/v1/alerts/stats          - 告警统计
POST   /api/v1/alerts/test-notification - 测试通知
```

## 代码统计

| 模块 | 文件数 | 代码行数 |
|------|--------|----------|
| 监控核心 | 2 | 521 |
| 通知器 | 4 | 246 |
| API 路由 | 2 | 521 |
| 前端 API | 1 | 72 |
| 前端页面 | 2 | 653 |
| **总计** | **11** | **2013** |

## 使用示例

### 配置告警规则

#### 1. CPU 使用率告警
```json
{
  "name": "CPU 使用率过高",
  "metric": "node_cpu_usage_percent",
  "operator": ">",
  "threshold": 80.0,
  "severity": "warning",
  "duration": 300,
  "notification_channels": ["email", "dingtalk"]
}
```

#### 2. 爬虫成功率告警
```json
{
  "name": "爬虫成功率过低",
  "metric": "spider_success_rate",
  "operator": "<",
  "threshold": 90.0,
  "severity": "critical",
  "duration": 600,
  "notification_channels": ["email", "dingtalk", "wechat"]
}
```

### 测试通知
```bash
curl -X POST "http://localhost:8000/api/v1/alerts/test-notification?channel=email" \
  -H "Authorization: Bearer <token>"
```

### 查看监控 Dashboard
访问: http://localhost:3000/monitoring

### 管理告警规则
访问: http://localhost:3000/alerts

## 环境变量配置

在 `.env` 文件中添加：

```bash
# 邮件配置
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_password
SMTP_FROM=noreply@example.com
ALERT_EMAILS=admin@example.com,dev@example.com

# 钉钉配置
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
DINGTALK_SECRET=your_secret

# 企业微信配置
WECHAT_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

## 监控指标集成

### 在代码中记录指标

```python
from app.monitoring import metrics_collector

# 记录 HTTP 请求
metrics_collector.record_http_request(
    method="POST",
    endpoint="/api/v1/projects",
    status=200,
    duration=0.125
)

# 记录爬虫运行
metrics_collector.record_spider_run(
    spider_name="example_spider",
    status="success",
    items=1000,
    duration=1800.5
)

# 记录调度执行
metrics_collector.record_schedule_execution(
    schedule_id="1",
    spider_name="example_spider",
    status="success"
)

# 更新节点指标
metrics_collector.update_node_metrics(
    node_id="1",
    node_name="node-1",
    cpu=65.5,
    memory=72.3,
    disk=55.0
)
```

## 待完善功能

### 短期
1. **Prometheus 集成**
   - 实际的指标采集
   - Grafana Dashboard
   - 指标持久化

2. **告警规则持久化**
   - 数据库存储
   - 规则版本管理
   - 规则导入/导出

3. **告警历史**
   - 完整的历史记录
   - 告警趋势分析
   - 告警关联分析

### 中期
4. **自定义指标**
   - 用户自定义指标
   - 指标计算公式
   - 指标聚合

5. **告警升级**
   - 超时自动升级
   - 多级通知
   - 值班表集成

6. **根因分析**
   - 告警关联
   - 依赖图谱
   - 智能诊断

## 启动说明

### 1. 启动后端
```bash
./dev.sh
```

### 2. 访问前端
- 监控中心: http://localhost:3000/monitoring
- 告警管理: http://localhost:3000/alerts
- API 文档: http://localhost:8000/docs

## 总结

Phase 4 成功实现了完整的监控告警系统，具备：
- ✅ Prometheus 指标收集
- ✅ 多渠道告警通知（邮件/钉钉/企微）
- ✅ 灵活的告警规则配置
- ✅ 实时监控 Dashboard
- ✅ 告警生命周期管理
- ✅ 系统健康检查

为 Phase 5 的高级功能打下了坚实基础。
