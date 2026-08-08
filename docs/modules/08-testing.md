> 📖 模块导航：[导读](README.md) ｜ [docs 首页](../README.md)
> 🔗 上一篇：[前端页面](07-frontend.md)

# 测试

## 验收测试（核心）

`tests/test_deployment_flow.py` 是**部署流程验收测试**，覆盖完整链路：

```text
登录 → 创建项目 → 创建爬虫 → 准备代码 → 运行 → 状态 → 日志 → 停止 → 数据库校验
```

运行方式（需先启动后端）：

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 18000
cd .. && python tests/test_deployment_flow.py
```

当前通过率：18/18。

## 其他测试

| 文件 | 说明 |
|------|------|
| `tests/full_flow_test.py` | 前后端全流程联调（41/41，覆盖 13 个页面接口） |
| `tests/schedule_test.py` | 定时调度端到端（35/35，含 cron 真实触发/幂等/启停/once 自动停用/级联删除，约 4 分钟） |
| `tests/git_credentials_test.py` | Git 凭据体系端到端（34/34，个人凭据/团队凭据池/引用保护/脱敏） |
| `tests/ws_push_test.py` | WebSocket 日志与状态推送验证 |
| `tests/api_test.py` | API 全量冒烟（登录后逐接口校验） |
| `tests/test_pagination.py` / `tests/test_pagination_auto.py` | 分页行为专项 |
| `tests/integration/pages/` | 页面级联调（nodes/spiders/tasks） |
| `tests/unit/test_01_auth.py` | 认证单测（6/6） |
| `tests/unit/test_02_projects.py` | 项目单测（部分用例与分页/删除接口格式不匹配，待修） |
| `tests/unit/test_edge_cases.py` | 边界条件（已移除调度相关用例） |
| `tests/unit/test_performance.py` | 性能测试 |
| `tests/integration/` | 页面联调与集成流程 |
| `tests/scenarios/test_scenarios.py` | 真实场景 |
| `tests/project_assessment.py` | 项目评估报告生成器 |

## 手动验证脚本

开发过程中使用的端到端验证：

- 本地模式：运行 → 状态 pending→running→success → 详情/日志
- Docker 模式：建 docker 节点 → 运行 → 容器构建/执行/清理
- Agent 模式：建 agent 节点 → 启动 `agent/crawlo_agent.py` → 派发任务 → 停止指令
- WebSocket：`ws://127.0.0.1:18000/ws/tasks/{id}` 观察日志流与终态推送

## 已知问题

- ~~`test_02_projects` 有 3 个用例失败~~（2026-08-07 已修复 7/7：分页/删除断言兼容
  当前接口格式 + `APIClient.put` 参数修正 + 注册开关回退）
- 依赖 `pytest`、`aiomysql` 需在 `crawlo_pilot` 环境安装
