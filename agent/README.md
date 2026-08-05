# CrawloPilot Agent

部署在目标服务器上的轻量执行代理，主动连接 CrawloPilot 控制端，
负责领取任务、执行爬虫、回报状态/日志/指标。

## 特性

- 纯 Python 标准库，无需额外依赖，Linux/macOS/Windows 均可运行
- 反向连接控制端，节点无需公网 IP，可穿透 NAT/防火墙
- 控制端不持有节点 SSH 凭据，安全边界清晰
- 自动安装 crawlo（缺失时 pip 安装，默认国内镜像）
- 心跳 / 任务轮询 / 日志实时上报 / 停止指令

## 用法

### 1. 在平台创建 Agent 节点

节点管理 → 添加节点 → 连接方式选择「Agent 代理」→ 创建后复制注册令牌。

### 2. 在节点服务器上启动 Agent

```bash
python crawlo_agent.py --server http://<控制端IP>:8000 --token <注册令牌>
```

可选参数：

- `--poll-interval <秒>`：任务轮询间隔（默认 5 秒）
- 环境变量 `PIP_INDEX_URL`：pip 镜像地址（默认清华源）

### 3. 运行爬虫

爬虫详情 → 运行对话框 → 选择「节点」→ 选中该 Agent 节点 → 运行。
任务状态、实时日志、指标会自动回报到平台。

## 开发

- `backend/app/api/v1/agent.py`：控制端 Agent 接口（注册/心跳/任务/代码/回报/日志）
- `backend/app/services/agent_service.py`：Agent 任务状态/日志/停止服务端
- `agent/crawlo_agent.py`：节点 Agent 程序
