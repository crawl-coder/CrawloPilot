# 前端页面

## 技术栈

Vue3 + Vite + Element Plus + Pinia + Vue Router + ECharts

## 目录结构

```text
frontend/src/
├── api/          # 后端接口封装（auth/project/spider/execution/node/team/monitoring）
├── components/   # 通用组件（Pagination/StatCard）
├── composables/  # 组合式函数
├── router/       # 路由与守卫
├── utils/        # 通用工具（状态映射/格式化/WebSocket）
└── views/        # 页面
```

## 页面清单与职责

| 页面 | 路由 | 职责 |
|------|------|------|
| Login | `/login` | 登录 |
| Dashboard | `/dashboard` | 统计概览（项目/爬虫/任务/节点） |
| Projects | `/projects` | 项目列表 |
| ProjectDetail | `/projects/:id` | 项目信息 + 爬虫列表 + 运行 |
| Spiders | `/spiders` | 爬虫列表（卡片/列表）+ 创建向导 |
| SpiderDetail | `/spiders/:id` | 代码结构 + 运行记录 + 运行对话框 |
| Tasks | `/tasks` | 任务列表（筛选/操作/日志） |
| TaskDetail | `/tasks/:id` | 执行详情（状态/指标/实时日志） |
| Nodes | `/nodes` | 节点管理（SSH/Docker/Agent） |
| Users | `/users` | 用户管理 |

## 布局

侧边栏菜单顺序：仪表盘 → 项目管理 → 爬虫管理 → 任务管理 → 节点管理 → 系统管理。

## 交互约定

- 运行爬虫后自动跳转到执行详情页，形成"运行 → 监控"闭环
- 任务列表点击任务 ID 进入详情页
- 执行详情页实时日志：WebSocket 优先，断线自动轮询兜底（每 3 秒）
- 节点添加后自动测试连接（Agent 节点弹窗展示注册令牌）
- 统一通过 `utils/common.js` 的状态映射显示（爬虫启用态 vs 任务运行态分离）

## 开发配置

`frontend/vite.config.js`：开发端口 3000，`/api` 代理到 `http://127.0.0.1:8000`。
