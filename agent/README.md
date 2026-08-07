# CrawloPilot Agent

部署在目标服务器上的轻量执行代理，主动连接 CrawloPilot 控制端，
负责领取任务、执行爬虫、回报状态/日志/指标。

## 工作原理

与 SSH/Docker 模式（控制端主动连服务器）相反，Agent 是**拉模式**：
所有连接都由 agent 向控制端发起（出站 HTTP），服务器无需公网 IP、
无需对控制端开放任何端口。

```text
启动 → register（注册，换取 node_id）
     → heartbeat 循环（周期心跳，控制端据此判定在线/离线）
     → poll_task 循环（每 5s 询问"有我的任务吗"）
        ├─ 无任务 → 继续轮询
        └─ 有任务 → 下载代码包 → 本地执行（自动装 crawlo 与 requirements）
                  → 日志实时上报 → 终态回报（状态/指标）
                  → 停止指令同样经轮询获得（stop_requested 标记）
```

安全性：agent 只持有 token，权限仅限于"注册/心跳/领任务/传日志/回报"，
控制端不接触服务器的任何登录凭据。

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
