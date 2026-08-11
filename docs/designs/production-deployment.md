> 📘 设计导读：[designs 目录](README.md) ｜ [docs 首页](../README.md)
> 📖 读者：部署运维 ｜ 关联模块：[节点管理模块](../modules/05-nodes.md)

# 生产环境部署架构

> 管理服务器部署在云服务器 A（公网 IP），节点服务器 B-G 通过 SSH / Docker / Agent
> 三种通道接入。本文描述架构、通信机制、凭证体系与安全规范。

---

## 1. 通信总览

| 模式 | 连接方向 | 协议/端口 | 凭证 |
|------|----------|-----------|------|
| SSH | A → B-G | SSH :22 | 用户名 + 密码/密钥 |
| Docker | A → B-G | TCP :2375 | Docker API 地址（明文，V2 启用 TLS） |
| Agent | B-G → A | HTTP :18000 | agent_token |

管理服务器 A 具有公网 IP，SSH 和 Docker 为出方向连接，Agent 为节点反向回连，
三种模式均无需内网穿透。

**平台模型**：本文中的"节点服务器 B-G"在平台中对应 **Server 实体**（一台真实服务器），
SSH / Docker / Agent 是该服务器下的三种**执行通道**（node）。一台服务器可开通一个或多个通道，
同一服务器的三种通道物理上共存、模型上互相独立。详见
[节点管理：真实服务器 × 执行通道](../modules/05-nodes.md)。

---

## 2. 架构

```text
┌──────────────────────────────────────────┐
│ 管理服务器 A（云服务器，公网 IP）             │
│ 前端 :3000（可配 nginx :80/443）           │
│ 后端 :18000 / MySQL / uploads/             │
│ （运行时仅依赖 MySQL）                       │
└────────────────────┬─────────────────────┘
                 SSH :22 / Docker :2375 │ │ │ │ │ │ │  HTTP :18000（Agent 回连）
          ┌────────────┬───────────────┼─┼─┼─┼─┼─┼──────────┐
          ▼            ▼               ▼                 ▼
      服务器 B       服务器 C       服务器 D ...        服务器 G
   ┌─────────┐  ┌─────────┐   ┌─────────┐         ┌─────────┐
   │SSH 通道 │  │Docker 通道│  │Agent 通道│        │三通道混合│
   │:22      │  │:2375     │  │反向注册  │        │         │
   └─────────┘  └─────────┘   └─────────┘         └─────────┘
```

### 2.1 SSH 模式（A → B-G）

管理服务器 A 通过 paramiko 主动连接节点 22 端口，上传代码到
`/opt/crawlopilot/workspace/{task_id}/`，远程执行入口命令
（优先 `entry_file`，其次自动发现 `run.py / main.py / crawl.py / start.py`，
最后 `crawlo run <spider>`），轮询进程状态并拉取日志。

**节点要求：**

- 开放 22 端口，安全组来源限制为 A 的公网 IP
- `/opt/crawlopilot` 目录对 SSH 用户可写
- Python 3.8+ 及运行依赖（或由执行器自动安装 requirements.txt）

### 2.2 Docker 模式（A → B-G）

管理服务器 A 直连节点 Docker API（`tcp://{host}:2375`），构建任务镜像
（项目 Dockerfile 优先，缺失时用内置模板：基础镜像
`crawlopilot/base:{CRAWLO_VERSION}`（当前 1.7.3）+ 爬虫代码 + 自动装 requirements），
在节点上启动容器执行。

**节点要求：**

- `dockerd` 监听 TCP 2375（`-H tcp://0.0.0.0:2375`）
- 安全组放行 2375，来源限制为 A 的 IP
- 可访问 PyPI 或镜像源（构建依赖）

**网络约束：**

- **同 VPC**：直接使用内网 IP 通信，延迟低且不暴露公网
- **跨 VPC**：需在云控制台配置 DNAT 端口转发（公网:2375 → 内网:2375），
  否则安全组放行也不生效
