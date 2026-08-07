# 任务管理与实时日志

## 职责

任务（TaskInstance）是平台可观测性的核心：状态、日志、指标、控制操作
（暂停/恢复/停止/重试/删除）都围绕任务展开。

## 后端实现

### 接口

- `backend/app/api/v1/execution.py`（prefix `/execution`，任务 API 统一入口）：
  - `POST /execution/tasks`：创建并执行（本地模式）
  - `GET /execution/tasks`：分页列表（`{total, items}`，支持 spider_id/schedule_id/node_id/status 过滤）
  - `GET /execution/tasks/running`：运行中的任务
  - `GET /execution/tasks/stats/summary`：统计概览（可按 schedule_id 过滤）
  - `GET /execution/tasks/recent`：最近任务
  - `GET /execution/tasks/schedule/{schedule_id}`：指定调度的任务
  - `GET /execution/tasks/status/{status}`：指定状态的任务
  - `GET /execution/tasks/{id}`：任务完整详情（含实时进程状态）
  - `GET /execution/tasks/{id}/status`：状态 + 指标
  - `GET /execution/tasks/{id}/logs`：日志
  - `POST /execution/tasks/{id}/pause|resume|stop`：控制
  - `POST /execution/tasks/{id}/retry`：重试（终态任务；保留原节点与部署模式）
  - `DELETE /execution/tasks/{id}`：删除
- 历史路由 `/task-instances/*` 已于 2026-08-07 收敛至此（旧文件 tasks.py 已删除）

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

## 定时调度（Schedule）

任务来源有两种：手动运行（`schedule_id` 为空）与定时触发（`schedule_id` 指向调度）。

- 调度引擎：`backend/app/services/scheduler_service.py`，进程内 APScheduler，
  随 lifespan 启停；支持 cron / interval / once 三种触发，默认时区 Asia/Shanghai
- 统一入口：`task_service.create_and_run_task`（手动与定时共用同一套校验/创建/分发）
- 幂等：`task_instance.(schedule_id, expected_run_at)` 唯一索引兜底，
  一次触发最多创建一个任务；run-now 不占幂等槽位（`expected_run_at=NULL`）
- 并发守卫：同调度 PENDING+RUNNING 任务数 >= max_concurrency 时跳过本次触发
- 错跑检测：重启后补偿窗口（默认 24h，env `SCHEDULE_COMPENSATION_HOURS`）内记
  `skipped` 不追跑，超窗只推进 `next_run_time`
- 一次性调度：触发后自动 `enabled=false` 并清空 `next_run_time`
- 删除调度/爬虫：任务历史保留（外键引用置 NULL），调度行级联删除
- API：`/schedules` CRUD / enable / disable / run-now / preview / history，
  详见 `docs/designs/scheduling.md`
- 测试：`tests/schedule_test.py`（35 项端到端，含真实触发等待）
