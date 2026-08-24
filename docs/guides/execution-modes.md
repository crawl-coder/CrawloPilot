> 📖 [docs 首页](../README.md) ｜ 关联：[节点管理原理](../modules/05-nodes.md)（为什么这样设计）｜ [部署执行实现](../modules/04-execution.md)（代码怎么跑）

# 执行模式使用指南：本地 / SSH / Docker / Agent

> 本文回答一个问题：**怎么把一个爬虫跑到目标机器上**。每种模式给出前置条件、操作步骤与排错入口；
> 四种模式的运行体验完全一致（同一运行对话框、同一任务详情页），差异只在"节点准备"这一步。

## 0. 开始之前：通用前置（一次即可）

无论哪种模式，先在平台上准备好爬虫（已就绪可跳过）：

```text
项目管理 → 创建项目 → 项目下创建爬虫 → 准备代码（Git 克隆 / ZIP 上传 / 在线编辑）
```

详见 [爬虫管理](../modules/03-spiders.md)。之后每次运行：

- 入口：**爬虫详情 → 「运行」对话框 → 选择节点**（不选节点 = 本地模式）；
- 定时触发：在爬虫表单或调度页配置，任务走同一条分发链路，见[定时调度设计](../designs/scheduling.md)。

> **代码如何到达节点？** 控制面把 `uploads/project_x/spider_x/` 打成 tar.gz 快照：
> SSH/Docker 为推（上传 / COPY 进镜像），Agent 为拉（节点认证后下载）。Git 只在
> 代码进入平台时用一次，执行节点不需要任何 Git 凭据。细节见[部署执行实现](../modules/04-execution.md)。

---

## 1. 本地模式（默认）

| | |
|---|---|
| 适用 | 开发调试、单机验收 |
| 前置 | 无（任务跑在控制面本机，子进程执行） |

**步骤**：运行对话框中**不选任何节点**，直接「运行」。

**验证**：任务详情页状态 `success`，实时日志滚动，指标（pages/items/errors）回写。

**说明**：`requirements.txt` 存在会自动安装；配了 `entry_file` 则精确执行 `python <entry_file>`。支持暂停/恢复（唯一支持的模式）。

---

## 2. SSH 模式

| | |
|---|---|
| 适用 | 有可达 IP 的云服务器，台数少，即配即用 |
| 前置 | 服务器 22 端口对控制面可达；账号可用密码或私钥登录；有 `python3` |

**步骤**：

```text
① 节点管理 → 添加服务器（名称 + IP）
② 服务器下创建通道 → 类型选 SSH → 填 用户 + 密码/私钥
③ 「测试连接」（握手 + python3 探测）→ 通过后「激活」
④ 爬虫详情 → 运行 → 选该 SSH 节点 → 运行
```

**行为**：控制面上传代码包到远端临时目录，`nohup` 启动进程，按 PID 轮询存活与日志。

**常见问题**：

| 现象 | 处理 |
|---|---|
| 测试连接失败 | 安全组放行 22；确认账号密码/私钥正确；云厂商密钥登录的机器需粘贴私钥内容而非密码 |
| 握手通过但激活失败 | 远端缺 `python3`（探测依赖它），`yum/apt install python3` |
| 任务 running 但无日志 | 多为远端 Python 输出缓冲（SSH 模式不注入 `PYTHONUNBUFFERED`），脚本里用 `print(..., flush=True)` 或运行前 `export PYTHONUNBUFFERED=1` |

---

## 3. Docker 模式

| | |
|---|---|
| 适用 | 节点有 Docker，要环境隔离与镜像复用 |
| 前置 | 节点 Docker daemon 对控制面可达（socket 或 tcp） |

**步骤**：

```text
① 服务器下创建通道 → 类型选 Docker → 填 daemon 地址
   - 与控制面同机：unix:///var/run/docker.sock
   - 远程节点：tcp://<IP>:2375（需 daemon 开启远程 API 且端口可达）
② 测试连接 → 激活
③ 运行爬虫 → 选该 Docker 节点
```