- **明文 TCP**：当前不支持 TLS，仅适用于受信内网。生产环境应使 A 与 B-G
  同 VPC，或启用 TLS（V2，见 §6）

### 2.3 Agent 模式（B-G → A）

节点运行 `crawlo_agent.py`，主动反向连接管理服务器 A 的 18000 端口。
流程：注册（携带 token）→ 心跳保活 → 长轮询领取任务 → 下载代码 → 执行 → 上报日志。

**部署方式**：可手动复制脚本运行，也推荐使用平台「批量部署 Agent」——
服务器下先有 SSH 通道，平台自动完成上传脚本、写 systemd（开机自启 + 崩溃重启）、
启动并等待上线，多台服务器可勾选批量处理，逐台报告结果。

**管理服务器要求：**

- 18000 端口对节点开放，安全组来源限制为 B-G 的 IP 段
- 节点能访问 A 的公网 IP

**凭证：** 节点创建时自动生成 `agent_token`（UUID），作为 agent 启动参数传入。

---

## 3. 凭证体系

### 3.1 凭证总表

| 凭据 | 存储位置 | 加密 | 持有方 | 用途 |
|------|----------|------|--------|------|
| SSH 密码/密钥 | `node.ssh_pwd` / `node.ssh_key` | Fernet 加密 | 管理服务器 A | 登录节点执行 |
| Docker 地址 | `node.host` / `node.port` / `node.docker_host` | 明文（IP:端口） | 管理服务器 A | 连接 Docker API |
| agent_token | `node.agent_token` | 明文（UUID） | 节点 B-G | 反向认证 |
| 用户 JWT | 前端 localStorage | - | 用户浏览器 | 访问 Web UI |
| Git 凭据 | `git_credential` 表 | Fernet 加密 | 管理服务器 A | 拉取爬虫代码 |

管理服务器集中持有节点凭据并加密落库，节点不保存管理服务器凭据。
Agent 仅持有自身的 token，注册后绑定 node_id。

### 3.2 加解密链路

```text
写入: node_service.create_node
      → encrypt_if_plain(ssh_pwd / ssh_key)   # Fernet 对称加密
      → DB

读取: task_service.create_and_run_task
      → decrypt_or_plain(node.ssh_pwd / ssh_key)
      → ssh_executor.SshConnection(password / key)
      → paramiko 连接
```

| 凭据 | 落库方式 | 运行时解密 |
|------|----------|-----------|
| SSH 密码 | `encrypt_if_plain` → 密文（`gAAAA...`） | `decrypt_or_plain` → 明文传 paramiko |
| SSH 私钥 | `encrypt_if_plain` → 密文 | `decrypt_or_plain` → 明文传 paramiko pkey |
| agent_token | 建节点时 `uuid4().hex` | 明文，无需解密 |
| Git 凭据 | Fernet 加密 | `decrypt_or_plain` |

### 3.3 SSH 免密登录（推荐）

管理服务器 A 通过 SSH 密钥免密登录节点 B-G（单向：A → B-G，节点无需反向登录 A）。
配置完成后，CrawloPilot 节点表单只填私钥、不填密码。

#### 步骤 1：在管理服务器 A 上生成密钥对

```bash
# 在管理服务器 A（云服务器）上执行
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
# 生成两个文件：
#   ~/.ssh/id_ed25519      ← 私钥（后面要粘贴到 CrawloPilot）
#   ~/.ssh/id_ed25519.pub  ← 公钥（后面要分发到各节点）
```

> 如果已有密钥对可跳过此步。检查方式：`ls ~/.ssh/id_ed25519*`

#### 步骤 2：把公钥分发到每台节点服务器

对每台节点 B、C、D... 重复执行：

