# 测试

## 验收测试（核心）

`tests/test_deployment_flow.py` 是**部署流程验收测试**，覆盖完整链路：

```text
登录 → 创建项目 → 创建爬虫 → 准备代码 → 运行 → 状态 → 日志 → 停止 → 数据库校验
```

运行方式（需先启动后端）：

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
cd .. && python tests/test_deployment_flow.py
```

当前通过率：18/18。

## 其他测试

| 文件 | 说明 |
|------|------|
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
- WebSocket：`ws://127.0.0.1:8000/ws/tasks/{id}` 观察日志流与终态推送

## 已知问题

- `test_02_projects` 有 3 个用例失败：测试脚本期望的响应格式与当前分页/删除接口
  不一致（既有问题，非本次改动引入）
- 依赖 `pytest`、`aiomysql` 需在 `crawlo_pilot` 环境安装
