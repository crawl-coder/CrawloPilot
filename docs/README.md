# CrawloPilot 文档

CrawloPilot 是爬虫管理平台：在**管理服务器**上管理爬虫项目与定时任务，
通过 SSH / Docker / Agent 三种通道分发到**节点服务器**执行。

本目录是全部文档的入口。按你的身份选择阅读路径，其余内容按需查阅。

---

## 一、按身份选择阅读路径

### 🧑💻 普通用户（只用平台跑爬虫）

关注如何使用，不涉及内部实现。

1. [快速开始](../README.md) —— 安装、启动、登录
2. [产品设计](product-design.md) —— 平台能做什么、功能模块
3. [认证与权限](modules/01-auth.md) —— 登录与账号权限
4. [项目管理](modules/02-projects.md) —— 创建项目
5. [爬虫管理](modules/03-spiders.md) —— 上传代码、Git、运行爬虫
6. **[执行模式使用指南](guides/execution-modes.md)** —— 把爬虫跑到本地/SSH/Docker/Agent 节点
7. [任务管理与日志](modules/06-tasks.md) —— 查看任务、实时日志

### 🧑💻 开发者（参与开发）

需要理解架构与实现。

1. [设计哲学](design-philosophy.md) —— 核心决策与设计原则
2. 模块文档（按业务链路）：
   - [认证与权限](modules/01-auth.md)
   - [项目管理](modules/02-projects.md)
   - [爬虫管理](modules/03-spiders.md)
   - [部署执行](modules/04-execution.md)
   - [节点管理（服务器 × 执行通道）](modules/05-nodes.md)
   - [任务管理与实时日志](modules/06-tasks.md)
   - [前端页面](modules/07-frontend.md)
   - [测试](modules/08-testing.md)
3. 专项设计：
   - [服务器管理](designs/server-management.md)
   - [定时任务调度](designs/scheduling.md)
4. [remaining-work.md](remaining-work.md) —— 版本状态与后续规划
5. [v2-development-plan.md](v2-development-plan.md) —— V2 下一阶段开发任务计划（走查结论 + Wave A–E 排期）
6. [v2-design-revised.md](v2-design-revised.md) / [v2-design.md](v2-design.md) —— V2 架构设计（修订版/原版）

### 🚀 部署运维（上线和维护）

关注部署架构与节点接入。

1. [执行模式使用指南](guides/execution-modes.md) —— 节点接入与任务分发实操（含排错表）
2. [生产环境部署架构](designs/production-deployment.md) —— 全云服务器部署
3. [开发调试环境方案](designs/dev-hybrid-deployment.md) —— Mac + 云服务器调试
4. [Agent 使用说明](../agent/README.md) —— 节点 Agent 部署手册
5. [版本发布管理](releases/README.md) —— 发版流程与版本索引

---

## 二、目录结构与导读

每个子目录都有独立 README 作为该目录的导航首页：

```
docs/
├── README.md                     ← 本文档：总入口（按角色导航）
├── design-philosophy.md          设计哲学与关键决策
├── product-design.md             产品设计（历史愿景稿，以当前实现为准）
├── remaining-work.md             V1 状态与 V2 规划
├── guides/                       任务导向的使用指南
│   └── execution-modes.md        四种执行模式使用指南（本地/SSH/Docker/Agent）
├── modules/                      按模块的功能与实现文档
│   ├── README.md                 ← 模块导读
│   ├── 01-auth.md                认证与权限
│   ├── 02-projects.md            项目管理
│   ├── 03-spiders.md             爬虫管理
│   ├── 04-execution.md           部署执行
│   ├── 05-nodes.md               节点管理
│   ├── 06-tasks.md               任务管理与实时日志
│   ├── 07-frontend.md            前端页面
│   └── 08-testing.md             测试
├── designs/                      专项设计文档
│   ├── README.md                 ← 设计导读
│   ├── production-deployment.md  生产环境部署架构
│   ├── dev-hybrid-deployment.md  开发调试环境方案
│   ├── server-management.md      服务器管理设计
│   └── scheduling.md             定时任务调度设计
├── releases/                     版本发布说明
│   ├── README.md                 ← 版本发布管理（发版流程与索引）
│   ├── TEMPLATE.md               Release 正文模板
│   └── v1.0.0.md                 v1.0.0 发布说明
└── legacy/                       早期阶段历史文档（已过时，仅历史参考）
    └── README.md                 ← 历史文档说明与术语对照
```

---

## 三、常用入口速查

| 我要做什么 | 看哪个文档 |
|-----------|-----------|
| 安装启动平台 | [根 README](../README.md) |
| 跑第一个爬虫 | [爬虫管理](modules/03-spiders.md) |
| 加一台服务器跑任务 | [生产环境部署架构](designs/production-deployment.md) |
| 配置定时任务 | [定时任务调度](designs/scheduling.md) |
| 理解四种执行模式 | [部署执行](modules/04-execution.md) + [节点管理](modules/05-nodes.md) |
| 排查任务问题 | [任务管理与实时日志](modules/06-tasks.md) |
| 发一个新版本 | [版本发布管理](releases/README.md) |
| 改前端页面 | [前端页面](modules/07-frontend.md) |
