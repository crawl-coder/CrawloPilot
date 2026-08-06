# Server（真实服务器）实体管理设计

> 关联文档：[节点管理](../modules/05-nodes.md) 定义了「服务器 × 执行通道」的整体模型；
> 本文细化 **server 实体本身的管理**：字段、生命周期、操作清单、API、前端页面、迁移。

## 1. 目标与范围

解决"有很多台真实服务器"时的管理问题：

- 服务器作为独立实体登记、探测、维护，不再散落在通道里
- 一台服务器下统一管理 SSH / Docker / Agent 三种执行通道
- 集群健康度一眼可见（服务器总状态 + 在线通道数）
- 删除/维护有明确的约束与联动

## 2. 实体模型

### server 表（新增）

```sql
CREATE TABLE server (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    name          VARCHAR(128) NOT NULL UNIQUE,      -- 服务器名称
    host          VARCHAR(256) NOT NULL,             -- IP / 域名
    os_type       VARCHAR(64),                       -- 探测获得：Linux/Windows/macOS
    os_version    VARCHAR(128),                      -- 探测获得
    cpu_cores     INT DEFAULT 0,                     -- 探测获得
    memory_total  BIGINT DEFAULT 0,                  -- 探测获得
    disk_total    BIGINT DEFAULT 0,                  -- 探测获得
    region        VARCHAR(64),                       -- 机房/区域
    labels        JSON,                              -- 自定义标签
    description   VARCHAR(512),                      -- 备注
    status        ENUM('online','offline','maintenance','unknown') DEFAULT 'unknown',
    last_probed_at DATETIME,                         -- 最近探测时间
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

要点：

- **server 不存任何连接凭据**，凭据只挂在通道（node）上
- `status` 四态：`unknown`（刚添加未探测）/ `online`（至少一个通道在线）/
  `offline`（全部通道离线）/ `maintenance`（维护中）

### node 表（改造）

```sql
ALTER TABLE node ADD COLUMN server_id BIGINT NULL;
ALTER TABLE node ADD INDEX ix_node_server_id (server_id);
```

- `server_id` 可空：空 = 独立节点（兼容存量，前端归入"未关联服务器"）
- 迁移脚本为存量节点按 `host` 分组自动创建 server 并回填（可选开关）

## 3. 生命周期与状态机

```text
未添加 → 添加（填名称/IP）→ unknown
  → 探测（TCP 22/2375 可达性 + 通道握手）→ 有在线通道 → online
  → 全部通道离线 → offline
  → 手动维护 → maintenance（运行中任务排空后进入）
  → 删除（约束：无在线通道）
```

### 状态聚合规则

- 服务器总状态 = **任一通道 online 即 online**；无任何通道时为 unknown/offline
- 后端每 60 秒与通道健康检查同步聚合，无需单独轮询

## 4. 管理操作清单（用户视角）

| 操作 | 说明 | 约束 |
|------|------|------|
| 添加服务器 | 名称 + IP + 标签/备注 | 名称唯一 |
| 重新探测 | 手动触发端口/系统探测 | 无 |
| 编辑 | 名称/标签/备注/机房 | 名称唯一 |
| 维护 | 置 maintenance，先排空在线 Docker 通道 | 有运行中任务时提示 |
| 删除 | 删除服务器及其通道 | 无在线通道；有则需先停/删通道 |
| 创建通道 | SSH/Docker/Agent 三选一 | 通道名唯一 |
| 批量导入 | CSV/IP 段（V2） | — |

## 5. 后端 API 设计

新增 `backend/app/api/v1/servers.py`：

```text
POST   /servers                    创建服务器（自动探测）
GET    /servers                    列表（分页 + 关键字 + 状态筛选）
GET    /servers/{id}               详情（含通道摘要与在线通道数）
PUT    /servers/{id}               更新基本信息
DELETE /servers/{id}               删除（无在线通道时）
POST   /servers/{id}/probe         重新探测
POST   /servers/{id}/maintenance   进入维护（先排空在线 Docker 通道）
GET    /servers/{id}/nodes         通道列表
POST   /servers/{id}/nodes         在服务器下创建通道（复用现有 node 创建逻辑）
```

响应示例（列表项）：

```json
{
  "id": 1,
  "name": "beijing-web-01",
  "host": "192.168.1.10",
  "status": "online",
  "region": "北京",
  "labels": {"env": "prod"},
  "cpu_cores": 8,
  "memory_total": 17179869184,
  "channel_summary": {"ssh": 1, "docker": 1, "agent": 0},
  "online_channels": 2,
  "last_probed_at": "2026-08-06T10:00:00"
}
```

## 6. 服务层逻辑（`services/server_service.py`）

```text
create_server    创建 + 触发异步探测
probe_server     探测：TCP 22/2375 可达性 → 更新 last_probed_at
                 若已有关联通道，改为逐通道真实握手并聚合