```bash
# 方式 A：用 ssh-copy-id 自动分发（推荐，需要知道节点密码）
ssh-copy-id -i ~/.ssh/id_ed25519.pub root@<节点IP>
# 输入节点密码，自动追加公钥到节点的 ~/.ssh/authorized_keys

# 方式 B：手动分发（ssh-copy-id 不可用时）
# 2.1 查看公钥内容
cat ~/.ssh/id_ed25519.pub
# 输出类似：ssh-ed25519 AAAAC3Nza... user@host

# 2.2 登录节点服务器
ssh root@<节点IP>

# 2.3 在节点上追加公钥
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "ssh-ed25519 AAAAC3Nza... user@host" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# 2.4 退出节点
exit
```

#### 步骤 3：验证免密登录

```bash
# 在管理服务器 A 上执行，应该不再要求输入密码
ssh root@<节点IP> "echo OK"
# 输出 OK 则配置成功
```

对每台节点都验证一次。

#### 步骤 4：在 CrawloPilot 中创建 SSH 节点

```bash
# 在管理服务器 A 上查看私钥内容
cat ~/.ssh/id_ed25519
# 输出类似：
# -----BEGIN OPENSSH PRIVATE KEY-----
# b3BlbnNzaC1rZXktdjEAAAAABG5vbmU...
# -----END OPENSSH PRIVATE KEY-----
```

在 CrawloPilot Web UI 中创建 SSH 通道：

```
节点管理 → 添加服务器（名称 + IP）
→ 服务器详情 → 创建通道 → 选择「SSH 直连」
  名称:       node-B
  通道类型:    SSH
  主机:       自动取服务器 IP
  SSH 用户:   root
  SSH 密码:   （留空）
  SSH 私钥:   （粘贴上面 cat 输出的完整私钥内容，含 BEGIN/END 行）
```

点击「测试」返回成功 → 「激活」，通道即可用。

> 节点管理页「添加节点」与「创建通道」是同一个流程：先选所属服务器，再填通道信息。

#### 批量配置多台节点

```bash
# 在管理服务器 A 上执行，批量分发公钥
for ip in 192.168.1.11 192.168.1.12 192.168.1.13; do
  echo "配置 $ip ..."
  ssh-copy-id -i ~/.ssh/id_ed25519.pub root@$ip
  ssh root@$ip "echo $ip OK"
done
```

然后在 CrawloPilot 中为每台服务器创建 SSH 通道，私钥都填同一份（A 的私钥）。

#### 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| 连接测试失败，提示密码认证 | 节点表单里填了密码未填私钥，或私钥格式不完整 | 清空密码字段，重新粘贴完整私钥（含 BEGIN/END 行） |
| `Permission denied (publickey)` | 公钥未正确追加到节点 authorized_keys | 检查节点 `~/.ssh/authorized_keys` 是否包含 A 的公钥 |
| `Bad permissions` | `.ssh` 目录权限不对 | `chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys` |
| `Host key verification failed` | 首次连接未信任节点指纹 | `ssh-keyscan <节点IP> >> ~/.ssh/known_hosts` |
| 免密 SSH 成功但 CrawloPilot 测试失败 | 节点表单私钥与 A 上实际私钥不一致 | 重新 `cat ~/.ssh/id_ed25519` 复制粘贴 |

**优势：**

- 统一密钥管理，所有节点共用 A 的一把私钥
- 私钥在管理服务器加密落库（Fernet），节点侧仅保存公钥（公钥无泄露风险）
- 消除密码轮换成本
- 新增服务器只需分发公钥 + 创建 SSH 通道，无需改动已有节点

---

## 4. 节点接入

### 4.1 代码生命周期

#### 4.1.1 代码存放

管理服务器 A 是代码唯一源。克隆或上传时，代码落在：

```
uploads/project_{id}/spider_{id}/    （git 工作区，保留 .git）
```

此目录是 git 工作区，后续的编辑、提交、推送都在这里进行，与节点无关。

#### 4.1.2 代码分发

节点上没有常驻代码，每次运行任务时由管理服务器 A 分发一份运行副本：

