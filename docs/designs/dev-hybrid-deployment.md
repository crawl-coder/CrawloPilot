> 📘 设计导读：[designs 目录](README.md) ｜ [docs 首页](../README.md)
> 📖 读者：开发/调试 ｜ 关联模块：[节点管理模块](../modules/05-nodes.md)

# 开发调试环境方案（本机 Mac + 云服务器节点）

> 目标：管理服务器跑在本机 Mac（NAT 后），云服务器作为远程节点。
> 本文聚焦开发调试场景下的特殊网络配置（frp 内网穿透、SSH 隧道等）。
> 日期：2026-08-07

---

## 1. 与生产环境的差异

生产环境管理服务器部署在云服务器（有公网 IP），三种模式都不需要内网穿透。
开发环境管理服务器跑在本机 Mac（NAT 后），**只有 Agent 模式需要 frp**，
SSH 和 Docker 模式是 Mac 主动连云服务器（出方向），不受 NAT 影响。

| 模式 | 连接方向 | Mac NAT 后是否受影响 | 解决方案 |
|------|----------|---------------------|----------|
| SSH | Mac → 云服务器 | 不受影响（出方向） | 无需额外配置 |
| Docker | Mac → 云服务器 | 不受影响（出方向） | 云服务器 2375 需对 Mac 可达 |
| Agent | 云服务器 → Mac | **受影响**（入方向被 NAT 拦截） | 需要 frp 内网穿透 |

---

## 2. 架构

```text
┌─────────────────────┐              ┌──────────────────────┐
│   Mac（管理服务器）       │              │  云服务器（远程节点）   │
│                     │              │  117.72.16.51         │
│  前端 :3000          │              │                      │
│  后端 :18000 ←───────┼──────────────│  Agent 进程（回连）    │
│  MySQL:3306          │              │                      │
│  Redis:6379          │   SSH :22    │  SSH :22              │
│  Local 执行（子进程）  │───出方向─────▶│  Docker :2375         │
│                     │   Docker     │                      │
└─────────┬───────────┘              └──────────────────────┘
          │
          │ frp 穿透
          ▼
     公网 frps 服务器（可复用云服务器）
```

---

## 3. SSH 模式（无需额外配置）

Mac 主动 SSH 连接云服务器，出方向不受 NAT 影响。

```bash
# Mac 上直接 SSH 到云服务器
ssh root@117.72.16.51

# 在 CrawloPilot 中创建 SSH 节点：
#   host: 117.72.16.51
#   port: 22
#   user: root
#   ssh_pwd: <密码>  或  ssh_key: <私钥内容>
```

SSH 节点配置完成后，可在 CrawloPilot 中执行「连接测试」验证连通性，再通过运行任务确认端到端可用。

---

## 4. Docker 模式（SSH 隧道绕过安全组限制）

### 4.1 问题：云服务器 2375 公网不可达

云服务器通常在 VPC 内（内网 IP），公网 IP 是网关 NAT。
即使安全组放行 2375，如果云服务商未配置 **DNAT 端口转发**，公网也无法直接访问 2375。

**典型场景**：安全组已放行 2375，但因 VPC 未配 DNAT，
Mac 无法直接访问 `tcp://{节点IP}:2375`。

### 4.2 方案 A：SSH 隧道（推荐，无需改云控制台）

通过 SSH 隧道把 Mac 本地端口转发到云服务器的 2375：

```text
Mac 127.0.0.1:2376  ──SSH 隧道──▶  云服务器 127.0.0.1:2375
```

**启动隧道**（在 Mac 上运行）：

```bash
# 方式 1：SSH 命令行（前台，调试用）
ssh -N -L 2376:127.0.0.1:2375 root@117.72.16.51
# 输入密码后保持窗口不关

# 方式 2：后台持久运行（推荐，重启后需重新启动）
# 使用 paramiko 实现一个守护进程式的隧道转发器，监听 127.0.0.1:2376，
# 将连接通过 SSH 通道转发到节点的 127.0.0.1:2375。
# 可封装为 launchd plist 实现开机自启。
```

**在 CrawloPilot 中创建 Docker 节点**：

```
host: 127.0.0.1
port: 2376
docker_host: tcp://127.0.0.1:2376
```

**注意**：Mac 重启后隧道进程会断，需重新启动。可做成 launchd 服务开机自启。