**镜像策略**（无需手工构建）：代码目录有 `Dockerfile` 则按项目 Dockerfile 构建，失败自动回退内置模板（`FROM crawlopilot/base:1.7.3`）；镜像按内容摘要缓存，代码不变秒级复用。

**常见问题**：

| 现象 | 处理 |
|---|---|
| 测试连接失败（远程） | daemon 未开远程 API 或安全组未放行 2375；云服务器 VPC 无 DNAT 时可用 SSH 隧道，见[开发调试环境方案](../designs/dev-hybrid-deployment.md) |
| 构建失败 | 查看 task 日志中的 build 输出；项目 Dockerfile 语法错误会回退内置模板重试 |
| Mac 本机 | Docker Desktop 已提供 socket，直接用默认 `unix:///var/run/docker.sock` |

---

## 4. Agent 模式

| | |
|---|---|
| 适用 | 节点在 NAT/防火墙后（家宽/内网/VPC）、不想交出 SSH 凭据、批量横向扩展 |
| 前置 | 节点能**出站**访问控制面 `http://<控制面>:18000`；节点有 `python3`（≥3.8，纯标准库） |

**步骤**：

```text
① 服务器下创建通道 → 类型选 Agent → 平台生成 token
② 部署 agent（二选一）：
   一键部署（推荐）：该服务器已有 SSH 通道时，点「批量部署 Agent」，
     自动上传脚本 + systemd 托管（开机自启/崩溃重启）
   手动部署：在节点上执行
     python3 crawlo_agent.py --server http://<控制面>:18000 --token <token>
③ 节点自动注册上线（心跳 30s；离线判定窗口约 60–90s）
④ 运行爬虫 → 选该 Agent 节点
```

**网络拓扑对照**（agent 必须能连到控制面）：

| 控制面位置 | agent 连接地址 | 是否需要穿透 |
|---|---|---|
| 云服务器（生产，推荐） | `http://<公网IP>:18000` | 不需要 |
| 内网/NAT 后（开发机） | 经 frp/SSH 反向隧道映射的地址 | 需要，见[开发调试环境方案](../designs/dev-hybrid-deployment.md) |

**行为**：长轮询领任务（空闲挂起最长 25s）→ 下载代码快照 → venv 执行（自动装 crawlo 与 requirements）→ 每 2s 回报日志、终态回报指标；停止指令经轮询下发（约 1s 内响应）。

**常见问题**：

| 现象 | 处理 |
|---|---|
| 注册失败 | 核对 `--server` 地址从节点侧可达（curl 控制面 `/health` 试一下）；token 与通道一致 |
| 节点反复 OFFLINE | agent 进程没常驻——用一键部署走 systemd；或心跳被防火墙间歇拦截 |
| 任务卡 running 无日志 | 节点上 agent 版本过旧与控制面协议不匹配，重新部署最新 `crawlo_agent.py`（回归测试 `tests/agent_flow_test.py` 可本地验证协议一致性） |
| 控制面重启后任务一直 RUNNING | 已知 V1 缺陷（无启动对账），修复排期见 [V2 计划 Wave A](../v2-development-plan.md)；临时手动将该任务标记失败 |

---

## 5. 任务运行后（四种模式一致）

- **实时日志**：任务详情页 WebSocket 推送；历史日志按级别/时间过滤；
- **指标**：自动解析 pages/items/errors 并回写爬虫运行记录；
- **控制**：停止（全模式）、重试（保留原部署模式与节点）、删除；
- **调度**：给爬虫配 cron/间隔/一次性规则即定时执行，见[调度设计](../designs/scheduling.md)。

## 附录：API 最小示例（任意模式通用）

```bash
TOKEN=$(curl -s -X POST localhost:18000/api/v1/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin&password=admin123' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 派发任务（node_id 留空 = 本地；填节点 ID = 对应模式）
curl -s -X POST localhost:18000/api/v1/execution/tasks \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"spider_id": "1", "node_id": "3"}'

# 轮询状态 / 查看日志
curl -s localhost:18000/api/v1/execution/tasks/<id>/status -H "Authorization: Bearer $TOKEN"
curl -s localhost:18000/api/v1/execution/tasks/<id>/logs   -H "Authorization: Bearer $TOKEN"
```
