# CrawloPilot 心跳监控机制 - 零侵入方案

**时间**: 2026-04-12  
**主题**: 实时监控、心跳机制、不需要 SDK

---

## 🎯 核心思路

**问题**: 如何实时监控爬虫状态,但不修改爬虫代码?

**答案**: 在 `spider-runner` 容器内运行**独立的心跳进程**,不侵入爬虫!

---

## 📊 方案设计

### 方案对比

| 方案 | 侵入性 | 实现难度 | 实时性 | 推荐度 |
|------|--------|---------|--------|--------|
| **SDK 心跳** | ❌ 需要修改爬虫 | 高 | 高 | ❌ |
| **日志采集** | ✅ 零侵入 | 中 | 中 | ✅ 当前 |
| **独立心跳进程** | ✅ 零侵入 | 低 | 高 | ✅ 推荐 |
| **Docker 监控** | ✅ 零侵入 | 低 | 中 | ✅ 补充 |

---

## 🔥 推荐方案: 独立心跳进程

### 架构设计

```
Docker 容器
├─ 主进程: 爬虫 (不修改)
│   └─ crawlo run spider_name
│
└─ 后台进程: 心跳监控 (独立运行)
    ├─ 每 5 秒发送心跳
    ├─ 读取容器资源使用
    ├─ 监控主进程状态
    └─ 上报平台 API
```

### 实现方式

#### 1. 心跳监控脚本

```python
# spider-runner/heartbeat.py

import os
import time
import requests
import psutil
from datetime import datetime

class HeartbeatMonitor:
    """心跳监控器 (独立进程,不侵入爬虫)"""
    
    def __init__(self):
        self.task_id = os.environ.get('TASK_ID')
        self.api_url = os.environ.get('API_URL')
        self.api_token = os.environ.get('API_TOKEN')
        self.interval = 5  # 5 秒一次
        
    def start(self):
        """启动心跳"""
        print(f"❤️  心跳监控启动: task_id={self.task_id}")
        print(f"   API: {self.api_url}")
        print(f"   间隔: {self.interval}秒")
        
        while True:
            try:
                self._send_heartbeat()
                time.sleep(self.interval)
            except KeyboardInterrupt:
                print("\n⏹️  心跳监控停止")
                break
            except Exception as e:
                print(f"❌ 心跳发送失败: {e}")
                time.sleep(self.interval)
    
    def _send_heartbeat(self):
        """发送心跳"""
        # 获取容器资源使用
        metrics = self._get_container_metrics()
        
        # 检查主进程状态
        main_process = self._check_main_process()
        
        # 构建心跳数据
        heartbeat_data = {
            "task_id": self.task_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "running" if main_process else "zombie",
            "metrics": metrics,
            "main_process_alive": main_process
        }
        
        # 发送到平台
        if self.api_url and self.api_token:
            try:
                resp = requests.post(
                    f"{self.api_url}/api/v1/execution/tasks/{self.task_id}/heartbeat",
                    json=heartbeat_data,
                    headers={"Authorization": f"Bearer {self.api_token}"},
                    timeout=5
                )
                
                if resp.status_code == 200:
                    print(f"❤️  心跳发送成功")
                else:
                    print(f"⚠️  心跳发送失败: {resp.status_code}")
                    
            except Exception as e:
                print(f"❌ 心跳请求失败: {e}")
        else:
            # 调试模式: 打印到控制台
            print(f"❤️  心跳: {metrics}")
    
    def _get_container_metrics(self):
        """获取容器资源使用"""
        try:
            import psutil
            
            # CPU 使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用
            memory = psutil.virtual_memory()
            memory_used = memory.used / 1024 / 1024  # MB
            memory_total = memory.total / 1024 / 1024  # MB
            
            return {
                "cpu_percent": cpu_percent,
                "memory_used_mb": memory_used,
                "memory_total_mb": memory_total,
                "memory_percent": memory.percent
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _check_main_process(self):
        """检查主进程 (爬虫) 是否存活"""
        try:
            # 查找父进程
            parent = psutil.Process().parent()
            
            if parent and parent.status() == psutil.STATUS_ZOMBIE:
                return False
            
            return True
        except:
            return False


if __name__ == '__main__':
    monitor = HeartbeatMonitor()
    monitor.start()
```

