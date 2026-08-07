# 分布式部署方案（控制面 + 多节点服务器）

> 目标：CrawloPilot 控制面部署到云服务器 **A**，服务器 **B/C/D/E/F/G** 作为节点
> 加入节点管理，每台服务器下再创建 SSH / Docker / Agent 三种执行通道。
> 本文描述服务器间通信机制、所需凭证、使用流程，并确认方案可行性。
> 日期：2026-08-07

---

## 1. 结论先行

**方案可行**，且比当前 frp 内网穿透方案**更简单**：

- 当前 frp 方案是因为**控制面跑在 Mac（NAT 后）**，云端节点无法主动访问，才需要反向隧道；
- 控制面一旦部署到云服务器 A（公网 IP 固定），节点 B-G 天然可达，**三种模式都不需要 frp**；
- 代码现状已支持该架构（SSH/Docker 直连、Agent 反向注册均已实现并通过验证）。

通信总览：

| 模式 | 连接方向 | 协议/端口 | 凭证 |
|------|----------|-----------|------|
| SSH | A → B-G | SSH :22 | SSH 用户名 + 密码/密钥 |
| Docker | A → B-G | TCP :2375 | Docker API 地址（无 TLS） |
| Agent | B-G → A | HTTP :8000 | agent_token（注册令牌） |

---

## 2. 架构与通信机制

```text
                        ┌─────────────────────────────┐
                        │  控制面 A（云服务器，公网 IP） │
                        │  前端 :80 / 后端 :8000       │
                        │  MySQL / Redis / uploads/    │
                        └──────────────┬──────────────┘
                 SSH :22 / Docker :2375 │ │ │ │ │ │ │  HTTP :8000（Agent 回连）
          ┌────────────┬───────────────┼─┼─┼─┼─┼─┼──────────┐
          ▼            ▼               ▼                 ▼
      服务器 B       服务器 C       服务器 D ...        服务器 G
    ┌─────────┐  ┌─────────┐   ┌─────────┐         ┌─────────┐
    │SSH 节点  │  │Docker 节点│  │Agent 节点│        │三通道混合│
    │:22       │  │:2375     │  │反向注册   │        │         │
    └─────────┘  └─────────┘   └─────────┘         └─────────┘
```

### 2.1 SSH 模式（A → B-G）

- 控制面 A 通过 paramiko 主动连接节点服务器 22 端口；
- 执行流程：A 把代码打包上传到 B-G 的 `/opt/crawlopilot/workspace/{task_id}/`，
  远程执行 `python main.py`，轮询状态/拉取日志；
- **要求**：B-G 开放 22 端口给 A（安全组来源限制为 A 的公网 IP）；
- **要求**：B-G 上 `/opt/crawlopilot` 目录对 SSH 用户可写（root 或 chown）；
- **要求**：B-G 有 Python 3.8+ 及爬虫运行所需依赖（或由系统执行器安装 requirements.txt）。

### 2.2 Docker 模式（A → B-G）

- 控制面 A 直连 B-G 的 Docker API（`tcp://{host}:2375`）；
- 执行流程：A 构建任务镜像（基础镜像 `crawlopilot/base:1.7.2` + 爬虫代码），
  在 B-G 上启动容器执行；
- **要求**：B-G 的 `dockerd` 监听 2375（`-H tcp://0.0.0.0:2375`），
  安全组放行 2375 给 A；
- **要求**：B-G 有 Docker 且可访问 PyPI/镜像源（构建依赖）；
- **已知限制**：当前 Docker 直连为**明文 TCP**（无 TLS），仅适合受信内网/VPC；
  生产环境建议改用 SSH 隧道或私有网络，详见 §6。
- **跨公网注意**：若 A 与 B-G 不在同一 VPC，云服务商的公网 IP 通常需要配置
  **DNAT 端口转发**（公网:2375 → 内网:2375），否则安全组放行也不生效。
  2026-08-07 实测中京东云未配 DNAT，改用 SSH 隧道绕过（详见 §7）。

### 2.3 Agent 模式（B-G → A）

- 在 B-G 上运行 `crawlo_agent.py`，**主动反向连接**控制面 A 的 8000 端口；
- 流程：注册（带 token）→ 心跳 → 领取任务 → 下载代码 → 执行 → 上报日志；
- **要求**：A 的 8000 端口对 B-G 开放（安全组放行，来源限制为 B-G 的 IP 段）；
- **要求**：B-G 能访问到 A（控制面在公网或 VPC 内时天然满足）；
- 凭证：节点创建时生成的 `agent_token`，agent 启动参数传入。

---

## 3. 凭证体系

### 3.1 凭证总表

