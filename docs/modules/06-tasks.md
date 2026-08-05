# 任务管理与实时日志

## 职责

任务（TaskInstance）是平台可观测性的核心：状态、日志、指标、控制操作
（暂停/恢复/停止/重试/删除）都围绕任务展开。

## 后端实现

### 接口

- `backend/app/api/v1/execution.py`（prefix `/execution`）：
  - `POST /execution/tasks`：创建并执行（本地模式）
  - `GET /execution/tasks`：分页列表（`{total, items}`）
  - `GET /execution/tasks/{id}`：任务完整详情（含实时进程状态）
  - `GET /execution/tasks/{id}/status`：状态 + 指标
  - `GET /execution/tasks/{id}/logs`：日志
  - `POST /execution/tasks/{id}/pause|resume|stop`：控制
  - `DELETE /execution/tasks/{id}`：删除
- `backend/app/api/v1/tasks.py`（prefix `/task-instances`）：实例列表/统计/重试/日志/最近任务

### 按模式分发

状态/日志/停止通过 `_get_executor_for_task` 按 `deploy_mode` 分发到
Local/Ssh/Docker/Agent 执行器，保证四种执行方式行为一致。

### 日志落盘

所有执行器统一把日志写到 `uploads/_task_logs/task_{id}.log`：

- 本地：进程 stdout 实时写入
- SSH：远程日志拉取
- Docker：容器日志，清理前落盘
- Agent：agent 实时上报追加

### WebSocket（`backend/app/api/v1/websocket.py`）

`ws://<host>/ws/tasks/{task_id}`：

- 连接后立即推送当前状态
- 持续推送日志行（`{type: "log", data: line}`）
- 周期推送状态增量（`{type: "status", data: {...}}`）
- 客户端可发 `pause / resume / stop` 命令
- 终态后排空日志并断开

## 前端实现

- `frontend/src/views/Tasks.vue`：任务列表（筛选/分页/操作），
  头部自动刷新开关（30 秒轮询），日志弹窗
- `frontend/src/views/TaskDetail.vue`：**执行详情页** `/tasks/:id`：
  - 任务信息（爬虫/项目/节点/模式/时长）
  - 指标卡片（pages/items/errors）
  - 实时日志区（WebSocket 优先，轮询兜底，自动滚动）
  - 控制按钮（暂停/恢复/停止/重试，按状态显示）
- `frontend/src/utils/websocket.js`：WebSocket 客户端封装

## 入口路径

```text
任务列表 → 点击任务 ID → 执行详情页
爬虫详情/项目详情 → 运行 → 自动跳转执行详情页
```