aggregate_status 聚合：任一通道 online → online；否则 offline
update_server    更新基本信息
delete_server    校验无在线通道 → 删除 server + 关联 node
enter_maintenance 先 drain 在线 Docker 通道 → 置 maintenance
get_channel_summary 按 connect_type 统计通道数
```

后台任务（`main.py` lifespan）：

```text
每 60 秒：通道轻量健康检查（已有）→ 按结果聚合所有 server 状态
```

## 7. 前端页面设计

### 节点管理页（改造）

```text
节点管理
├── Tab ① 服务器（默认）
│   └── 服务器卡片/表格：名称/IP/系统/资源/在线通道数/总状态
│       + 搜索（名称/IP）+ 状态筛选 + 分页 + 「添加服务器」
│       + 卡片操作：详情 / 重新探测 / 编辑 / 维护 / 删除
├── Tab ② SSH 通道      （全部服务器的 SSH 通道，按类型巡检）
├── Tab ③ Docker 通道
└── Tab ④ Agent 通道
```

### 服务器详情页（新增路由 `/servers/:id`）

```text
服务器信息：名称/IP/系统/资源/机房标签/总状态/最近探测时间
  ├─ 操作：编辑 / 重新探测 / 维护 / 删除
  └─ 通道管理（按 SSH/Docker/Agent 分组，复用现有节点卡片）
       ├─ 各组显示通道状态与操作（测试/激活/编辑/删除）
       └─ 「创建通道」按钮 → 类型选择对话框 → 复用现有添加节点表单
```

### 添加服务器对话框

```text
名称* | IP* | 机房 | 标签（逗号分隔）| 备注
提交 → 创建并立即探测 → 显示探测结果与"下一步：创建通道"引导
```

## 8. 数据库迁移与兼容

1. 新增 `server` 表 + `node.server_id`（迁移 `s1e2r3v4e5r6`）
2. 存量节点兼容：`server_id = NULL` 视为独立节点，前端显示在"未关联服务器"分组
3. 可选回填脚本：按 `host` 分组创建 server 并回填，减少手工整理
4. 现有 `/nodes` API 保持不变；新增 `/servers` 系列

## 9. 边界与决策记录

| 决策 | 理由 |
|------|------|
| server 不存凭据 | 权限边界清晰，凭据只属于通道 |
| 总状态 = 任一通道在线 | 服务器"可用"即至少一条路能跑任务 |
| 删除需无在线通道 | 防止误删导致线上任务悬空 |
| 维护先排空 Docker 通道 | 与节点排空语义一致 |
| 探测分层 | 未关联通道时只做端口探测；有关联通道时做真实握手 |
| 批量导入放 V2 | 先保证单台管理闭环 |

## 10. 实施拆解（建议顺序）

> 实施状态：2026-08-06 已完成后端 1-3 与前端 4-5，并基于真实云服务器
> （117.72.16.51）打通「添加服务器 → SSH 通道 → 激活 → 远程运行」全链路。

1. ✅ 后端：server 表 + node.server_id 迁移
2. ✅ 后端：server_service + servers API（CRUD/探测/聚合/通道关联）
3. ✅ 后端：健康检查循环聚合 server 状态
4. ✅ 前端：服务器 Tab + 添加/探测/删除
5. ✅ 前端：服务器详情页 + 通道创建引导（含 Agent 令牌展示）
6. ⏳ 兼容：存量节点回填脚本（可选）