| 凭证 | 存哪里 | 加密 | 谁持有 | 用途 |
|------|--------|------|--------|------|
| SSH 密码/密钥 | node 表 `ssh_pwd`/`ssh_key` | Fernet 加密落库 | 控制面 A | A 登录 B-G 执行 |
| Docker 地址 | node 表 `host`/`port`/`docker_host` | 明文（IP/端口） | 控制面 A | A 连接 B-G Docker API |
| agent_token | node 表 `agent_token` | 明文 | 节点 B-G（agent 启动参数） | B-G 反向认证到 A |
| 用户 JWT | 前端 localStorage | - | 用户浏览器 | 访问控制面 Web UI |
| Git 凭据 | git_credential 表 | Fernet 加密 | 控制面 A | 拉取爬虫代码 |

**原则**：控制面 A 集中持有节点凭据（加密落库），节点不保存控制面凭据；
agent 只持自己的 token（注册后即绑定 node_id）。

### 3.2 各模式凭证准备步骤

**SSH 模式**（每台节点服务器 B-G）：

```bash
# 1. 确保 SSH 服务开启且密码/密钥可用
# 2. 确保工作目录可写
sudo mkdir -p /opt/crawlopilot/workspace
sudo chown -R root:root /opt/crawlopilot   # 或用执行用户
# 3. 在 CrawloPilot 节点管理里创建 SSH 节点，填 host/port/用户/密码或密钥
```

### 3.3 免密登录最佳实践（推荐）

**目标**：控制面 A 与节点 B-G 之间建立 SSH 互信，节点只填密钥、不填密码。

**一次性配置**（在控制面 A 执行，对每台节点服务器 B-G）：

```bash
# 1. 控制面 A 生成密钥对（如已有可跳过）
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519

# 2. 把 A 的公钥加入 B-G 的 authorized_keys（每台节点执行一次）
ssh-copy-id root@<B-G 的 IP>
# 或手动：
# echo "$(cat ~/.ssh/id_ed25519.pub)" >> ~/.ssh/authorized_keys

# 3. 验证免密
ssh root@<B-G 的 IP> "echo OK"
```

**在 CrawloPilot 中创建节点**：

- SSH 节点只填 `ssh_key`（A 的私钥内容），**不填 ssh_pwd**；
- 系统 SSH 执行器原生支持 RSA / Ed25519 密钥认证（paramiko pkey 方式）；
- 已实测：仅密钥节点连接测试成功、任务执行 SUCCESS（2026-08-07）。

**优点**：

- 所有节点统一用一把私钥管理，无需记忆各服务器密码；
- 私钥在控制面 A 加密落库（Fernet），节点侧只保存 A 的公钥（公钥无泄露风险）；
- 免去密码认证带来的口令管理/轮换成本。

### 3.4 凭据加密现状（已实现）

控制面 A 集中持有节点凭据、**加密落库**的功能当前已实现并实测通过：

| 凭据 | 落库方式 | 实测证据 |
|------|----------|----------|
| SSH 密码 | `encrypt_if_plain`（Fernet）写入 `node.ssh_pwd` | 创建节点后 DB 为密文（`gAAAA...`），运行时 `decrypt_or_plain` 解密 |
| SSH 私钥 | `encrypt_if_plain`（Fernet）写入 `node.ssh_key` | 仅密钥节点 DB 存 652 字符密文，无明文私钥 |
| agent_token | 建节点时自动生成 uuid 写入 `node.agent_token` | 节点创建即带 token |
| Git 凭据 | Fernet 加密（个人/团队凭据） | 已通过加密测试 |

**加解密链路**（代码路径）：

```text
写入: node_service.create_node → encrypt_if_plain(ssh_pwd/ssh_key) → DB
读取: task_service.create_and_run_task → decrypt_or_plain(node.ssh_pwd/ssh_key)
      → ssh_executor.SshConnection(password/key) → paramiko 连接
```

**结论**：无需额外开发，"控制面集中持有 + 加密落库"模型已经可用。

**Docker 模式**（每台节点服务器 B-G）：

```bash
# 1. 修改 /etc/docker/daemon.json 或 docker.service，监听 TCP
# ExecStart=/usr/bin/dockerd -H unix:///var/run/docker.sock -H tcp://0.0.0.0:2375
sudo systemctl daemon-reload && sudo systemctl restart docker
# 2. 安全组放行 2375（来源：控制面 A 的 IP）
# 3. 在节点管理创建 Docker 节点，填 host:2375
```

**Agent 模式**（每台节点服务器 B-G）：

```bash
# 1. 控制面先创建 Agent 节点 → 获得 agent_token
# 2. 在 B-G 上运行（可做成 systemd 服务）：
python3 crawlo_agent.py --server http://<控制面A>:8000 --token <agent_token>
# 3. 控制面安全组放行 8000（来源：B-G 的 IP）
```

---

## 4. 使用流程（用户操作视角）

### 4.0 代码生命周期（多节点前提）

