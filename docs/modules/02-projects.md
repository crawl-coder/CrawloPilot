# 项目管理

## 职责

项目是爬虫的容器：一个项目下有多个爬虫、多个版本，归属一个团队。
代码通过文件接口上传到项目的爬虫目录。

## 数据模型

- `project`：name/team_id/description/git_url（保留字段）/status
- `project_version`：版本快照（config_snapshot/image_tag）

`status`：`active / archived / deleted`。删除为**软删除**（置为 deleted），列表过滤掉。

## 后端实现（`backend/app/api/v1/projects.py`）

| 接口 | 说明 |
|------|------|
| `GET /projects` | 分页列表（排除已删除） |
| `POST /projects` | 创建（需 team_id） |
| `GET /projects/{id}` | 详情 |
| `PUT /projects/{id}` | 更新 |
| `DELETE /projects/{id}` | 软删除 |
| `POST /projects/{id}/versions` | 创建版本 |
| `GET /projects/{id}/versions` | 版本列表 |

### 代码文件接口（`backend/app/api/v1/project_files.py`）

项目级文件管理（树/内容/创建/删除/重命名），爬虫级文件管理见
[爬虫管理](03-spiders.md)。

### 代码存储约定

```text
uploads/project_{project_id}/spider_{spider_id}/   # 爬虫代码
```

路径由 `backend/app/services/upload_service.py` 统一解析，
本地运行、SSH 上传、Docker 镜像构建、Agent 代码包下载都使用该目录。

## 前端实现

- `frontend/src/views/Projects.vue`：项目列表（创建/编辑/删除/进详情）
- `frontend/src/views/ProjectDetail.vue`：项目信息 + 爬虫列表（详情/运行）
- 创建对话框支持选择团队（`GET /teams`）

## 设计说明

项目详情页内嵌爬虫列表，是"项目 → 爬虫 → 运行"操作路径的中间层；
爬虫的完整管理（编辑/删除/代码）在爬虫管理页，详情页只保留查看与运行。