| 模式 | 分发方式 | 节点上的路径 | .git 处理 |
|------|----------|-------------|-----------|
| SSH | A 打包 tar.gz → SFTP 上传 → 远程解压 | `/opt/crawlopilot/workspace/{task_id}/` | 随包上传（当前未排除） |
| Docker | A 遍历代码 → 构建镜像时 COPY | 镜像内 `/app` | **排除**（`_iter_code_files` 跳过 `.git`） |
| Agent | A 打包 tar.gz → agent 通过接口下载 | 节点临时目录 | 随包上传 |

> Docker 模式排除 `.git` 是有意设计：避免镜像膨胀和潜在的密钥泄露。

#### 4.1.3 一份代码多节点运行

代码源在管理服务器 A，节点只是运行副本。同一份代码跑多个节点只需：
同一爬虫创建多个任务/调度，分别选不同节点。

```text
管理服务器 A（代码源 uploads/.../spider_1/）
   ├── 任务1 → 节点 B（SSH）      ← 每次运行都从 A 分发最新代码
   ├── 任务2 → 节点 C（Docker）
   └── 任务3 → 节点 D（Agent）
```

节点之间互不干扰，每次运行都是 A 的最新代码。

#### 4.1.4 代码修改流程

节点上的代码是执行副本（临时目录 / 容器镜像），**不是 git 工作区**。
在节点上修改代码不会同步回管理服务器，下次运行时会被新副本覆盖。

正确流程：

1. 在管理服务器 A 修改代码（Web 在线编辑器，或克隆到本地修改）
2. Git 提交 → 推送到远程仓库（平台已实现 commit/push/pull/切分支）
3. 下次运行任务 → A 自动分发最新代码到任意节点

> **禁止在节点上修改代码**：修改不持久、无法提交推送、下次运行丢失。

### 4.2 首次接入一台服务器

```text
1. 节点管理 → 服务器管理 → 添加服务器 B（名称 + IP）
2. 服务器 B → 创建 SSH 通道（用户/密码或密钥）
3. （可选）服务器 B → 创建 Docker 通道（host:2375）
4. （可选）服务器 B → 创建 Agent 通道：点「批量部署 Agent」自动部署，
   或手动运行 `python crawlo_agent.py --server http://A:18000 --token <token>`
5. 测试 → 激活 → 状态变为 online
6. 运行爬虫时选择目标通道即可
```

### 4.3 批量接入建议

- **SSH**：统一使用 root + 密钥，将 A 的公钥加入各节点 `authorized_keys`
- **Docker**：A 与节点同 VPC，使用内网 IP 通信，避免公网暴露明文 2375
- **Agent**：适用于无法开放 22/2375 入站的服务器（如外部合作方），
  仅需节点能访问 A 的 18000 端口

---

## 5. 安全组配置清单

| 位置 | 方向 | 端口 | 来源 | 用途 |
|------|------|------|------|------|
| A | 入站 | 80/443 | 用户浏览器 | Web UI |
| A | 入站 | 18000 | B-G 的 IP 段 | Agent 回连 |
| A | 入站 | 22 | 运维 IP | SSH 管理 |
| B-G | 入站 | 22 | A 的 IP | SSH 模式 |
| B-G | 入站 | 2375 | A 的 IP | Docker 模式（同 VPC 用内网 IP） |
| B-G | 入站 | 2376 | A 的 IP | Docker TLS（V2 启用后） |

> 最小权限原则：来源精确到 IP，不使用 0.0.0.0/0。

---

## 6. 安全演进（V2）

| 项目 | 现状 | V2 目标 |
|------|------|---------|
| Docker 传输 | 明文 TCP | `dockerd --tlsverify` + CA 证书，DockerService 增加 TLS 参数 |
| 网络隔离 | 安全组 IP 白名单 | A 与 B-G 同 VPC 内网通信，公网零暴露 |
| SSH 认证 | 密码/密钥二选一 | 密钥优先，密码仅作备选 |
| 管理服务器可用性 | 单实例 | 调度主备（DB 分布式锁）+ 共享存储 |
| Agent token | 创建时固定 | 支持轮换/失效 |
