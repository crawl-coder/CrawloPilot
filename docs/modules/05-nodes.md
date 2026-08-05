# 节点管理

## 职责

节点是**执行目标**。运行爬虫时可指定节点，平台把代码送到节点上执行。
支持三种接入方式（`connect_type`）：SSH 直连、Docker 直连、Agent 代理。

## 节点形态

```text
真实服务器 ── SSH 直连（控制端主动连接，需 SSH 凭据）
          └─ Agent 代理（节点主动反向注册，无需凭据）

Docker daemon（可能部署在真实服务器上）
          └─ Docker 直连（tcp://host:port 或 docker_host 覆盖）
```

一台真实服务器可以同时注册 SSH 节点和多个 Docker 节点（指向不同 daemon）。

## 数据模型（`node`）

关键字段：`name / host / port / connect_type / status / labels / resources /
os_type / os_version / cpu_cores / memory_total / cpu_usage / memory_usage /
agent_version / agent_status / agent_token / last_heartbeat`。

状态机：`online / offline / draining / maintenance`。

## 生命周期

```text
创建（offline）→ 测试连接（真实握手）→ 激活（必须先通过测试）
→ 自动健康检查（每 60s 轻量探活，失败自动 offline）
→ 排空/删除
```

## 后端实现

### API（`backend/app/api/v1/nodes.py` + `backend/app/api/v1/agent.py`）

| 接口 | 说明 |
|------|------|
| `POST/GET/PUT/DELETE /nodes` | 节点 CRUD |
| `POST /nodes/{id}/test` | 测试连接（按类型分发） |
| `POST /nodes/health-check` | 手动全量健康检查 |
| `POST /nodes/{id}/activate` | 激活（先测试，通过才置 online） |
| `POST /nodes/{id}/drain` | 排空（停止容器） |
| `GET /nodes/{id}/containers` | 容器列表（Docker 节点） |
| `POST /nodes/agent/register` | Agent 注册（token → node_id） |
| `POST /nodes/agent/heartbeat` | Agent 心跳 |
| `GET /nodes/agent/tasks` | Agent 领取任务 |
| `GET /nodes/agent/tasks/{id}/code` | 下载爬虫代码包 |
| `POST /nodes/agent/tasks/{id}/logs` | Agent 实时上报日志 |
| `POST /nodes/agent/tasks/{id}/report` | Agent 回报终态 |
| `GET /nodes/agent/tasks/{id}/status` | 查询状态/停止标记 |

### 连接测试（`services/node_service.py`）

- SSH：paramiko 真实握手（登录 + `python3 --version` 探测 + 采集系统信息）
- Docker：DockerService 连接 daemon 获取 info
- Agent：看心跳时间（< 90s 视为在线）

### 自动健康检查

后端启动后在 `main.py` lifespan 中运行后台循环，每 60 秒轻量探活：
SSH/Docker 节点做 TCP ping，Agent 节点看心跳时间；失败自动置 offline。

### Agent 令牌

创建 `connect_type=agent` 节点时自动生成 `agent_token`（创建响应中仅显示一次，
列表/详情不返回），节点上的 agent 程序用它注册。

## 前端实现

- `frontend/src/views/Nodes.vue`：节点卡片网格（类型/状态/资源进度条/心跳）、
  测试/编辑/激活/排空/删除/容器列表；创建 Agent 节点后弹窗展示注册令牌
- 爬虫详情运行对话框可选择节点（SSH/Docker/Agent）

## 安全说明

- SSH 凭据（`ssh_pwd/ssh_key`）当前明文存储在数据库，V2 建议 Fernet 加密
- Agent 接口用 `node_id + token` 认证，不依赖用户 JWT
