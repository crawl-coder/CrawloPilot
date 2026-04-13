# CrawloPilot Spider Runner Docker Image

标准爬虫运行环境 Docker 镜像

## 特性

- ✅ 预装 CrawloPilot SDK
- ✅ 自动配置注入
- ✅ Git 代码拉取
- ✅ 日志与数据上报
- ✅ 心跳保活
- ✅ 系统监控
- ✅ 非 root 用户运行

## 镜像信息

- **名称**: `crawlopilot/spider-runner`
- **基础镜像**: `python:3.10-slim`
- **镜像大小**: ~500MB
- **架构**: linux/amd64, linux/arm64

## 环境变量

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| API_URL | ✅ | - | 平台 API 地址 |
| API_TOKEN | ✅ | - | 认证令牌 |
| TASK_ID | ✅ | - | 任务 ID |
| SPIDER_NAME | ✅ | - | 爬虫名称 |
| GIT_URL | ❌ | - | Git 仓库地址 |
| GIT_BRANCH | ❌ | main | Git 分支 |
| OUTPUT_FORMAT | ❌ | json | 输出格式 |
| OUTPUT_PATH | ❌ | /output | 输出路径 |
| LOG_LEVEL | ❌ | INFO | 日志级别 |
| NODE_ID | ❌ | - | 节点 ID |
| CONTAINER_ID | ❌ | - | 容器 ID |

## 快速开始

### 1. 构建镜像

```bash
cd /Users/oscar/projects/CrawloPilot
./docker/spider-runner/build.sh
```

### 2. 运行容器

```bash
# 基本用法 (已有代码)
docker run -it --rm \
  -e API_URL=http://localhost:8000 \
  -e API_TOKEN=your_token_here \
  -e TASK_ID=task_123 \
  -e SPIDER_NAME=my_spider \
  -v $(pwd)/output:/output \
  crawlopilot/spider-runner:latest

# 从 Git 拉取代码
docker run -it --rm \
  -e API_URL=http://localhost:8000 \
  -e API_TOKEN=your_token_here \
  -e TASK_ID=task_123 \
  -e SPIDER_NAME=my_spider \
  -e GIT_URL=https://github.com/xxx/spider.git \
  -e GIT_BRANCH=main \
  -v $(pwd)/output:/output \
  crawlopilot/spider-runner:latest
```

### 3. 查看输出

```bash
# 查看爬取数据
cat output/items.json

# 查看日志
tar -xzf output/logs.tar.gz
cat spider.log
```

## 目录结构

```
容器内部:
/app/                 # 爬虫代码目录
/output/              # 输出目录 (挂载)
  ├── items.json      # 爬取数据
  ├── logs.tar.gz     # 日志压缩包
  └── config.py       # SDK 配置
/logs/                # 日志目录
  └── spider.log      # 爬虫日志
```

## 工作流程

```
1. 容器启动
   ↓
2. 验证环境变量
   ↓
3. 拉取 Git 代码 (如果设置 GIT_URL)
   ↓
4. 安装依赖 (requirements.txt)
   ↓
5. 注入 SDK 配置
   ↓
6. 上报任务开始
   ↓
7. 启动爬虫
   ↓
8. SDK 自动工作:
   ├─ 日志上报
   ├─ 数据上传
   ├─ 心跳保活
   └─ 指标上报
   ↓
9. 打包日志
   ↓
10. 上报任务完成
   ↓
11. 容器退出
```

## 安全

- ✅ 非 root 用户运行 (crawlopilot:crawlopilot)
- ✅ 最小权限原则
- ✅ 健康检查
- ✅ 资源限制 (通过 Docker run 参数)

## 资源限制示例

```bash
docker run -it --rm \
  --memory=512m \
  --cpus=1.0 \
  --network=crawlopilot-network \
  -e API_URL=http://localhost:8000 \
  -e API_TOKEN=token \
  -e TASK_ID=task_123 \
  -e SPIDER_NAME=my_spider \
  -v $(pwd)/output:/output \
  crawlopilot/spider-runner:latest
```

## 调试

### 进入容器调试

```bash
docker run -it --rm \
  --entrypoint /bin/bash \
  -e API_URL=http://localhost:8000 \
  -e API_TOKEN=token \
  -e TASK_ID=task_123 \
  -e SPIDER_NAME=my_spider \
  crawlopilot/spider-runner:latest
```

### 查看日志

```bash
docker logs <container_id>
docker logs --tail 100 <container_id>
docker logs -f <container_id>
```

## 许可证

MIT License
