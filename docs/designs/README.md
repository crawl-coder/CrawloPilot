# designs/ 专项设计文档

本目录收录**跨模块的专项设计**，解决"某个主题怎么落地"的问题。
区别于 [modules/](../modules/)（按业务链路描述当前实现），
本目录更侧重**部署架构**与**特定功能的设计**。

## 文档一览

| 文档 | 主题 | 读者 |
|------|------|------|
| [production-deployment.md](production-deployment.md) | 生产环境部署架构（全云服务器） | 部署运维 |
| [dev-hybrid-deployment.md](dev-hybrid-deployment.md) | 开发调试环境方案（Mac + 云服务器） | 开发/调试 |
| [server-management.md](server-management.md) | Server 实体管理设计 | 开发者 |
| [scheduling.md](scheduling.md) | 定时任务调度设计 | 开发者 |

## 两个部署文档的区别

| | 生产环境 | 开发调试 |
|---|----------|----------|
| 管理服务器位置 | 云服务器 A（公网 IP） | Mac（NAT 后） |
| 是否需要穿透 | 否，直连 | Agent 需 frp，Docker 需 SSH 隧道 |
| 适用场景 | 正式上线 | 本地开发联调 |

> 核心原则：**生产环境零穿透**。只有"管理服务器在 NAT 后"的开发阶段才需要 frp/隧道。
> 管理服务器有公网 IP 后，SSH/Docker 出方向直连、Agent 节点反向回连，均无需穿透。

## 与其他目录的关联

- **模型定义**：Server/Node 模型见 [节点管理](../modules/05-nodes.md)
- **执行器实现**：四种执行器见 [部署执行](../modules/04-execution.md)
- **历史方案**：早期部署思路见 [legacy/](../legacy/README.md)（已过时）
