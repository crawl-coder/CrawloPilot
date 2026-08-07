# 版本发布管理

> 本文档说明 CrawloPilot 的版本号策略与 GitHub Releases 发布流程。
> 每个版本的发布说明按版本号存放在 `docs/releases/vX.Y.Z.md`，
> 创建 GitHub Release 时直接复制对应文件内容作为正文。

## 版本号策略

采用语义化版本（SemVer）：`MAJOR.MINOR.PATCH`

- `MAJOR`：不兼容的架构/API 变更（如执行器契约重构）
- `MINOR`：向后兼容的新功能（如新增执行模式、调度能力）
- `PATCH`：Bug 修复与细节优化

版本号需要保持三处同步：

| 位置 | 文件 |
|------|------|
| 后端 | `backend/app/__init__.py` 的 `__version__` |
| 前端 | `frontend/package.json` 的 `version` |
| Release 文档 | `docs/releases/vX.Y.Z.md` |

## 发布流程

1. **更新版本号**：同步修改 `backend/app/__init__.py` 与 `frontend/package.json`，
   提交并推送。
2. **编写发布说明**：复制 `docs/releases/TEMPLATE.md` 为 `docs/releases/vX.Y.Z.md`，
   填写新特性、修复、已知事项；在 `docs/releases/README.md` 索引表中登记该版本。
3. **打 Tag 并推送**：

   ```bash
   git tag -a vX.Y.Z -m "CrawloPilot vX.Y.Z"
   git push origin vX.Y.Z
   ```

4. **创建 GitHub Release**：在仓库 [Releases](https://github.com/crawl-coder/CrawloPilot/releases)
   页面点击 *Draft a new release*：
   - Choose a tag：选择刚推送的 `vX.Y.Z`
   - Release title：`CrawloPilot vX.Y.Z`
   - 正文：复制 `docs/releases/vX.Y.Z.md` 的内容
   - 有预编译产物时附件上传到 Assets
5. **验证 CI**：确认 Tag 触发的工作流（backend-test / frontend-test /
   code-quality / security-scan / docker-build）全部通过。

## 版本索引

| 版本 | 日期 | 摘要 | 文档 |
|------|------|------|------|
| [v1.0.0](v1.0.0.md) | 2026-08-07 | 首个正式版：爬虫部署全链路打通 | [v1.0.0.md](v1.0.0.md) |

## Release 正文模板

新建版本时以 [TEMPLATE.md](TEMPLATE.md) 为起点填写。
