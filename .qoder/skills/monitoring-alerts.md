# 监控告警系统

## 概述
CrawloPilot使用Prometheus + Grafana实现完整的监控告警体系。

## 架构

### 组件
- **Prometheus**: 指标采集和存储
- **Grafana**: 可视化仪表板
- **AlertManager**: 告警规则管理
- **Notifiers**: 多渠道通知（邮件/钉钉/企业微信）

### 指标类型
- **系统指标**: CPU、内存、磁盘、网络
- **爬虫指标**: 爬取速率、成功率、数据量
- **调度指标**: 任务执行时间、成功率、队列长度
- **部署指标**: 容器状态、部署频率、回滚次数
- **API指标**: 请求速率、响应时间、错误率

## Prometheus配置

### 配置文件
位置: `docker/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'crawlopilot'
    static_configs:
      - targets: ['backend:8000']
```

### 指标端点
- 后端: `http://localhost:8000/metrics`
- Prometheus: `http://localhost:9090`

## Grafana仪表板

### 访问
- 地址: `http://localhost:3001`
- 默认账号: admin/admin

### 预置仪表板
位置: `docker/grafana/dashboards/crawlopilot-dashboard.json`

包含面板：
1. **系统概览** - CPU、内存、磁盘使用率
2. **爬虫监控** - 爬取速率、成功率趋势
3. **任务调度** - 执行状态、队列长度
4. **API性能** - 响应时间、错误率
5. **部署状态** - 容器健康、部署历史

## 告警规则

### 配置位置
`backend/app/monitoring/alert_engine.py`

### 告警类型

#### 1. 爬虫告警
```python
# 爬虫失败率过高
if failure_rate > 20%:
    trigger_alert('spider_failure_rate', spider_name)

# 数据量异常
if data_volume < threshold:
    trigger_alert('data_volume_low', spider_name)
```

#### 2. 系统告警
```python
# CPU使用率过高
if cpu_usage > 85%:
    trigger_alert('cpu_high')

# 内存不足
if memory_usage > 90%:
    trigger_alert('memory_critical')
```

#### 3. 任务告警
```python
# 任务执行超时
if task_duration > timeout:
    trigger_alert('task_timeout', task_id)

# 任务连续失败
if consecutive_failures >= 3:
    trigger_alert('task_consecutive_failures', task_id)
```

## 通知渠道

### 1. 邮件通知
配置: `.env`
```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=alerts@example.com
SMTP_PASSWORD=password
ALERT_EMAIL=admin@example.com
```

### 2. 钉钉通知
配置: `.env`
```bash
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
```

### 3. 企业微信通知
配置: `.env`
```bash
WECHAT_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

## 健康检查

### 端点
- 后端健康: `GET /health`
- 数据库: `GET /api/v1/monitoring/health`

### 检查项
```python
{
    "status": "healthy",
    "database": "connected",
    "redis": "connected",
    "scheduler": "running",
    "workers": 3
}
```

## 监控API

### 获取系统指标
```javascript
import { getSystemMetrics } from '@/api/monitoring'

const metrics = await getSystemMetrics()
```

### 获取爬虫指标
```javascript
import { getSpiderMetrics } from '@/api/monitoring'

const spiderMetrics = await getSpiderMetrics({
  project_id: 1,
  days: 7
})
```

### 获取告警列表
```javascript
import { getActiveAlerts } from '@/api/monitoring'

const alerts = await getActiveAlerts({
  status: 'active'
})
```

## 最佳实践

### 1. 告警分级
- **P0 紧急**: 系统宕机、数据丢失 - 电话通知
- **P1 严重**: 核心功能失败 - 短信+邮件
- **P2 警告**: 性能下降 - 邮件+钉钉
- **P3 提示**: 信息通知 - 仅记录

### 2. 告警抑制
- 避免告警风暴
- 相同告警5分钟内只发送一次
- 维护窗口期间暂停告警

### 3. 指标优化
- 只采集必要的指标
- 使用合适的采集间隔
- 定期清理过期数据

## 故障排查

### Prometheus问题
```bash
# 查看Prometheus日志
docker logs crawlopilot-prometheus

# 检查targets状态
curl http://localhost:9090/api/v1/targets
```

### Grafana问题
```bash
# 查看Grafana日志
docker logs crawlopilot-grafana

# 重启Grafana
docker restart crawlopilot-grafana
```

### 告警未触发
1. 检查AlertManager配置
2. 验证告警规则语法
3. 查看通知渠道配置
4. 检查指标数据是否正常

## 扩展

### 添加新指标
```python
from prometheus_client import Gauge, Counter, Histogram

# 定义指标
SPIDER_DURATION = Histogram(
    'spider_duration_seconds',
    'Spider execution duration',
    ['spider_name']
)

# 记录数据
SPIDER_DURATION.labels(spider_name='example').observe(duration)
```

### 添加新通知渠道
```python
from app.monitoring.notifiers.base import BaseNotifier

class CustomNotifier(BaseNotifier):
    def send(self, alert):
        # 实现发送逻辑
        pass
```

## 访问地址
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001
- 后端指标: http://localhost:8000/metrics