#### 2. 更新 Dockerfile

```dockerfile
# spider-runner/Dockerfile

FROM python:3.10-slim

WORKDIR /spider

# 安装依赖
RUN pip install --no-cache-dir \
    crawlo \
    psutil \
    requests

# 复制心跳脚本
COPY heartbeat.py /spider/heartbeat.py

# ... 其他配置
```

#### 3. 更新启动脚本

```python
# spider-runner/run_spider.py

def main():
    """主函数"""
    # ... 原有代码 ...
    
    # 启动心跳监控 (后台进程)
    import subprocess
    heartbeat_proc = subprocess.Popen(
        ['python', '/spider/heartbeat.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        background=True
    )
    
    # 运行爬虫 (主进程)
    if entry_file:
        subprocess.run(['python', entry_file], cwd='/spider/code')
    else:
        subprocess.run(['crawlo', 'run', spider_name], cwd='/spider/code')
    
    # 爬虫结束后,停止心跳
    heartbeat_proc.terminate()
```

---

## 📡 平台端 API

### 心跳接收接口

```python
# backend/app/api/v1/execution.py

@router.post("/tasks/{task_id}/heartbeat")
async def receive_heartbeat(
    task_id: str,
    heartbeat_data: dict,
    db: Session = Depends(get_db)
):
    """接收爬虫心跳"""
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 更新心跳时间
    task.last_heartbeat_at = datetime.utcnow()
    
    # 更新指标
    metrics = heartbeat_data.get('metrics', {})
    task.cpu_percent = metrics.get('cpu_percent')
    task.memory_used = metrics.get('memory_used_mb')
    
    # 检查状态
    if not heartbeat_data.get('main_process_alive'):
        task.status = TaskStatus.FAILED
        task.error_message = "主进程异常退出"
    
    db.commit()
    
    return {"status": "ok"}
```

### 数据库模型

```python
# backend/app/models/__init__.py

class TaskInstance(Base):
    # ... 原有字段 ...
    
    # 心跳相关
    last_heartbeat_at = Column(DateTime)  # 最后心跳时间
    cpu_percent = Column(Float)           # CPU 使用率
    memory_used = Column(Float)           # 内存使用 (MB)
```

---

## 🎯 完整流程

### 启动流程

```
1. 平台创建容器
   ↓
2. 容器启动 run_spider.py
   ↓
3. run_spider.py 启动两个进程:
   ├─ 主进程: crawlo run spider_name (爬虫)
   └─ 后台进程: python heartbeat.py (心跳)
   ↓
4. 心跳进程每 5 秒:
   ├─ 采集资源指标 (CPU/内存)
   ├─ 检查主进程状态
   └─ 发送心跳到平台 API
   ↓
5. 平台接收心跳:
   ├─ 更新 last_heartbeat_at
   ├─ 更新资源指标
   └─ 检测异常 (超时未心跳)
```

### 异常检测

```python
# 平台定时任务 (每 30 秒)

async def check_heartbeat_timeout():
    """检查心跳超时"""
    tasks = db.query(TaskInstance).filter(
        TaskInstance.status == TaskStatus.RUNNING
    ).all()
    
    for task in tasks:
        if task.last_heartbeat_at:
            # 计算超时
            timeout = (datetime.utcnow() - task.last_heartbeat_at).total_seconds()
            
            if timeout > 60:  # 60 秒未心跳
                logger.warning(f"Task {task.id} heartbeat timeout!")
                
                # 标记为失败
                task.status = TaskStatus.FAILED
                task.error_message = f"Heartbeat timeout ({timeout}s)"
                
                # 停止容器
                await executor.stop_task(task.id)
                
                db.commit()
```

