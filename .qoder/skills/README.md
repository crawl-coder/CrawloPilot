# CrawloPilot 项目 Skills 索引

## 📚 可用 Skills

### 1. [项目开发规范](./crawlopilot-dev.md)
**适用场景**: 了解项目整体结构、技术栈和开发规范

**包含内容**:
- 项目概述和定位(爬虫部署平台)
- 技术栈说明
- 目录结构说明
- 后端/前端开发规范
- 爬虫管理注意事项
- Git 提交规范
- 常用命令
- 默认账号和访问地址

---

### 2. [API 开发指南](./api-development.md)
**适用场景**: 开发新的 API 接口

**包含内容**:
- API 路由结构
- 已实现的 API 列表
- 创建新 API 的步骤
- Pydantic Schema 定义
- 权限控制
- 错误处理
- 最佳实践

---

### 3. [数据库开发指南](./database-guide.md)
**适用场景**: 数据库模型设计、迁移管理

**包含内容**:
- 数据库配置
- 核心数据模型
- Alembic 迁移管理
- 创建新模型示例
- 数据库查询示例
- Pydantic Schema 定义
- 数据库调试技巧
- 数据备份方法

---

### 4. [前端开发指南](./frontend-guide.md)
**适用场景**: 前端页面开发

**包含内容**:
- 技术栈说明
- 项目结构
- 组件开发规范
- API 调用方式
- 路由配置
- 表单处理
- 表格使用
- Element Plus 组件
- 状态管理
- 调试技巧

---

### 5. [Celery 异步任务](./celery-tasks.md)
**适用场景**: 开发异步任务

**包含内容**:
- Celery 架构
- 创建新任务
- 任务装饰器选项
- 任务重试机制
- 任务链和编排
- 定时任务
- 监控和管理
- 最佳实践
- 启动 Worker

---

## 🚀 快速开始

### 新用户上手
1. 阅读 [项目开发规范](./crawlopilot-dev.md)
2. 了解 [API 开发指南](./api-development.md)
3. 学习 [前端开发指南](./frontend-guide.md)

### 开发新功能
1. 数据库设计 → [数据库开发指南](./database-guide.md)
2. 后端 API → [API 开发指南](./api-development.md)
3. 异步任务 → [Celery 异步任务](./celery-tasks.md)
4. 前端页面 → [前端开发指南](./frontend-guide.md)

### 日常开发
- 启动服务: `./start-dev.sh`
- 数据库迁移: `alembic upgrade head`
- 启动 Worker: `celery -A app.workers.celery_app worker`

---

### 6. [监控告警系统](./monitoring-alerts.md) ⭐ NEW
**适用场景**: 配置监控指标和告警规则

**包含内容**:
- Prometheus指标采集
- Grafana仪表板
- 告警规则配置
- 多渠道通知（邮件/钉钉/企业微信）
- 健康检查机制

---

### 7. [Git集成与文件上传](./git-upload.md) ⭐ NEW
**适用场景**: 项目代码管理

**包含内容**:
- Git仓库克隆/拉取/推送
- 分支和标签管理
- 本地代码包上传（ZIP/TAR）
- 自动解压和验证

---

### 8. [测试指南](./testing-guide.md) ⭐ NEW
**适用场景**: 编写和运行测试

**包含内容**:
- 单元测试编写
- 集成测试框架
- 页面级联调测试
- 测试运行器使用
- 覆盖率报告

---

### 9. [爬虫管理开发指南](./spider-management.md) ⭐ NEW
**适用场景**: 开发和管理爬虫项目

**包含内容**:
- 分步创建向导设计
- 卡片/列表视图实现
- 代码编辑和Git管理
- 数据模型和API接口
- 常见问题和最佳实践

---

## 📋 项目状态

### 已完成 ✅
- ✅ Phase 1: 核心基座(用户/权限/项目)
- ✅ Phase 2: 部署引擎(Docker 容器管理)
- ✅ Phase 3: 调度系统(APScheduler + DAG)
- ✅ Phase 4: 监控告警(Prometheus + Grafana + 多渠道通知)
- ✅ Phase 5: 数据质量(检测规则 + 统计分析)
- ✅ Phase 6: 代理池与API管理(代理健康检查 + API限流熔断)
- ✅ Phase 7: 生产加固(安全审计 + 性能优化 + CI/CD)
- ✅ 爬虫管理优化(分步创建、卡片视图、代码编辑器)

### 核心特性
- 🎯 完整的项目管理能力(Git集成 + 本地上传)
- 🕷️ **爬虫管理**(分步创建向导、卡片/列表视图、代码编辑、Git管理)
- 🚀 自动化部署(Docker容器化)
- ⏰ 灵活的任务调度(Cron/间隔/DAG依赖)
- 📊 实时监控告警(多维度指标 + 多渠道通知)
- 🔍 数据质量检测(空值/重复/格式/时效性)
- 🌐 代理池管理(自动健康检查 + 智能分配)
- 🔒 安全审计(操作日志 + 权限控制 + API限流)

---

## 🔗 重要资源

### 文档
- [README.md](../README.md) - 项目说明
- [DEVELOPMENT.md](../DEVELOPMENT.md) - 开发指南
- [STARTUP_GUIDE.md](../STARTUP_GUIDE.md) - 启动指南
- [DEFAULT_ACCOUNTS.md](../DEFAULT_ACCOUNTS.md) - 默认账号

### 外部文档
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Vue3 文档](https://vuejs.org/)
- [Element Plus 文档](https://element-plus.org/)
- [Celery 文档](https://docs.celeryq.dev/)
- [Alembic 文档](https://alembic.sqlalchemy.org/)

---

## 💡 使用建议

1. **开发前**: 先阅读相关指南，了解项目规范
2. **开发中**: 参考最佳实践和示例代码
3. **遇到问题**: 查看常见问题和调试技巧
4. **提交代码**: 遵循 Git 提交规范

---

**最后更新**: 2026-04-11 (爬虫管理页面优化完成)