### 4.3 方案 B：云控制台配置 DNAT（一劳永逸）

在云服务商控制台配置 DNAT 端口转发：

```
公网端口: 2375 → 内网 IP:2375
协议: TCP
```

配置后 Mac 可直接访问 `tcp://117.72.16.51:2375`，无需 SSH 隧道。

> 京东云需要先创建 NAT 网关并绑定弹性公网 IP，然后在 NAT 网关上添加 DNAT 规则。

### 4.4 云服务器 Docker 配置

```bash
# 在云服务器上开启 Docker Remote API
sudo vim /lib/systemd/system/docker.service
# ExecStart=/usr/bin/dockerd -H fd:// -H tcp://0.0.0.0:2375
sudo systemctl daemon-reload && sudo systemctl restart docker

# 配置镜像加速器（国内拉取 Docker Hub 超时）
cat > /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": ["https://registry.cn-hangzhou.aliyuncs.com"],
  "dns": ["114.114.114.114", "8.8.8.8"]
}
EOF
sudo systemctl restart docker
```

### 4.5 常见问题与规避

| 问题 | 原因 | 规避 |
|------|------|------|
| Docker Hub 拉取超时 | 部分云环境访问 Docker Hub 慢 | 配置镜像加速器（阿里云等） |
| `systemd-resolved` 占用 DNS | 127.0.0.53 优先于 resolv.conf | 禁用 systemd-resolved，直接写 resolv.conf |
| Docker COPY 报绝对路径错误 | build context 不接受以 `/` 开头的文件路径 | tar 中使用相对路径（文件名） |
| pip 报 wheel 文件名不合法 | 重命名 wheel 后不符合 `{name}-{version}-*.whl` 规范 | 保留原始文件名 |

---

## 5. Agent 模式（frp 内网穿透）

### 5.1 为什么需要 frp

Agent 是云服务器**主动反向连接**管理服务器 Mac:18000。
但 Mac 在 NAT 后，云服务器无法直接访问 Mac 的 18000 端口，需要 frp 内网穿透。

### 5.2 frp 配置

需要一台有公网 IP 的服务器作为 frps（frp server）。
可以用云服务器本身兼做 frps。

**frps 配置**（在云服务器上）：

```ini
# frps.ini
[common]
bind_port = 7000
```

```bash
# 启动 frps
./frps -c frps.ini
# 安全组放行 7000
```

**frpc 配置**（在 Mac 上）：

```ini
# frpc.ini
[common]
server_addr = 117.72.16.51
server_port = 7000

[crawlopilot]
type = tcp
local_ip = 127.0.0.1
local_port = 18000
remote_port = 28000
```

```bash
# 启动 frpc
./frpc -c frpc.ini
```

**Agent 连接地址**：

```bash
# 云服务器上运行 Agent，指向 frp 暴露的端口
python3 crawlo_agent.py --server http://117.72.16.51:28000 --token <agent_token>
```

frp 把云服务器对 `117.72.16.51:28000` 的访问转发到 Mac 的 `127.0.0.1:18000`。

### 5.3 frp 仅用于开发阶段

> **重要**：frp 只在"管理服务器跑在 Mac（NAT 后）"时需要。
> 一旦管理服务器部署到云服务器（有公网 IP），Agent 直接回连管理服务器公网 IP:18000，
> **frp 完全不需要**。详见 [生产环境部署方案](./production-deployment.md)。

---

## 6. 开发环境快速启动清单

```text
1. Mac 启动服务
   ├── MySQL (本机 3306)
   ├── Redis (本机 6379)
   ├── 后端 (uvicorn :18000)
   └── 前端 (npm run dev :3000)

2. 云服务器配置
   ├── Docker 安装 + Remote API :2375
   ├── Docker Hub 镜像加速器
   └── frps (如需 Agent 模式)

3. Mac 启动隧道/穿透
   ├── SSH 隧道 (Docker 模式用) :2376 → 云服务器 :2375
   └── frpc (Agent 模式用) :28000 → Mac :18000

4. CrawloPilot 创建节点
   ├── SSH 节点: host=117.72.16.51, port=22
   ├── Docker 节点: host=127.0.0.1, port=2376 (隧道)
   └── Agent 节点: 创建后拿 token，在云服务器运行 agent
```