---

## 📊 前端展示

### 实时状态面板

```vue
<template>
  <div class="task-monitor">
    <!-- 心跳状态 -->
    <div class="heartbeat-status">
      <el-icon :color="heartbeatAlive ? '#67C23A' : '#F56C6C'">
        <component :is="heartbeatAlive ? 'CircleCheck' : 'CircleClose'" />
      </el-icon>
      <span>{{ heartbeatAlive ? '心跳正常' : '心跳超时' }}</span>
    </div>
    
    <!-- 资源使用 -->
    <div class="metrics">
      <div class="metric">
        <span>CPU:</span>
        <el-progress :percentage="task.cpu_percent" />
      </div>
      
      <div class="metric">
        <span>内存:</span>
        <el-progress :percentage="task.memory_percent" />
      </div>
    </div>
    
    <!-- 最后心跳时间 -->
    <div class="last-heartbeat">
      最后心跳: {{ formatTime(task.last_heartbeat_at) }}
    </div>
  </div>
</template>
```

---

## ✅ 优势对比

### vs SDK 方案

| 对比项 | SDK 方案 | 独立心跳进程 |
|--------|---------|-------------|
| **侵入性** | ❌ 需要导入 SDK | ✅ 完全零侵入 |
| **修改爬虫** | ❌ 需要修改代码 | ✅ 不需要 |
| **部署复杂度** | ❌ 每个爬虫安装 SDK | ✅ 容器内置 |
| **实时性** | ✅ 高 | ✅ 高 (5秒) |
| **资源监控** | ❌ 需要额外实现 | ✅ psutil 直接获取 |
| **故障隔离** | ❌ SDK 错误影响爬虫 | ✅ 独立进程,互不影响 |

### vs 纯日志采集

| 对比项 | 日志采集 | 心跳机制 |
|--------|---------|---------|
| **实时性** | ⚠️ 5秒延迟 | ✅ 5秒心跳 |
| **资源监控** | ❌ 无法获取 | ✅ CPU/内存 |
| **进程状态** | ❌ 需要解析日志 | ✅ 直接检查 |
| **异常检测** | ⚠️ 依赖日志关键词 | ✅ 超时自动检测 |
| **网络开销** | ✅ 无 | ⚠️ 每 5 秒 HTTP |

---

## 🚀 实现建议

### 第一阶段: 日志采集 (已完成)

✅ 流式采集 Docker 日志  
✅ 解析 Crawlo 日志格式  
✅ 提取页面/数据/错误数  

### 第二阶段: 心跳监控 (推荐添加)

🔄 添加 heartbeat.py  
🔄 容器启动后台进程  
🔄 平台接收心跳 API  
🔄 超时自动检测  

### 第三阶段: WebSocket 推送 (未来优化)

🔮 实时推送日志和指标  
🔮 前端实时更新  
🔮 减少轮询延迟  

---

## 💡 总结

### 你的两个问题:

**1. 暂停爬虫是否需要考虑断点续爬?**

**答**: ❌ 不需要! 直接使用 Docker pause/unpause:
```python
container.pause()    # 暂停 (cgroup freezer)
container.unpause()  # 恢复
```
平台只负责容器控制,爬虫是否支持断点是框架的事!

**2. 是否需要心跳机制?**

**答**: ✅ 推荐! 但用**零侵入**方案:
- 不需要 SDK
- 不需要修改爬虫
- 在容器内运行独立心跳进程
- 通过 psutil 监控资源
- 每 5 秒上报平台

### 最佳方案:

```
日志采集 (已完成) + 心跳监控 (推荐) + Docker 监控 (补充)
= 完整的零侵入监控体系!
```

---

**心跳机制可以实现,而且完全零侵入! 不需要 SDK!** 🎯