**控制面 A 是代码唯一源**，节点只有运行副本（详见
[爬虫管理模块代码生命周期](../modules/03-spiders.md#代码生命周期控制面为唯一代码源)）：

```text
代码源：A 的 uploads/project_{id}/spider_{id}/（git 工作区，保留 .git）
   │
   ├── 任务1 → 节点 B（SSH）      ← 每次运行从 A 分发最新代码
   ├── 任务2 → 节点 C（Docker）
   └── 任务3 → 节点 D（Agent）
```

- 同一份代码多节点运行：每建一个任务/调度并选节点，即分发一次；
- 代码修改：在控制面（在线编辑器或本地）→ Git 提交/推送 →
  下次运行自动生效；
- **不要在节点上改代码**：节点副本不持久、无法经平台提交推送。

### 4.1 首次接入一台服务器（以 B 为例）

```text
1. 节点管理 → 服务器管理 → 添加服务器 B（填名称 + IP）
2. 服务器 B → 创建 SSH 节点（host/port/用户/密码或密钥）
3. （可选）服务器 B → 创建 Docker 节点（host:2375）
4. （可选）服务器 B → 创建 Agent 节点（获得 token）
5. 探测/连接测试 → B 的状态变为 online
6. 运行爬虫时选择目标节点（SSH/Docker/Agent）即可
```

### 4.2 批量接入 B-G 的推荐路径

- 所有节点统一用 **root + 密钥**（把 A 的 SSH 公钥加入各服务器 `authorized_keys`），
  密码与密钥二选一即可；
- Docker 模式建议**只在 A 与 B-G 同 VPC/内网时使用明文 2375**；
- Agent 模式适合**无法开 22/2375 出方向**的服务器（如外部合作方），
  只需要它能访问 A 的 8000。

---

## 5. 安全组/防火墙配置清单

| 位置 | 方向 | 端口 | 来源/目的 | 用途 |
|------|------|------|-----------|------|
| A 安全组 | 入站 | 80/443 | 用户浏览器 | Web UI |
| A 安全组 | 入站 | 8000 | B-G 的 IP 段 | Agent 回连 |
| A 安全组 | 入站 | 22 | 运维 | SSH 管理 |
| B-G 安全组 | 入站 | 22 | A 的 IP | SSH 模式 |
| B-G 安全组 | 入站 | 2375 | A 的 IP | Docker 模式 |
| B-G 安全组 | 入站 | 2376 | A 的 IP（如启用 TLS） | Docker TLS |

> 最小权限原则：来源尽量精确到 IP，不要用 0.0.0.0/0。

---

## 6. 生产环境安全建议（V2）

1. **Docker 直连加 TLS**：用 `dockerd --tlsverify` + CA/客户端证书，
   DockerService 增加 TLS 参数（当前仅支持明文 TCP）；
2. **VPC 内网**：A 与 B-G 在同一 VPC 时用内网 IP，避免公网暴露；
3. **SSH 密钥优先**：控制面 A 统一管理各节点密钥，密码仅作备选；
4. **多实例控制面**：Scheduler 主备（Redis 分布式锁）+ 共享 `UPLOAD_DIR`；
5. **Agent token 轮换**：agent_token 支持重建/失效。

---

## 7. 可行性验证记录（2026-08-07 实测）

| 模式 | 本机 | 京东云 117.72.16.51 | 结论 |
|------|------|---------------------|------|
| SSH | ✅ 成功 | ✅ 成功 | 直连可行 |
| Docker | ✅ 成功 | ✅ 成功（SSH 隧道绕过安全组） | **未验证公网直连**，见下方说明 |
| Agent | ✅ 成功 | ✅ 成功（frp 隧道） | 反向连接可行 |

> **Docker 模式实测说明**：
> 京东云服务器在 VPC 内（内网 IP `172.16.0.3`），公网 IP `117.72.16.51` 是网关 NAT。
> 安全组放行 2375 后，由于 VPC 网关未配置 DNAT 端口转发，**公网无法直接访问 2375**。
> 实际使用 SSH 隧道（Mac `127.0.0.1:2376` → 京东云 `127.0.0.1:2375`）绕过此限制。
>
> **结论**：Docker 模式在**控制面与节点同 VPC/内网**时直连可行；在**跨公网**场景下，
> 要么在云控制台配置 DNAT（2375 → 内网:2375），要么使用 SSH 隧道，要么启用 TLS（V2）。
>
> frp 隧道仅用于"控制面在 NAT 后"的过渡场景；控制面上云后无需 frp。

---

## 8. 与 frp 方案的对比

| 维度 | frp 内网穿透（当前） | 控制面上云（目标） |
|------|---------------------|-------------------|
| 组件 | frps（云端）+ frpc（Mac） | 无额外组件 |
| 链路 | Mac ←frp→ 云 → agent | A 直连 B-G（SSH/Docker）或 B-G 回连 A（Agent） |
| 稳定性 | 依赖 frpc 常驻、隧道保活 | 原生 TCP/HTTP，稳定 |
| 安全 | frp 7000/18000 额外暴露 | 仅标准端口（22/2375/8000） |
| 适用 | 开发机在 NAT 后 | 生产部署 |
