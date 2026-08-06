# CrawloPilot 文档

## 阅读路径

首次接触本项目，建议按顺序阅读：

1. [设计哲学](DESIGN_PHILOSOPHY.md) —— 为什么这样设计、核心决策
1. [产品设计](PRODUCT_DESIGN.md) —— 产品定位、功能模块、技术方案
2. [REMAINING_WORK.md](REMAINING_WORK.md) —— 当前版本状态与后续规划
3. 模块文档（按业务链路）：
   - [认证与权限](modules/01-auth.md)
   - [项目管理](modules/02-projects.md)
   - [爬虫管理](modules/03-spiders.md)
   - [部署执行](modules/04-execution.md)
   - [节点管理（服务器 × 执行通道设计）](modules/05-nodes.md)
   - [任务管理与实时日志](modules/06-tasks.md)
   - [前端页面](modules/07-frontend.md)
   - [测试](modules/08-testing.md)

## 目录结构

```
docs/
├── README.md               # 本文档索引
├── DESIGN_PHILOSOPHY.md    # 设计哲学与关键决策
├── PRODUCT_DESIGN.md       # 产品设计文档
├── REMAINING_WORK.md       # V1 状态与 V2 规划
├── modules/                # 按模块的功能与实现文档
│   ├── 01-auth.md
│   ├── 02-projects.md
│   ├── 03-spiders.md
│   ├── 04-execution.md
│   ├── 05-nodes.md
│   ├── 06-tasks.md
│   ├── 07-frontend.md
│   └── 08-testing.md
├── designs/                # 专项设计文档
│   └── server-management.md  # Server 实体管理设计（含 API/前端/迁移）
└── legacy/                 # 早期阶段历史文档（部分功能已裁剪）
```

## 其他入口

- 项目根 [README](../README.md)：快速开始与部署
- [Agent 使用说明](../agent/README.md)：节点 Agent 部署手册
